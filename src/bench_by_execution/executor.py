"""
Executor scorer — the ground-truth measurement that exposes the Format Scorer Trap.

Most LLM benchmarks score by checking if the output LOOKS like correct
code (presence of fenced blocks, names matching expected files, regex
matches). That's a format-fit measurement. Models that learn to satisfy
the format gate score high regardless of whether the code actually works.

This module measures whether the code WORKS. It:
  1. Extracts each FILE block from the model's response
  2. Writes each block to an isolated temp directory
  3. Invokes the script with test inputs (per the task's harness)
  4. Compares actual output to expected output
  5. Returns a score 0..3

Rubric:
  0 = couldn't extract / file missing / crashed / syntax error
  1 = ran but output is wrong
  2 = ran, output mostly right with minor flaw
  3 = ran, output matches what the task asked for

The score is what would happen if a human ran the code and checked it.
That's the ground truth. Format scorers are a proxy for it; this module
IS it.

— Dr Model
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# FILE-block extraction. The opening fence may use any of these forms,
# all of which we accept (some models add language identifiers despite
# the contract — we tolerate it and strip the stray line if present so
# the extracted body parses).
FILE_BLOCK_RE = re.compile(
    r"```(?:FILE|file):\s*(?P<filename>[^\n]+?)\n(?P<body>.*?)```",
    re.DOTALL,
)


@dataclasses.dataclass
class ExecutorResult:
    """One task's execution result. Composable; trivially JSON-serializable.

    score is the headline number (0..3). reason is the one-line
    explanation a human would write looking at the same evidence.
    extracted_files lists what files were pulled from the response (lets
    you debug "the model produced 3 files but we only ran 1").
    """
    score: int
    reason: str
    extracted_files: List[str]
    elapsed_s: float
    crashed: bool = False
    stdout_preview: str = ""
    stderr_preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def extract_file_blocks(text: str) -> Dict[str, str]:
    """Pull FILE: <name>-fenced blocks out of a model response.

    Tolerates the common bug where a model adds a stray language
    identifier line right after the opening fence (e.g. `python` after
    ```FILE: x.py). We strip that line if present and the rest still
    parses. Other extractors might score these responses as 0 because
    of the language-identifier; we choose to give the code the benefit
    of the doubt and let the execution test decide.
    """
    files: Dict[str, str] = {}
    for m in FILE_BLOCK_RE.finditer(text):
        name = m.group("filename").strip()
        body = m.group("body")
        # Strip a leading stray language identifier line if present
        # (common bug on Haiku, intermittent on Kimi K2 Thinking).
        lines = body.splitlines()
        if lines and lines[0].strip().lower() in (
            "python", "py", "bash", "sh", "javascript", "js",
            "typescript", "ts", "ruby", "rb",
        ):
            body = "\n".join(lines[1:])
        files[name] = body
    return files


def _run(cwd: Path, argv: List[str], stdin_bytes: Optional[bytes] = None,
         timeout: float = 8.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        input=stdin_bytes,
        cwd=str(cwd),
        capture_output=True,
        timeout=timeout,
    )


def _materialize_files(files: Dict[str, str], target_dir: Path) -> List[str]:
    written: List[str] = []
    for name, body in files.items():
        if name == "__unnamed__":
            continue
        # Don't allow path traversal — basename only.
        safe = Path(name).name
        (target_dir / safe).write_text(body, encoding="utf-8")
        written.append(safe)
    return written


def executor_score(
    response_text: str,
    *,
    task_id: str,
    harness: Dict[str, Any],
    timeout_s: float = 10.0,
) -> ExecutorResult:
    """Score a model response by executing the code it produced.

    Args:
        response_text: the model's raw response (with FILE blocks inside)
        task_id: identifier used for logging/debugging
        harness: a dict with keys:
            primary_file: the filename the task expected
            prepare(tmp_dir): callable that writes test inputs
            invoke(tmp_dir, script_path): callable returning CompletedProcess
            check(completed, tmp_dir): callable returning (int score, str reason)
        timeout_s: hard timeout per subprocess invocation

    Returns:
        ExecutorResult with score, reason, extracted_files, timing.
    """
    start = time.time()
    files = extract_file_blocks(response_text)
    if not files:
        return ExecutorResult(
            score=0,
            reason="no FILE blocks extracted from response",
            extracted_files=[],
            elapsed_s=time.time() - start,
            crashed=False,
        )

    tmp_path = Path(tempfile.mkdtemp(prefix="execscore_"))
    try:
        written = _materialize_files(files, tmp_path)
        primary = harness["primary_file"]
        script_path = tmp_path / primary

        if not script_path.exists():
            return ExecutorResult(
                score=0,
                reason=f"primary file '{primary}' not produced (extracted: {written})",
                extracted_files=written,
                elapsed_s=time.time() - start,
                crashed=False,
            )

        # Prepare any test-input fixtures
        harness["prepare"](tmp_path)

        try:
            completed = harness["invoke"](tmp_path, script_path)
        except subprocess.TimeoutExpired:
            return ExecutorResult(
                score=0,
                reason=f"script exceeded {timeout_s}s timeout",
                extracted_files=written,
                elapsed_s=time.time() - start,
                crashed=True,
            )
        except Exception as e:
            return ExecutorResult(
                score=0,
                reason=f"invoke failed: {type(e).__name__}: {e}",
                extracted_files=written,
                elapsed_s=time.time() - start,
                crashed=True,
            )

        try:
            score, reason = harness["check"](completed, tmp_path)
        except Exception as e:
            return ExecutorResult(
                score=0,
                reason=f"check failed: {type(e).__name__}: {e}",
                extracted_files=written,
                elapsed_s=time.time() - start,
                crashed=True,
            )

        stdout_str = completed.stdout.decode("utf-8", "replace") if completed.stdout else ""
        stderr_str = completed.stderr.decode("utf-8", "replace") if completed.stderr else ""

        return ExecutorResult(
            score=score,
            reason=reason,
            extracted_files=written,
            elapsed_s=time.time() - start,
            crashed=completed.returncode != 0,
            stdout_preview=stdout_str[:200],
            stderr_preview=stderr_str[:200],
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


# Quick-shape format scoring — the kind of measurement industry benchmarks
# use. Provided here so users can run BOTH scorers and see the gap.
def format_score(
    response_text: str,
    *,
    expected_files: List[str],
) -> Dict[str, Any]:
    """Format-fit scoring (the kind that traps people).

    Returns a dict with:
        score_pct: 0-100, weighted sum of three gates
        breakdown: which gates fired and why
        files_found: filenames extracted from response

    The three gates:
      50% — at least one expected file present (named match)
      30% — body parses (Python: ast.parse; bash: nonempty)
      20% — a run command is named (demo.sh or inline `python script.py`)

    These are the same gates industry benchmarks tend to check. They
    correlate WEAKLY with actual code correctness (r ≈ 0.4-0.6 in
    practice). Run `executor_score` against the same response to see
    the divergence.
    """
    import ast

    files = extract_file_blocks(response_text)
    expected_set = set(expected_files)
    found_names = set(files.keys())
    breakdown: Dict[str, str] = {}

    if expected_set & found_names:
        file_pts = 50
        breakdown["file_present"] = "yes (named match)"
    elif files:
        file_pts = 15
        breakdown["file_present"] = f"partial — got {sorted(found_names)} expected {sorted(expected_set)}"
    else:
        file_pts = 0
        breakdown["file_present"] = "no FILE blocks"

    parse_pts = 0
    if files:
        primary = next(iter(expected_set & found_names), None) or next(iter(found_names))
        body = files[primary]
        if body.strip():
            if primary.endswith(".py"):
                try:
                    ast.parse(body)
                    parse_pts = 30
                    breakdown["body_parses"] = "yes (Python)"
                except SyntaxError as e:
                    parse_pts = 5
                    breakdown["body_parses"] = f"no — {e.msg}"
            else:
                parse_pts = 30
                breakdown["body_parses"] = "yes (non-Python; assumed valid)"
        else:
            breakdown["body_parses"] = "no — empty body"
    else:
        breakdown["body_parses"] = "no — no files"

    invoke_pts = 0
    if "demo.sh" in files:
        invoke_pts = 20
        breakdown["invoke_named"] = "yes (demo.sh)"
    elif re.search(r"\b(python3?\s+\S+\.py|bash\s+\S+\.sh)\b", response_text):
        invoke_pts = 15
        breakdown["invoke_named"] = "yes (inline command)"
    else:
        breakdown["invoke_named"] = "no"

    total = file_pts + parse_pts + invoke_pts
    return {
        "score_pct": total,
        "breakdown": breakdown,
        "files_found": sorted(found_names),
    }
