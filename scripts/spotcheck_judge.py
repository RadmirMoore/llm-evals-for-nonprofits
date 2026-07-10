#!/usr/bin/env python3
"""Human-in-the-loop spot-check of the LLM judge's verdicts.

The judge can be wrong or gamed, so before trusting it you should sample its
verdicts and have a human agree or disagree. This reads a results file produced
by a judged run, samples some cases, shows you what the judge saw and decided,
and records whether you agree — then reports how often the judge matched you.

    # 1. Produce judged results (offline example, or use --responses live):
    python3 src/run_eval.py --responses good --judge --json > results.json

    # 2. Spot-check them:
    python3 scripts/spotcheck_judge.py results.json --sample 8 --out labels.jsonl

The results file must come from a `--judge --json` run (each row needs a
`judge` verdict and the graded `response`).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Callable

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import run_eval  # noqa: E402  (import after sys.path setup is intentional)


def judged_rows(results: list[dict]) -> list[dict]:
    """Rows that actually carry a judge verdict."""
    return [r for r in results if isinstance(r.get("judge"), dict)]


def sample_rows(rows: list[dict], n: int, seed: int) -> list[dict]:
    """A reproducible sample of up to `n` rows (all of them if n <= 0 or >= len)."""
    if n <= 0 or n >= len(rows):
        return list(rows)
    return random.Random(seed).sample(rows, n)


def judge_passed(row: dict) -> bool:
    return row.get("judge", {}).get("overall") == "pass"


def resolve_inputs() -> dict[str, str]:
    """Map case id -> client message, so we can show what the judge was judging."""
    inputs: dict[str, str] = {}
    for suite in run_eval.load_evals(None):
        for case in suite.get("cases", []):
            inputs[case.get("id")] = case.get("input", "")
    return inputs


def summarize(labels: list[dict]) -> dict:
    """Agreement stats over the human-labeled (non-skipped) rows."""
    scored = [l for l in labels if l["human_agrees"] is not None]
    agreed = sum(1 for l in scored if l["human_agrees"])
    # Of the ones the human disagreed on, how did the judge err?
    false_pass = sum(1 for l in scored
                     if not l["human_agrees"] and l["judge_passed"])
    false_fail = sum(1 for l in scored
                     if not l["human_agrees"] and not l["judge_passed"])
    return {
        "reviewed": len(scored),
        "agreed": agreed,
        "agreement_rate": agreed / len(scored) if scored else 0.0,
        "judge_false_pass": false_pass,
        "judge_false_fail": false_fail,
    }


def run_spotcheck(rows: list[dict], inputs: dict[str, str],
                  ask: Callable[[str], str]) -> list[dict]:
    """Drive the review loop. `ask(prompt)->str` is injected so this is testable
    without real stdin. Returns one label record per row."""
    labels: list[dict] = []
    for i, row in enumerate(rows, 1):
        verdict = "PASS" if judge_passed(row) else "FAIL"
        reasons = row.get("judge", {}).get("reasons", "")
        print(f"\n[{i}/{len(rows)}] {row.get('eval')} / {row.get('case')} "
              f"({row.get('source')})")
        print(f"  client:   {inputs.get(row.get('case'), '(input unavailable)')}")
        print(f"  response: {_oneline(row.get('response', ''))}")
        print(f"  judge:    {verdict} — {reasons}")

        answer = ask("  Do you agree with the judge? [y]es / [n]o / [s]kip: ").strip().lower()
        if answer.startswith("y"):
            agrees: bool | None = True
        elif answer.startswith("n"):
            agrees = False
        else:
            agrees = None  # skipped
        note = ask("  Note (optional): ").strip() if agrees is not None else ""

        labels.append({
            "case": row.get("case"),
            "source": row.get("source"),
            "judge_passed": judge_passed(row),
            "human_agrees": agrees,
            "note": note,
        })
    return labels


def _oneline(text: str, limit: int = 300) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("results", help="Path to a `--judge --json` results file.")
    p.add_argument("--sample", type=int, default=10,
                   help="How many judged cases to review (<=0 means all). Default: 10")
    p.add_argument("--seed", type=int, default=0, help="Sampling seed. Default: 0")
    p.add_argument("--out", help="Write per-case labels here as JSONL.")
    args = p.parse_args(argv)

    try:
        results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"could not read results file: {e}")

    rows = judged_rows(results)
    if not rows:
        sys.exit("No judge verdicts in that file. Re-run with `--judge --json`.")

    chosen = sample_rows(rows, args.sample, args.seed)
    print(f"Spot-checking {len(chosen)} of {len(rows)} judged case(s).")
    labels = run_spotcheck(chosen, resolve_inputs(), input)

    stats = summarize(labels)
    print(f"\nJudge agreement: {stats['agreed']}/{stats['reviewed']} "
          f"({stats['agreement_rate']:.0%}) over reviewed cases.")
    if stats["judge_false_pass"] or stats["judge_false_fail"]:
        print(f"  Disagreements — judge too lenient: {stats['judge_false_pass']}, "
              f"too strict: {stats['judge_false_fail']}.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            for label in labels:
                fh.write(json.dumps(label, ensure_ascii=False) + "\n")
        print(f"Wrote {len(labels)} label(s) to {args.out}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
