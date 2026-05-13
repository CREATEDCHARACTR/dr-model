"""Smoke tests — package imports + scorer pipeline works on a mock response.

No network calls; runs offline; validates the executor scorer can
correctly judge a known-good and known-broken submission.
"""

import sys
from pathlib import Path

# Make the package importable without `pip install -e .`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_imports() -> None:
    from bench_by_execution import HarnessedClient, executor_score, PUBLIC_CONTRACT, contract_version
    from bench_by_execution.executor import format_score, extract_file_blocks
    from bench_by_execution.tasks import PUBLIC_TASKS
    assert len(PUBLIC_CONTRACT) > 100, "public contract should be non-trivial"
    assert contract_version() == "public-v1.0"
    assert len(PUBLIC_TASKS) == 5
    print("  imports + constants OK")


def test_extractor() -> None:
    from bench_by_execution.executor import extract_file_blocks
    # Well-formed FILE block
    txt = "Here:\n```FILE: word_count.py\nimport sys\nprint(len(set(open(sys.argv[1]).read().split())))\n```"
    files = extract_file_blocks(txt)
    assert "word_count.py" in files
    assert "import sys" in files["word_count.py"]
    # FILE block with stray language identifier (the bug we tolerate)
    txt2 = "```FILE: foo.py\npython\nimport sys\n```"
    files2 = extract_file_blocks(txt2)
    assert "foo.py" in files2
    assert files2["foo.py"].startswith("import sys"), \
        f"stray language identifier not stripped: {files2['foo.py']!r}"
    print("  extractor OK (handles stray language id)")


def test_format_scorer() -> None:
    from bench_by_execution.executor import format_score
    response = "```FILE: word_count.py\nimport sys\nprint(42)\n```\n\nRun: `python3 word_count.py file.txt`"
    score = format_score(response, expected_files=["word_count.py"])
    assert score["score_pct"] >= 80, f"expected high format score, got {score}"
    assert "word_count.py" in score["files_found"]
    print(f"  format scorer OK (well-formed response → {score['score_pct']}/100)")


def test_executor_on_known_good() -> None:
    """End-to-end: a known-correct word_count.py should score 3."""
    from bench_by_execution.executor import executor_score
    from bench_by_execution.tasks import PUBLIC_TASKS

    word_count_task = next(t for t in PUBLIC_TASKS if t["id"] == "word_count")
    # A correct word_count.py implementation
    response = """```FILE: word_count.py
#!/usr/bin/env python3
import sys, string
text = open(sys.argv[1]).read().lower()
tokens = [t.strip(string.punctuation) for t in text.split()]
print(len({t for t in tokens if t}))
```"""
    result = executor_score(
        response,
        task_id=word_count_task["id"],
        harness=word_count_task["harness"],
    )
    assert result.score == 3, f"expected 3, got {result.score}: {result.reason}"
    print(f"  executor OK (known-good word_count.py → {result.score}/3)")


def test_executor_on_broken() -> None:
    """A syntactically broken file should score 0."""
    from bench_by_execution.executor import executor_score
    from bench_by_execution.tasks import PUBLIC_TASKS

    word_count_task = next(t for t in PUBLIC_TASKS if t["id"] == "word_count")
    response = "```FILE: word_count.py\nthis is not python\n```"
    result = executor_score(
        response,
        task_id=word_count_task["id"],
        harness=word_count_task["harness"],
    )
    assert result.score == 0, f"expected 0, got {result.score}: {result.reason}"
    print(f"  executor OK (broken word_count.py → {result.score}/3)")


def test_executor_on_missing_file() -> None:
    """Response with the wrong filename should score 0."""
    from bench_by_execution.executor import executor_score
    from bench_by_execution.tasks import PUBLIC_TASKS

    word_count_task = next(t for t in PUBLIC_TASKS if t["id"] == "word_count")
    response = "```FILE: wc.py\nprint(7)\n```"  # wrong name
    result = executor_score(
        response,
        task_id=word_count_task["id"],
        harness=word_count_task["harness"],
    )
    assert result.score == 0, f"expected 0 (wrong filename), got {result.score}"
    print(f"  executor OK (wrong filename → {result.score}/3)")


if __name__ == "__main__":
    test_imports()
    test_extractor()
    test_format_scorer()
    test_executor_on_known_good()
    test_executor_on_broken()
    test_executor_on_missing_file()
    print("\nALL 6 SMOKE TESTS PASSED")
