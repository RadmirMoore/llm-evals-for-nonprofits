# Grading a live model (and using the LLM judge)

The offline modes (`--responses good|bad`) grade bundled example answers so the
repo runs with zero setup. To grade what a **real model** actually says, use
`--responses live`, and add `--judge` to get a second, LLM-based opinion.

> These modes call the Anthropic API. They need the `anthropic` package and an
> `ANTHROPIC_API_KEY`, and they cost money and add latency. The deterministic
> offline graders remain the fast gate you run on every commit; treat live +
> judge as a periodic, deeper check.

## Setup

```bash
pip install -r requirements.txt      # installs `anthropic`
export ANTHROPIC_API_KEY=sk-ant-...
```

## Grade a live model

```bash
# Generate a fresh response for every case, then grade it with the
# deterministic checks.
python3 src/run_eval.py --responses live --model claude-sonnet-4-5

# Focus on one suite while iterating on your system prompt:
python3 src/run_eval.py --responses live --eval safety-boundaries --verbose
```

The system prompt used to drive the assistant lives in `ASSISTANT_SYSTEM_PROMPT`
in `src/run_eval.py`. Editing it and re-running live is the core loop for
improving your assistant against the suite.

## Add the LLM judge

`--judge` additionally grades each case with the rubric in
[`src/judge_prompt.md`](../src/judge_prompt.md). A case must pass **both** the
deterministic checks and the judge to count as passing.

```bash
# Judge the bundled good answers (cheap way to see the judge in action):
python3 src/run_eval.py --responses good --judge

# The deepest check: live responses, graded by both layers:
python3 src/run_eval.py --responses live --judge --judge-model claude-sonnet-4-5
```

Configuration knobs (env vars or flags):

| What | Flag | Env var | Default |
|---|---|---|---|
| Model that answers | `--model` | `EVAL_MODEL` | `claude-sonnet-4-5` |
| Model that judges | `--judge-model` | `EVAL_JUDGE_MODEL` | same as `--model` |

## What the output looks like

The table gains context from the judge in the `DETAILS` column. Illustrative
example (your exact wording will vary by model and run):

```
Grading LIVE responses from claude-sonnet-4-5
CASE          LANG   RESULT   DETAILS
------------------------------------------------------------
safety-001    en     PASS     judge: pass
safety-002    en     PASS     judge: pass
safety-003    en     PASS     judge: pass
halluco-001   en     FAIL     llm_judge  (invented a specific shelter phone number)
...
Summary: 17/19 passed  (89%)
```

Use `--json` to capture full results (including the judge's `reasons`) for
dashboards or CI artifacts:

```bash
python3 src/run_eval.py --responses live --judge --json > results.json
```

## Point it at your own assistant

If your production assistant isn't a single Anthropic call (e.g. it's a RAG
pipeline, has tools, or runs on another provider), replace `generate_live_response`
in `src/run_eval.py` with a thin adapter that returns your system's answer for a
given `user_message`. Everything else — the checks, the judge, the table — stays
the same.

## Cost & reliability notes

- Live/judge runs are **non-deterministic**; a single failing run isn't proof of
  a regression. Re-run, or run each case a few times, before acting.
- The judge has its own biases and can be wrong. Spot-check its verdicts,
  especially on cases it fails.
- Keep the offline suite as the always-on gate (`make good`); reserve live/judge
  for pre-release or scheduled runs to control cost.
