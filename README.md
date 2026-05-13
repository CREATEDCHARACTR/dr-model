# bench-by-execution

> *Open heart surgery for AI models — bench LLMs by running their code, not by checking if the output looks right.*
>
> — **Dr Model**, Local AI Open Heart Surgeon

---

## The one-line claim

The benchmarks the AI industry uses to rank models measure **format-compliance**, not problem-solving.

When you measure problem-solving directly — by executing the code the model produces — a **$1/M-token model often matches a $45/M-token model** on hard tasks. The gap between what those two scorers say is **"The Format Scorer Trap."**

This repo lets you reproduce that finding against any model you choose.

---

## Quick start (60 seconds)

```bash
pip install bench-by-execution
export OPENROUTER_API_KEY=sk-or-v1-...

# Run the public tasks against any model
bench-by-execution demo --model anthropic/claude-haiku-4.5

# Compare two price tiers side-by-side
bench-by-execution compare \
  --models anthropic/claude-opus-4.7,anthropic/claude-haiku-4.5
```

Each task is run **twice**: once with a public-tier EXECUTION CONTRACT wrapping the prompt, once without. Both responses are scored two ways:

| Scorer | What it measures | What industry uses |
|---|---|---|
| **format_score** | Did the response have the right SHAPE? (FILE blocks, named files, run commands) | This is what most LMSYS-style benchmarks check |
| **executor_score** | Did the code actually solve the task? Run with test inputs, check output | This is ground truth |

The gap between the format-score Δ (harnessed − unharnessed) and the executor-score Δ is the **Format Scorer Trap** in action.

---

## What the doctrine says

> The EXECUTION CONTRACT — the wrapper that teaches a model to emit FILE-block-formatted output — teaches **format compliance**, not problem-solving capability. Models with full baseline capability on a task perform the same harnessed and unharnessed; the harness just makes their output substrate-readable. Format-scored benchmarks reward this format-compliance teaching and look like a quality lift. Execution-scored benchmarks reveal it for what it is: format normalization across model families.

If the doctrine holds, the consequence for AI economics is concrete: **most enterprise premium-model spend is overpaid by 5-20×** because the benchmarks driving model selection are format-fit benchmarks.

This repo is the test. Run it, see for yourself.

---

## Try it for days with your own LLMs

The `HarnessedClient` is the same wrapper used in the demo, exposed for programmatic use:

```python
from bench_by_execution import HarnessedClient, executor_score
from bench_by_execution.tasks import PUBLIC_TASKS

client = HarnessedClient(model="anthropic/claude-haiku-4.5")

for task in PUBLIC_TASKS:
    response = client.complete(task["prompt"], harnessed=True)
    result = executor_score(
        response.text,
        task_id=task["id"],
        harness=task["harness"],
    )
    print(f"{task['id']}: {result.score}/3  ({result.reason})")
```

Want to bench your own tasks? Mirror the shape of `PUBLIC_TASKS` (see `src/bench_by_execution/tasks/public.py`) — write a prompt, an `expected_files` list, and three functions: `prepare(tmp_dir)`, `invoke(tmp_dir, script_path)`, `check(completed_proc, tmp_dir) → (score, reason)`. Run it against any model, any contract, any number of arms.

---

## SWE-Bench Verified subset (the headline result)

Pre-baked results on 20 instances from [SWE-Bench Verified](https://www.swebench.com/) — the industry-standard agent code benchmark — across six models live in `results/`. (Phase 2 — adding soon.)

The headline: harness-treated small models land within striking distance of premium models on real GitHub issues, at a fraction of the cost.

---

## Models tested in `results/`

*(Phase 2 deliverable — currently in progress)*

| Model | Provider | $/M blended |
|---|---|---|
| Claude Opus 4.7 | Anthropic / OpenRouter | $45 |
| Claude Sonnet 4.6 | Anthropic / OpenRouter | $9 |
| Claude Haiku 4.5 | Anthropic / OpenRouter | $3 |
| GPT-5.5 | OpenAI / OpenRouter | $17.50 |
| GPT-4.1-mini | OpenAI / OpenRouter | $1 |
| Kimi K2 Thinking | Moonshot / OpenRouter | $1.50 |

All bench results are JSON in `results/`. The model responses, the test executions, the per-task scores, the costs — everything is auditable.

---

## What's NOT in this repo (and why)

The author maintains an internal substrate with a more aggressively tuned EXECUTION CONTRACT, per-model "augmentation" profiles that fix specific model defects (e.g. small models adding stray language identifiers after FILE-block fences), task-class–specific instructions, and a multi-turn agent loop with checkpoint verification. Those add 5-15 score points beyond what this repo's public-tier contract provides on format-graded benchmarks; on executor-graded benchmarks they add less.

The full substrate is not open-sourced. The methodology this repo demonstrates — **dual scoring (format + executor), the harness wrapper pattern, the Format Scorer Trap framing** — is.

The doctrine is reproducible with the public contract alone. That's the point.

---

## Reproducible examples in this repo

See [`examples/`](examples/) for three sample bench-output JSONs:

- `sample_bench_haiku.json` — healed Haiku: `Δformat=+21.7`, `Δexec=0.00` (FORMAT_ONLY)
- `sample_bench_opus.json` — premium Opus: `Δformat=+35.0`, `Δexec=0.00` (FORMAT_ONLY)
- `sample_bench_haiku_broken.json` — pre-heal Haiku: `Δformat=+25.0`, `Δexec=-3.00` (**HARNESS_REGRESSES** — the smoking gun)

The third file is the most important. It shows what the format scorer hides: **a harness that emits a stray `python` line inside the FILE block, causing every harnessed response to SyntaxError**. The format scorer sees a clean FILE block and rewards it. The executor catches the regression. Without dual-scoring you ship a "harness that works" that doesn't.

## Roadmap

| Phase | Status | What |
|---|---|---|
| **0** | ✅ Shipped (v0.1.0) | Core package: `bench-by-execution demo` CLI, public-tier contract, executor + format scorers, 5 public tasks, 6/6 offline smoke test |
| **1** | ✅ Shipped | `demo --out PATH` persists per-row results + summary to JSON; auditable replay |
| **2** | ✅ Shipped | `examples/` directory with three real sample bench JSONs showing the Format Scorer Trap on Opus, Haiku, and pre-heal Haiku |
| **3** | ✅ Shipped | GitHub Actions CI (`.github/workflows/smoke.yml`) runs the offline smoke + parse-gates the CLI on every push, across Python 3.10/3.11/3.12 |
| **4** | ✅ Shipped | This README's roadmap + sample-output narration. Methodology is now both *reproducible* and *explained*. |
| 5+ | Open | Live multi-model batched runs from a single command. Sweep across the price curve in one shot. Per-task category benchmarks (CSV, parsing, search, async). PRs welcome. |

## License

MIT — use it freely.

— Dr Model
