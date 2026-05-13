"""
5 public-tier tasks with executor harnesses.

Each harness defines:
  prepare(tmp_dir): write any test-input files the script needs
  invoke(tmp_dir, script_path): run the script with the right argv/stdin
  check(completed_process, tmp_dir): score 0..3 + reason

The tasks are deliberately simple CLI exercises — the methodology
generalizes; you can layer harder tasks on top using the same shape.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


def _run(script: Path, argv: List[str], stdin: Optional[bytes] = None,
         cwd: Optional[Path] = None, timeout: float = 8.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(script)] + argv,
        input=stdin,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        timeout=timeout,
    )


# ──────────────────────────────────────────────────────────────────
# task 1 — word_count
# ──────────────────────────────────────────────────────────────────

def _t1_prepare(tmp: Path) -> None:
    (tmp / "sample.txt").write_text(
        "The quick brown fox. The lazy dog!\nThe FOX runs.\n",
        encoding="utf-8",
    )


def _t1_invoke(tmp: Path, script: Path) -> subprocess.CompletedProcess:
    return _run(script, [str(tmp / "sample.txt")], cwd=tmp)


def _t1_check(p: subprocess.CompletedProcess, tmp: Path) -> Tuple[int, str]:
    if p.returncode != 0:
        return 0, f"exit {p.returncode}: {p.stderr.decode('utf-8','replace')[:120]}"
    out = p.stdout.decode("utf-8", "replace").strip()
    try:
        n = int(out.splitlines()[-1] if out else "")
    except ValueError:
        return 1, f"output not an integer: {out[:60]!r}"
    if n == 7:
        return 3, "exact match (7 unique words)"
    if 6 <= n <= 8:
        return 2, f"off-by-one tolerance — got {n}, expected 7"
    return 1, f"wrong count: got {n}, expected 7"


# ──────────────────────────────────────────────────────────────────
# task 2 — csv_to_json
# ──────────────────────────────────────────────────────────────────

def _t2_prepare(tmp: Path) -> None:
    (tmp / "in.csv").write_text(
        "name,age,city\nAlice,30,NYC\nBob,25,LA\n",
        encoding="utf-8",
    )


def _t2_invoke(tmp: Path, script: Path) -> subprocess.CompletedProcess:
    return _run(script, [str(tmp / "in.csv"), str(tmp / "out.json")], cwd=tmp)


def _t2_check(p: subprocess.CompletedProcess, tmp: Path) -> Tuple[int, str]:
    import json
    if p.returncode != 0:
        return 0, f"exit {p.returncode}: {p.stderr.decode('utf-8','replace')[:120]}"
    out_path = tmp / "out.json"
    if not out_path.exists():
        return 1, "out.json not created"
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return 1, f"out.json malformed: {e}"
    if not isinstance(data, list) or len(data) != 2:
        return 1, f"expected list of 2 rows; got len={len(data) if hasattr(data,'__len__') else '?'}"
    row0 = data[0]
    if not isinstance(row0, dict) or set(row0.keys()) != {"name", "age", "city"}:
        return 1, f"keys wrong: {list(row0.keys()) if isinstance(row0, dict) else type(row0).__name__}"
    if row0.get("name") != "Alice" or row0.get("city") != "NYC":
        return 1, f"row[0] values wrong: {row0}"
    return 3, "JSON matches CSV exactly"


# ──────────────────────────────────────────────────────────────────
# task 3 — uniq_sort
# ──────────────────────────────────────────────────────────────────

def _t3_prepare(tmp: Path) -> None:
    pass


def _t3_invoke(tmp: Path, script: Path) -> subprocess.CompletedProcess:
    return _run(script, [], stdin=b"banana\napple\ncherry\napple\nbanana\n", cwd=tmp)


def _t3_check(p: subprocess.CompletedProcess, tmp: Path) -> Tuple[int, str]:
    if p.returncode != 0:
        return 0, f"exit {p.returncode}: {p.stderr.decode('utf-8','replace')[:120]}"
    out = [l for l in p.stdout.decode("utf-8", "replace").splitlines() if l]
    if out == ["apple", "banana", "cherry"]:
        return 3, "exact match"
    if sorted(out) == ["apple", "banana", "cherry"]:
        return 2, f"unique correct but unsorted: {out}"
    return 1, f"wrong output: {out[:5]}"


# ──────────────────────────────────────────────────────────────────
# task 4 — json_pretty
# ──────────────────────────────────────────────────────────────────

def _t4_prepare(tmp: Path) -> None:
    pass


def _t4_invoke(tmp: Path, script: Path) -> subprocess.CompletedProcess:
    return _run(script, [], stdin=b'{"b":2,"a":1,"nested":{"z":3,"y":4}}', cwd=tmp)


def _t4_check(p: subprocess.CompletedProcess, tmp: Path) -> Tuple[int, str]:
    if p.returncode != 0:
        return 0, f"exit {p.returncode}: {p.stderr.decode('utf-8','replace')[:120]}"
    out = p.stdout.decode("utf-8", "replace")
    if '"a"' not in out or '"b"' not in out:
        return 1, "missing keys"
    if out.find('"a"') > out.find('"b"'):
        return 1, "keys not sorted"
    if '  "a":' not in out:
        return 2, "sorted but not 2-space indent"
    if out.find('"y"') > out.find('"z"'):
        return 2, "outer sorted, nested not"
    return 3, "sorted + 2-space indent (outer + nested)"


# ──────────────────────────────────────────────────────────────────
# task 5 — grep_lines
# ──────────────────────────────────────────────────────────────────

def _t5_prepare(tmp: Path) -> None:
    (tmp / "sample.txt").write_text(
        "alpha one\nbeta two\nalpha three\ngamma four\n",
        encoding="utf-8",
    )


def _t5_invoke(tmp: Path, script: Path) -> subprocess.CompletedProcess:
    return _run(script, ["alpha", str(tmp / "sample.txt")], cwd=tmp)


def _t5_check(p: subprocess.CompletedProcess, tmp: Path) -> Tuple[int, str]:
    if p.returncode not in (0, 1):  # grep convention
        return 0, f"exit {p.returncode}: {p.stderr.decode('utf-8','replace')[:120]}"
    out = p.stdout.decode("utf-8", "replace").strip()
    lines = [l for l in out.splitlines() if l.strip()]
    if len(lines) != 2:
        return 1, f"expected 2 matches, got {len(lines)}"
    if not all("alpha" in l for l in lines):
        return 1, f"non-alpha lines: {lines}"
    if re.search(r"\b1\b", out) and re.search(r"\b3\b", out):
        return 3, "both matches with line numbers"
    return 2, f"matches present, line numbers unclear: {out[:80]}"


# ──────────────────────────────────────────────────────────────────
# Public task registry
# ──────────────────────────────────────────────────────────────────

PUBLIC_TASKS: List[Dict[str, Any]] = [
    {
        "id": "word_count",
        "prompt": (
            "Build a Python script word_count.py that takes a filepath as "
            "its first argument and prints the count of unique words "
            "(case-insensitive, punctuation stripped) to stdout."
        ),
        "expected_files": ["word_count.py"],
        "harness": {
            "primary_file": "word_count.py",
            "prepare": _t1_prepare,
            "invoke": _t1_invoke,
            "check": _t1_check,
        },
    },
    {
        "id": "csv_to_json",
        "prompt": (
            "Build csv_to_json.py — reads a CSV from argv[1], writes JSON "
            "to argv[2]. CSV headers become JSON keys; each row becomes a "
            "JSON object."
        ),
        "expected_files": ["csv_to_json.py"],
        "harness": {
            "primary_file": "csv_to_json.py",
            "prepare": _t2_prepare,
            "invoke": _t2_invoke,
            "check": _t2_check,
        },
    },
    {
        "id": "uniq_sort",
        "prompt": (
            "Build a script uniq_sort.py that reads stdin, outputs unique "
            "lines sorted alphabetically to stdout. No external deps."
        ),
        "expected_files": ["uniq_sort.py"],
        "harness": {
            "primary_file": "uniq_sort.py",
            "prepare": _t3_prepare,
            "invoke": _t3_invoke,
            "check": _t3_check,
        },
    },
    {
        "id": "json_pretty",
        "prompt": (
            "Build json_pretty.py — reads JSON from stdin, writes "
            "pretty-printed JSON (2-space indent, sorted keys) to stdout."
        ),
        "expected_files": ["json_pretty.py"],
        "harness": {
            "primary_file": "json_pretty.py",
            "prepare": _t4_prepare,
            "invoke": _t4_invoke,
            "check": _t4_check,
        },
    },
    {
        "id": "grep_lines",
        "prompt": (
            "Build grep_lines.py — takes a pattern as argv[1] and a file "
            "as argv[2]. Prints lines matching the pattern with their "
            "line numbers (format: 'N:line')."
        ),
        "expected_files": ["grep_lines.py"],
        "harness": {
            "primary_file": "grep_lines.py",
            "prepare": _t5_prepare,
            "invoke": _t5_invoke,
            "check": _t5_check,
        },
    },
]
