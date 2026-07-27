# Model Regression Detection System

# Model Regression Detection System

A CI/CD pipeline that catches LLM output quality regressions before they
reach production — automatically, on every pull request that changes a
prompt, with zero manual review required to catch the obvious cases.

**Status:** Complete (Phases 1-6). Fully working, evidenced end-to-end.

## The result, up front

On a real (not synthetic) test: a deliberately weakened prompt was pushed
through this pipeline. It was caught, scored, and blocked automatically.

```
Baseline:  v1 (100% category accuracy, 4.78/5 avg summary quality)
Candidate: v2 (83% category accuracy, 4.72/5 avg summary quality)

Severity: CRITICAL
Regressed cases (3): account-001, general-002, general-003
```

The pull request containing this change was automatically blocked by CI,
with the full diff posted as a PR comment — no human had to notice the
regression by reading output samples.

## The problem this solves

Most teams shipping LLM-powered features change prompts the way they'd
tweak a config value: push it, watch for complaints. There's no equivalent
of a unit test suite for "does this prompt still produce correct outputs?"
This project builds that missing piece: CI for prompt/model behavior, not
just code correctness.

## Architecture

```
prompts/                Versioned prompt configs (the "code" under test)
eval_data/               Hand-labeled golden dataset (ground truth, 18 cases)
src/
  classifier.py          The LLM feature under test (email triage classifier)
  golden_dataset.py       Loads + validates the golden dataset
  judge.py                 LLM-as-judge summary quality scoring
  eval_runner.py            Async test runner (concurrent API calls)
  diff_runs.py               Run-to-run diff logic + severity thresholds
  report_generator.py         HTML diff report generation (Jinja2)
  discord_alert.py             Discord webhook alerting
  drift_detector.py             Rolling-window slow-drift detection
docs/decisions/           Architecture Decision Records (why, not just what)
reports/runs/              Real eval run history (raw evidence, not mocked)
.github/workflows/eval.yml  CI: runs the eval suite on every prompt change,
                              comments results on the PR, blocks merge on
                              CRITICAL severity
```

## How it works, end to end

1. A prompt change is proposed (new `.yaml` file under `prompts/`)
2. CI runs the full 18-case golden dataset against both the baseline and
   candidate prompt, concurrently (async, ~5 requests in flight at once)
3. Every response is scored two ways: category correctness (exact match)
   and summary quality (LLM-as-judge against a written rubric)
4. The two runs are diffed: pass-rate delta, per-case regressions/
   improvements, and a severity level (`none` / `warning` / `critical`)
   based on configurable thresholds (3% / 8%)
5. Results are posted as a PR comment and an HTML report; a Discord alert
   fires with the same summary
6. If severity is `CRITICAL`, the CI check fails — blocking merge until a
   human reviews it
7. Independently, a drift detector watches the rolling average across the
   last N runs, catching slow multi-run decline that no single diff
   would flag

## Key design decisions

Full reasoning in [`docs/decisions/`](docs/decisions/). Highlights:

- **[ADR 001](docs/decisions/001-structured-output-via-tool-use.md)** —
  structured output via forced tool-use, not prompted JSON, eliminating an
  entire class of malformed-output bugs.
- **[ADR 002](docs/decisions/002-versioned-prompts-as-yaml.md)** — prompts
  are versioned YAML files, not inline strings, so a prompt change is a
  data change, not a code change.
- **[ADR 003](docs/decisions/003-hand-written-golden-dataset.md)** — the
  golden dataset is hand-labeled by a human, never LLM-generated, so the
  eval suite can catch model blind spots instead of confirming the model
  agrees with itself.
- **[ADR 004](docs/decisions/004-llm-as-judge-summary-scoring.md)** —
  summary quality is scored via LLM-as-judge with an explicit written
  rubric (content/meaning equivalence, not wording similarity).
- **[ADR 005](docs/decisions/005-validated-regression-detection.md)** —
  the diff/severity system was validated against a real, deliberately
  induced regression, not just unit-tested in isolation.

## Setup

```bash
git clone https://github.com/CODEWITHNDAHIRO/LLM-regression-detector.git
cd LLM-regression-detector
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY (and DISCORD_WEBHOOK_URL, optional)
python src/eval_runner.py v1      # run the golden dataset against a prompt version
python src/diff_runs.py v1 v2     # compare two runs
python src/report_generator.py v1 v2   # generate an HTML report
```

To enable the CI check on your own fork: add `ANTHROPIC_API_KEY` as a
repository secret (Settings → Secrets and variables → Actions), then open
a PR that touches `prompts/`.

## What I'd extend next

- Golden dataset currently sits at 18 cases; the real-world version of this
  (Project 13 in the broader build series) would mine production logs for
  failure cases automatically rather than relying solely on hand-curation.
- Drift detection currently only tracks category pass rate; extending the
  rolling window to also track summary score trend would catch a second
  class of slow decline.
- No cost tracking yet — the LLM-as-judge step roughly doubles API spend
  per eval run, which is fine at 18 cases but would need budgeting at scale.

## Why this project

Built to demonstrate the evaluation/operations side of AI engineering —
the part of the job that's mostly invisible in typical "call an API, deploy
a chatbot" portfolio projects, but is what production AI teams actually
spend most of their time on. Full build log and reasoning throughout in
`docs/decisions/`.