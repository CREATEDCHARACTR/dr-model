"""
The public-tier EXECUTION CONTRACT.

This is a simplified demonstration of the harness pattern that exposes
"The Format Scorer Trap" — the hidden assumption in industry-standard
benchmarks. The full pattern (with per-model augmentations, anti-examples,
naming-discipline rules, and reasoning-budget instructions) is months of
tuning and is NOT shipped here.

This simplified contract is enough to reproduce the main finding:
  - Models told to ship FILE blocks score higher on format-graded benchmarks
  - When you ALSO measure with an executor scorer (does the code run?),
    the format-score lift is exposed as format-fit, not capability lift
  - Cheap models match expensive models on real problem-solving

If you want to test the doctrine: run this contract against any LLM,
score with `executor_score`, and compare format-score vs executor-score
deltas. They diverge wildly. That's the trap.

— Dr Model (Local AI Open Heart Surgeon)
"""

# Public-tier EXECUTION CONTRACT v1.0. Open-source, MIT.
PUBLIC_CONTRACT = """\
When you write code in response to this task, follow this format:

For each file your solution requires, emit a fenced code block with this
exact opening line:

    ```FILE: <filename>
    <file body — the literal contents of the file>
    ```

Use one block per file. The filename in the fence is the only place the
filename appears — do NOT add a language identifier line (no `python`,
no `bash`) after the fence opening. The reader infers the language from
the filename extension.

If the task requires a way to run your code, include a `demo.sh` file as
one of your blocks, OR include a one-line invocation in your prose
explaining how to run it.

What happens to your output:
  1. A parser extracts each FILE block by its filename
  2. The contents are written to a temporary directory
  3. The code is executed against the test inputs defined for this task
  4. The output is compared to the expected behavior

Your score depends on whether the code runs and produces the right
output — not on how well you explain your approach. Be concise in any
explanatory prose; let the code carry the answer.
"""


def contract_version() -> str:
    """Return the version + checksum-like identifier for this contract.

    Useful when comparing bench results across runs: pinned contract
    means results are comparable. Different contract text → different
    measurement.
    """
    return "public-v1.0"


# Why this is simplified vs. the full TFB substrate contract:
#
# The internal TFB substrate uses a more aggressive contract with:
#   - Explicit per-task-class augmentations (byte_exact_compliance,
#     short_tactical_reply, reasoning_planning, open_synthesis, default)
#   - Per-model "anti-example" demonstrations of common failure modes
#     (e.g. Haiku's FILE-block language-identifier bug)
#   - Naming-discipline rules ("use spec nouns as filenames")
#   - Reasoning-budget hints for reasoning models
#   - "Evidence of completion" gates and "BLOCKED" escape hatch
#
# Those refinements add ~5-15 score points on format-scored benchmarks
# beyond what the public-tier contract above provides. They're months
# of empirical tuning. The doctrine they validate (format-fit ≠ quality)
# is reproducible with the public contract alone — that's the point.
#
# If you build your own augmentations on top of this base, the
# methodology composes: keep the executor scorer as your ground truth,
# layer profile augmentations as residual-variance heals, and the
# pattern generalizes to any model family.
