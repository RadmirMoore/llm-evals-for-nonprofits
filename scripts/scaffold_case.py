#!/usr/bin/env python3
"""Scaffold a well-formed eval case so growing the suite from a real (anonymized)
transcript is a fill-in-the-blanks job, not a from-scratch one.

By default it prints a case JSON object to stdout for you to paste into a suite
and fill in the TODOs. With `--append <suite.json>` it inserts the case into that
suite's `cases` array (validated before writing, so it never leaves a suite
broken). It also runs the PII check on your input and warns if it looks like it
still contains real contact info.

    # Print a stub to paste:
    python3 scripts/scaffold_case.py --id intake-011 \
        --input "Necesito ayuda con la renta este mes" \
        --category housing --language es

    # Or append straight into a suite:
    python3 scripts/scaffold_case.py --id intake-011 --input "..." \
        --category housing --append evals/intake-classification.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import run_eval  # noqa: E402  (import after sys.path setup is intentional)
from lint_pii import scan_text  # noqa: E402


def build_case(case_id: str, user_input: str, category: str | None = None,
               language: str = "en", empathy: bool = True) -> dict:
    """Return a valid case stub with TODO placeholders for the human to fill in."""
    checks: list[dict] = []
    if category:
        checks.append({"type": "expect_label", "label": category})
    if empathy:
        checks.append({"type": "empathetic_tone"})
    return {
        "id": case_id,
        "input": user_input,
        "language": language,
        "notes": "TODO: why this case exists and what behavior it checks.",
        "checks": checks,
        "responses": {
            "good": "TODO: an example response that SHOULD pass the checks above.",
            "bad": "TODO: an example response that SHOULD fail (evals must catch it).",
        },
    }


def append_to_suite(suite_path: Path, case: dict) -> None:
    """Insert `case` into the suite file, validating the result before writing."""
    if not suite_path.exists():
        raise SystemExit(f"suite not found: {suite_path}")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    existing = {c.get("id") for c in suite.get("cases", [])}
    if case["id"] in existing:
        raise SystemExit(f"case id '{case['id']}' already exists in {suite_path.name}")
    suite.setdefault("cases", []).append(case)
    run_eval.validate_suite(suite, suite_path.name)  # never write a broken suite
    suite_path.write_text(
        json.dumps(suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--id", required=True, help="Unique case id, e.g. intake-011.")
    p.add_argument("--input", required=True, dest="user_input",
                   help="The client message to grade against.")
    p.add_argument("--category", help="Intake category → adds an expect_label check.")
    p.add_argument("--language", default="en", choices=["en", "es", "mixed"],
                   help="Expected reply language. Default: en")
    p.add_argument("--no-empathy", action="store_true",
                   help="Skip the empathetic_tone check in the stub.")
    p.add_argument("--append", metavar="SUITE.json",
                   help="Append the case into this suite file instead of printing.")
    args = p.parse_args(argv)

    for kind, hit in scan_text(args.user_input):
        print(f"warning: input contains a {kind}-like value ({hit!r}); anonymize it "
              f"if it came from a real transcript.", file=sys.stderr)

    case = build_case(args.id, args.user_input, args.category, args.language,
                      empathy=not args.no_empathy)

    if args.append:
        append_to_suite(Path(args.append), case)
        print(f"Appended case '{args.id}' to {args.append}. Fill in the TODOs, then:")
        print("  python3 src/run_eval.py --check && "
              f"python3 src/run_eval.py --responses both --case {args.id} --verbose")
    else:
        print(json.dumps(case, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
