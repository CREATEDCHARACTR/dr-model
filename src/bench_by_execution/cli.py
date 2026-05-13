"""
bench-by-execution CLI.

One command, runs the public tasks against any model, prints both
scores side-by-side. The Format Scorer Trap surfaces in the gap.

    bench-by-execution demo --model anthropic/claude-haiku-4.5
    bench-by-execution demo --model openai/gpt-4.1-mini --tasks 3
    bench-by-execution compare --models anthropic/claude-opus-4.7,anthropic/claude-haiku-4.5

— Dr Model
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .harness import HarnessedClient, CompletionResult
from .executor import executor_score, format_score
from .tasks import PUBLIC_TASKS


# ─────────────────────────────────────────────────────────────────
# Output formatting — clean, prints well on a screen recording
# ─────────────────────────────────────────────────────────────────

# ANSI color codes. Detect tty; degrade to plain if not a terminal.
_USE_COLOR = sys.stdout.isatty()


def _c(s: str, color: str) -> str:
    if not _USE_COLOR:
        return s
    codes = {
        "green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m",
        "blue": "\033[34m", "bold": "\033[1m", "dim": "\033[2m",
        "reset": "\033[0m",
    }
    return f"{codes.get(color, '')}{s}{codes['reset']}"


def _check(ok: bool) -> str:
    return _c("✓", "green") if ok else _c("✗", "red")


def _format_cost(cost: Optional[float]) -> str:
    if cost is None:
        return "?"
    if cost < 0.001:
        return f"${cost*1000:.3f}m"  # millicents
    return f"${cost:.4f}"


# ─────────────────────────────────────────────────────────────────
# demo command
# ─────────────────────────────────────────────────────────────────

def _save_bench_json(out_path: str, payload: dict) -> None:
    """Persist a bench run to JSON. Schema matches dual-delta-reporter
    consumers: top-level {timestamp_iso, model, tasks, results, summary}.

    Phase 1 of dr-model: bench results are now auditable + replayable.
    Without this, every demo run printed and vanished — the
    Format Scorer Trap evidence was ephemeral.
    """
    from pathlib import Path
    p = Path(out_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, default=str))


def cmd_demo(args: argparse.Namespace) -> int:
    """Run the public tasks against one model, both arms, print side-by-side."""
    tasks = PUBLIC_TASKS[:args.tasks] if args.tasks else PUBLIC_TASKS

    client = HarnessedClient(model=args.model, api_key=args.api_key)
    # Phase 1: collect per-row results so we can persist via --out
    rows: List[dict] = []

    print()
    print(_c("═" * 72, "dim"))
    print(_c(f"  bench-by-execution — model: {args.model}", "bold"))
    print(_c(f"  tasks: {len(tasks)}  •  contract: public-v1.0  •  scorer: executor + format", "dim"))
    print(_c("═" * 72, "dim"))
    print()

    h_exec_scores: List[int] = []
    u_exec_scores: List[int] = []
    h_fmt_scores: List[int] = []
    u_fmt_scores: List[int] = []
    total_cost: float = 0.0

    for i, task in enumerate(tasks, 1):
        task_id = task["id"]
        print(_c(f"[{i}/{len(tasks)}] {task_id}", "bold"))

        # HARNESSED arm
        h_resp = client.complete(task["prompt"], harnessed=True)
        if h_resp.error:
            print(f"   HARNESSED   {_c('API ERROR', 'red')}: {h_resp.error[:80]}")
            h_exec = type("R", (), {"score": 0, "reason": "api error"})()
            h_fmt = {"score_pct": 0, "files_found": []}
        else:
            h_exec = executor_score(
                h_resp.text,
                task_id=task_id,
                harness=task["harness"],
            )
            h_fmt = format_score(h_resp.text, expected_files=task["expected_files"])
            print(
                f"   HARNESSED   exec={_c(str(h_exec.score), 'green' if h_exec.score == 3 else 'yellow' if h_exec.score >= 2 else 'red')}/3  "
                f"format={h_fmt['score_pct']:>3}  "
                f"{_check(h_exec.score == 3)}  "
                f"({h_exec.reason[:60]})"
            )
        h_exec_scores.append(h_exec.score)
        h_fmt_scores.append(h_fmt["score_pct"])
        if h_resp.cost_usd:
            total_cost += h_resp.cost_usd

        # UNHARNESSED arm
        u_resp = client.complete(task["prompt"], harnessed=False)
        if u_resp.error:
            print(f"   UNHARNESSED {_c('API ERROR', 'red')}: {u_resp.error[:80]}")
            u_exec = type("R", (), {"score": 0, "reason": "api error"})()
            u_fmt = {"score_pct": 0, "files_found": []}
        else:
            u_exec = executor_score(
                u_resp.text,
                task_id=task_id,
                harness=task["harness"],
            )
            u_fmt = format_score(u_resp.text, expected_files=task["expected_files"])
            print(
                f"   UNHARNESSED exec={_c(str(u_exec.score), 'green' if u_exec.score == 3 else 'yellow' if u_exec.score >= 2 else 'red')}/3  "
                f"format={u_fmt['score_pct']:>3}  "
                f"{_check(u_exec.score == 3)}  "
                f"({u_exec.reason[:60]})"
            )
        u_exec_scores.append(u_exec.score)
        u_fmt_scores.append(u_fmt["score_pct"])
        if u_resp.cost_usd:
            total_cost += u_resp.cost_usd
        # Phase 1: per-row record for persistence
        rows.append({
            "task_id":   task_id,
            "harnessed": {
                "exec_score":   h_exec.score,
                "exec_reason":  h_exec.reason,
                "format_score": h_fmt["score_pct"],
                "files_found":  h_fmt.get("files_found", []),
                "raw_text":     getattr(h_resp, "text", "") or "",
                "cost_usd":     getattr(h_resp, "cost_usd", None),
                "error":        getattr(h_resp, "error", None),
            },
            "unharnessed": {
                "exec_score":   u_exec.score,
                "exec_reason":  u_exec.reason,
                "format_score": u_fmt["score_pct"],
                "files_found":  u_fmt.get("files_found", []),
                "raw_text":     getattr(u_resp, "text", "") or "",
                "cost_usd":     getattr(u_resp, "cost_usd", None),
                "error":        getattr(u_resp, "error", None),
            },
        })
        print()

    # Summary
    n = len(tasks)
    h_exec_mean = sum(h_exec_scores) / n
    u_exec_mean = sum(u_exec_scores) / n
    h_fmt_mean = sum(h_fmt_scores) / n
    u_fmt_mean = sum(u_fmt_scores) / n

    print(_c("═" * 72, "dim"))
    print(_c("  RESULTS", "bold"))
    print(_c("═" * 72, "dim"))
    print(f"                        FORMAT SCORE       EXECUTOR SCORE")
    print(f"  Harnessed             {h_fmt_mean:>6.1f}/100         {h_exec_mean:>4.2f}/3.00")
    print(f"  Unharnessed           {u_fmt_mean:>6.1f}/100         {u_exec_mean:>4.2f}/3.00")
    print(f"  Δ (harness lift)      {_c(f'+{h_fmt_mean - u_fmt_mean:>5.1f}', 'yellow'):>20}     "
          f"{_c(f'+{h_exec_mean - u_exec_mean:>4.2f}', 'green'):>15}")
    print()
    print(f"  Total cost: {_format_cost(total_cost)}")
    print()
    print(_c("  The gap between the two Δs is The Format Scorer Trap.", "dim"))
    print(_c("  Format-score lift = harness teaches the format gate.", "dim"))
    print(_c("  Executor-score lift = harness teaches actual problem-solving.", "dim"))
    print(_c("  Industry benchmarks measure the first; the second is what matters.", "dim"))
    print()

    # Phase 1: persist if --out provided
    if getattr(args, "out", None):
        import time as _time
        payload = {
            "timestamp_iso": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "model": args.model,
            "n_tasks": n,
            "results": rows,
            "summary": {
                "harnessed_exec_mean":    h_exec_mean,
                "unharnessed_exec_mean":  u_exec_mean,
                "harnessed_format_mean":  h_fmt_mean,
                "unharnessed_format_mean": u_fmt_mean,
                "delta_exec":             h_exec_mean - u_exec_mean,
                "delta_format":           h_fmt_mean - u_fmt_mean,
                "total_cost_usd":         total_cost,
            },
        }
        _save_bench_json(args.out, payload)
        print(_c(f"  → saved bench JSON to {args.out}", "dim"))
        print()

    return 0


# ─────────────────────────────────────────────────────────────────
# compare command — multi-model side-by-side
# ─────────────────────────────────────────────────────────────────

def cmd_compare(args: argparse.Namespace) -> int:
    """Run the public tasks against multiple models; print a matrix."""
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    tasks = PUBLIC_TASKS[:args.tasks] if args.tasks else PUBLIC_TASKS

    print()
    print(_c("═" * 80, "dim"))
    print(_c(f"  bench-by-execution compare — {len(models)} models × {len(tasks)} tasks", "bold"))
    print(_c("═" * 80, "dim"))
    print()

    results = []
    for model in models:
        print(_c(f"Running {model}…", "dim"))
        client = HarnessedClient(model=model, api_key=args.api_key)
        h_scores: List[int] = []
        u_scores: List[int] = []
        cost = 0.0
        for task in tasks:
            h_resp = client.complete(task["prompt"], harnessed=True)
            if not h_resp.error:
                h_s = executor_score(h_resp.text, task_id=task["id"], harness=task["harness"]).score
            else:
                h_s = 0
            h_scores.append(h_s)
            if h_resp.cost_usd:
                cost += h_resp.cost_usd

            u_resp = client.complete(task["prompt"], harnessed=False)
            if not u_resp.error:
                u_s = executor_score(u_resp.text, task_id=task["id"], harness=task["harness"]).score
            else:
                u_s = 0
            u_scores.append(u_s)
            if u_resp.cost_usd:
                cost += u_resp.cost_usd

        results.append({
            "model": model,
            "harnessed_mean": sum(h_scores)/len(h_scores),
            "unharnessed_mean": sum(u_scores)/len(u_scores),
            "cost": cost,
        })

    # Matrix print
    print()
    print(_c(f"{'model':<40} {'harnessed':>12} {'unharnessed':>13} {'cost':>10}", "bold"))
    print(_c("─" * 80, "dim"))
    for r in results:
        h = r["harnessed_mean"]
        u = r["unharnessed_mean"]
        print(
            f"{r['model']:<40} "
            f"{_c(f'{h:>5.2f}/3.00', 'green' if h >= 2.5 else 'yellow'):>20} "
            f"{u:>6.2f}/3.00 "
            f"{_format_cost(r['cost']):>10}"
        )
    print()
    print(_c("Same task pool, same scorer, different price tiers.", "dim"))
    print(_c("The executor scorer ignores which model the response came from.", "dim"))
    print()
    return 0


# ─────────────────────────────────────────────────────────────────
# main entry point
# ─────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bench-by-execution",
        description=(
            "Bench LLMs by running their code. Expose 'The Format Scorer Trap' "
            "by scoring with both a format scorer (the kind industry uses) and "
            "an executor scorer (the kind that measures actual problem-solving). "
            "When you run a cheap model and a premium model on the same tasks, "
            "the format-score gap is much bigger than the executor-score gap. "
            "That gap is the trap. — Dr Model"
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="Run public tasks against one model, both arms")
    p_demo.add_argument("--out", default=None,
                          help="Path to save bench JSON (per-row results + summary). "
                               "Without this, the run prints + vanishes.")
    p_demo.add_argument("--model", required=True,
                        help="Provider-prefixed model slug (e.g. anthropic/claude-haiku-4.5)")
    p_demo.add_argument("--tasks", type=int, default=None,
                        help="Number of tasks to run (default: all 5)")
    p_demo.add_argument("--api-key", default=None,
                        help="OpenRouter API key (default: $OPENROUTER_API_KEY)")
    p_demo.set_defaults(func=cmd_demo)

    p_cmp = sub.add_parser("compare", help="Run multiple models side-by-side")
    p_cmp.add_argument("--models", required=True,
                       help="Comma-separated list of model slugs")
    p_cmp.add_argument("--tasks", type=int, default=None)
    p_cmp.add_argument("--api-key", default=None)
    p_cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
