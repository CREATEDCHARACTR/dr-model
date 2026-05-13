"""
bench-by-execution — Bench LLMs by running their code.

The thesis (named "The Format Scorer Trap" in the writeup): the
benchmarks the AI industry uses to rank models measure format-compliance,
not problem-solving. When you measure problem-solving directly — by
executing the code the model produces — a $1/M-token model often matches
a $45/M-token model on hard tasks.

This package lets you reproduce that finding yourself, with whatever
models you choose. The public-tier contract included here is a simplified
demonstration of the pattern. The full doctrine: when the harness teaches
format compliance, format-graded benchmarks lift; execution-graded
benchmarks barely move. The cheap model's underlying capability is
usually enough.

Quick start:
    pip install bench-by-execution
    bench-by-execution demo --model anthropic/claude-haiku-4.5

Programmatic use:
    from bench_by_execution import HarnessedClient, executor_score
    client = HarnessedClient(model="anthropic/claude-haiku-4.5")
    response = client.complete(task)
    score = executor_score(response, task)

— Dr Model
"""

from .harness import HarnessedClient
from .executor import executor_score, ExecutorResult
from .contract import PUBLIC_CONTRACT, contract_version

__version__ = "0.1.0"
__all__ = [
    "HarnessedClient",
    "executor_score",
    "ExecutorResult",
    "PUBLIC_CONTRACT",
    "contract_version",
]
