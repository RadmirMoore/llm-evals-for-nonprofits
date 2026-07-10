#!/usr/bin/env python3
"""Flag real-looking contact info in eval cases so cases distilled from real
transcripts get anonymized before they are committed.

It scans the `input` and `notes` of every case for phone numbers, URLs, emails,
and street addresses (reusing the harness's own regexes) and reports what it
finds. This is **advisory**: a case may legitimately quote a contact (e.g. a
hallucination case that asks "is 555-... a real number?"), so real numbers should
be replaced with obviously-fake ones. Use `--strict` to exit non-zero when
anything is found (handy in a pre-submit check).

    python3 scripts/lint_pii.py            # report findings, always exit 0
    python3 scripts/lint_pii.py --strict   # exit 1 if anything looks like PII
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import run_eval  # noqa: E402  (import after sys.path setup is intentional)

# Only user-authored, free-text fields. Example `responses` are deliberately
# excluded: good/bad answers legitimately contain hotline numbers and 211 URLs.
SCANNED_FIELDS = ("input", "notes")


def scan_text(text: str) -> list[tuple[str, str]]:
    """Return (kind, value) pairs for contact-like substrings in `text`."""
    hits: list[tuple[str, str]] = []
    hits += [("phone", m.strip()) for m in run_eval.PHONE_RE.findall(text)]
    hits += [("url", u.strip()) for u in run_eval.URL_RE.findall(text)]
    hits += [("email", e.strip()) for e in run_eval.EMAIL_RE.findall(text)]
    hits += [("address", m.group(0).strip()) for m in run_eval.ADDRESS_RE.finditer(text)]
    return hits


def find_pii(suites: list[dict]) -> list[dict]:
    """Scan the free-text fields of every case across all suites."""
    findings: list[dict] = []
    for suite in suites:
        for case in suite.get("cases", []):
            for field in SCANNED_FIELDS:
                value = case.get(field)
                if not isinstance(value, str):
                    continue
                for kind, hit in scan_text(value):
                    findings.append({
                        "suite": suite.get("eval"),
                        "case": case.get("id"),
                        "field": field,
                        "kind": kind,
                        "value": hit,
                    })
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if any contact-like content is found.")
    args = p.parse_args(argv)

    suites = run_eval.load_evals(None)
    findings = find_pii(suites)
    if not findings:
        print("No contact-like content found in case input/notes.")
        return 0

    print(f"Found {len(findings)} contact-like item(s) in case input/notes:")
    for f in findings:
        print(f"  {f['suite']} / {f['case']} [{f['field']}] {f['kind']}: {f['value']}")
    print("\nIf these came from a real transcript, replace them with obviously-fake "
          "values before committing.")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
