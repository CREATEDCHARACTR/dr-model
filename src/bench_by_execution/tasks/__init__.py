"""
Public task pool — 5 reproducible CLI tasks with executor harnesses.

These are standard CLI exercises anyone could have designed. The point
isn't task novelty; it's the SCORING METHODOLOGY. Run any LLM against
these with two scorers (format + executor) and watch the gap.

The harder, designed-to-trip task pool that TFB uses internally is NOT
shipped here — those tasks are months of empirical work selecting
adversarial inputs that expose model-specific failure modes. The
public tasks below are simpler and well-suited for demos; the doctrine
generalizes regardless.

To add your own tasks, mirror the shape:
    {
        "id": str,
        "prompt": str (the user message — the LLM sees this),
        "expected_files": List[str],
        "harness": {
            "primary_file": str,
            "prepare": Callable[[Path], None],
            "invoke": Callable[[Path, Path], CompletedProcess],
            "check":  Callable[[CompletedProcess, Path], Tuple[int, str]],
        }
    }

— Dr Model
"""

from .public import PUBLIC_TASKS

__all__ = ["PUBLIC_TASKS"]
