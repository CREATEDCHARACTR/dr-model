"""
HarnessedClient — wraps any LLM call with the public-tier EXECUTION CONTRACT.

The thing the YouTuber points at any model — OpenRouter, Anthropic
direct, OpenAI direct, or local Ollama. The harness prepends the public
contract to the user message. Without the harness, you measure the raw
model. With the harness, you measure the model + contract.

If you bench both arms (with + without) and score with `executor_score`,
you'll see what the doctrine calls "The Format Scorer Trap":

  - Format score lifts substantially with the harness (often +15 to +35
    points)
  - Executor score barely moves with the harness (often <+0.5 / 3.0)
  - Therefore: the harness teaches the model to satisfy the format gates
    the format scorer checks; the model's actual problem-solving
    capability is determined by its baseline, not the harness

That gap is the trap. Most LLM rankings are format-score rankings. They
mistake format-compliance teaching for capability lift.

— Dr Model
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .contract import PUBLIC_CONTRACT, contract_version


@dataclasses.dataclass
class CompletionResult:
    text: str
    model_used: str
    latency_s: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    error: Optional[str] = None
    harnessed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# Per-million-token blended cost (approximate — for cost-comparison only;
# operators should verify against their provider's live pricing).
# Numbers reflect public OpenRouter pricing as of 2026-05.
_COST_PER_M_BLENDED: Dict[str, float] = {
    # Anthropic
    "anthropic/claude-opus-4.7": 45.00,
    "anthropic/claude-sonnet-4.6": 9.00,
    "anthropic/claude-haiku-4.5": 3.00,
    # OpenAI
    "openai/gpt-5.5": 17.50,
    "openai/gpt-4.1-mini": 1.00,
    "openai/gpt-4o-mini": 0.30,
    # Moonshot
    "moonshotai/kimi-k2-thinking": 1.50,
    "moonshotai/kimi-k2": 1.50,
    # DeepSeek
    "deepseek/deepseek-chat-v3.1": 0.30,
    "deepseek/deepseek-v3.2-exp": 0.30,
    "deepseek/deepseek-r1": 0.55,
    # Qwen
    "qwen/qwen3-235b-a22b-thinking-2507": 0.50,
}


def _estimate_cost(model: str, in_tokens: Optional[int], out_tokens: Optional[int]) -> Optional[float]:
    if in_tokens is None or out_tokens is None:
        return None
    rate = _COST_PER_M_BLENDED.get(model)
    if rate is None:
        return None
    # Blended approximation: rate is roughly (in_cost + 4*out_cost)/5,
    # so just multiply (in + out) by rate / 1_000_000. Operator can plug
    # in exact rates per provider for precision.
    return (in_tokens + out_tokens) * rate / 1_000_000


class HarnessedClient:
    """LLM client that optionally wraps each call with the EXECUTION CONTRACT.

    Args:
        model: provider-prefixed model slug. Examples:
            "anthropic/claude-haiku-4.5"   (OpenRouter)
            "openai/gpt-4.1-mini"          (OpenRouter)
            "moonshotai/kimi-k2-thinking"  (OpenRouter)
            "deepseek/deepseek-v3.2-exp"   (OpenRouter)
        api_key: OpenRouter key. If None, reads OPENROUTER_API_KEY env.
        base_url: API base. Defaults to OpenRouter. Override for
                  Anthropic-direct or OpenAI-direct if you want.
        contract: which contract to apply when harnessed=True. Default
                  is the public-tier contract. Pass an empty string to
                  test what bare-contract bench looks like.

    Usage:
        client = HarnessedClient(model="anthropic/claude-haiku-4.5")

        # WITHOUT the contract (raw model behavior — what most APIs send)
        bare = client.complete("Build word_count.py ...", harnessed=False)

        # WITH the contract (the harness wrapping the call)
        harnessed = client.complete("Build word_count.py ...", harnessed=True)

        # Compare: format score will lift; executor score barely will.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        contract: Optional[str] = None,
        max_tokens: int = 4000,
        timeout_s: float = 360.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "No API key. Pass api_key= or set OPENROUTER_API_KEY in env."
            )
        self.base_url = base_url.rstrip("/")
        self.contract = PUBLIC_CONTRACT if contract is None else contract
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s

    def complete(
        self,
        task: str,
        *,
        harnessed: bool = True,
        system: Optional[str] = None,
    ) -> CompletionResult:
        """Call the model with the task.

        If harnessed=True (default), prepends the EXECUTION CONTRACT to
        the user message. If False, sends just the task — the raw API
        call most operators write.
        """
        messages: List[Dict[str, str]] = []
        sys_msg = system or "You are a careful coding assistant."
        messages.append({"role": "system", "content": sys_msg})

        if harnessed:
            user_content = f"{self.contract}\n\n---\n\nTask:\n{task}"
        else:
            user_content = task
        messages.append({"role": "user", "content": user_content})

        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        # Note: reasoning models (gpt-5, o1, kimi-k2-thinking) may need
        # different params. Most OpenRouter endpoints tolerate the basic
        # shape; we don't add reasoning-specific params here. Operators
        # who need them can subclass HarnessedClient.

        start = time.time()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/dr-model/bench-by-execution",
                "X-Title": "bench-by-execution",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_text = ""
            try:
                err_text = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            return CompletionResult(
                text="",
                model_used=self.model,
                latency_s=time.time() - start,
                error=f"HTTP {e.code}: {err_text}",
                harnessed=harnessed,
            )
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            return CompletionResult(
                text="",
                model_used=self.model,
                latency_s=time.time() - start,
                error=f"{type(e).__name__}: {e}",
                harnessed=harnessed,
            )

        text = ""
        usage = data.get("usage") or {}
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            text = ""

        in_tokens = usage.get("prompt_tokens")
        out_tokens = usage.get("completion_tokens")
        cost = _estimate_cost(self.model, in_tokens, out_tokens)

        return CompletionResult(
            text=text,
            model_used=data.get("model") or self.model,
            latency_s=time.time() - start,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
            error=None,
            harnessed=harnessed,
        )
