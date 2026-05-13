# Examples — The Format Scorer Trap, in numbers

Three sample bench-output JSONs reproduced from real runs against
OpenRouter models. Each is what `bench-by-execution demo --model X --out FILE`
produces.

## What the files show

| File | Model | Headline finding |
|---|---|---|
| `sample_bench_haiku.json` | claude-haiku-4.5 | Healed harness: Δexec ≈ 0 (FORMAT_ONLY), Δformat ≈ +14. Harness teaches format, not quality — exactly the doctrine. |
| `sample_bench_opus.json` | claude-opus-4.7 | Premium model: identical exec_mean harnessed vs unharnessed (3.00/3.00). Δformat ≈ +35. The harness is pure format-fit overhead, not a quality multiplier. |
| `sample_bench_haiku_broken.json` | claude-haiku-4.5 (pre-heal) | Surgery target: Δexec = -2.67, Δformat = +14. The harness was **actively hurting** execution quality, hidden by the format scorer. This is what triggered Dr. LLM's first harness surgery. |

## Reproducing

```bash
pip install bench-by-execution
export OPENROUTER_API_KEY=sk-or-v1-...

# Run + save (replaces the corresponding sample file)
bench-by-execution demo \
  --model anthropic/claude-haiku-4.5 \
  --tasks 3 \
  --out examples/my_bench.json

# Read the JSON
python3 -c "
import json, sys
d = json.load(open('examples/my_bench.json'))
print('Δformat:', d['summary']['delta_format'])
print('Δexec:  ', d['summary']['delta_exec'])
"
```

## What the JSON looks like

Top-level shape (matches what a dual-delta reporter expects):

```json
{
  "timestamp_iso": "2026-05-13T...",
  "model": "anthropic/claude-haiku-4.5",
  "n_tasks": 3,
  "results": [
    {
      "task_id": "p1_csv_head",
      "harnessed":   { "exec_score": 3, "format_score": 95, "raw_text": "...", ... },
      "unharnessed": { "exec_score": 3, "format_score": 70, "raw_text": "...", ... }
    },
    ...
  ],
  "summary": {
    "harnessed_exec_mean":   2.83,
    "unharnessed_exec_mean": 3.00,
    "harnessed_format_mean": 96.7,
    "unharnessed_format_mean": 82.5,
    "delta_exec":   -0.17,
    "delta_format": +14.2,
    "total_cost_usd": 0.012
  }
}
```

## The headline

Across these three runs, the consistent pattern:

- **Format-score delta is always positive and double-digit.** The harness reliably teaches the FILE-block convention. 100% of the time.
- **Executor-score delta is in the noise floor on healthy harnesses (±0.2/3.00).** Premium model, mid model, both arms — the harness is format normalization, not quality lift.
- **When delta_exec goes NEGATIVE (haiku_broken sample), the harness is broken.** That's a surgery trigger.

This is what we mean by *"the Format Scorer Trap"*: industry benchmarks largely measure the first row, then attribute it to model quality. Once you measure the second row, the spend math changes.
