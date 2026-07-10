# Contributor scripts

Small, dependency-free helpers for growing the eval suite. Both import the
harness from `src/`, so run them from the repo root.

## `scaffold_case.py` — start a new case from a template

Prints (or appends) a valid case stub with TODO placeholders, so adding a case
distilled from a real interaction is fill-in-the-blanks.

```bash
# Print a stub to paste into a suite:
python3 scripts/scaffold_case.py --id intake-011 \
  --input "Necesito ayuda con la renta" --category housing --language es

# Or append it straight into a suite (validated before writing):
python3 scripts/scaffold_case.py --id intake-011 --input "..." \
  --category housing --append evals/intake-classification.json
```

## `lint_pii.py` — anonymization safety net

Flags real-looking phone numbers, emails, URLs, and addresses in each case's
`input` and `notes`, so PII from a real transcript doesn't get committed. Also
available as `make lint-pii`.

```bash
python3 scripts/lint_pii.py            # report, always exit 0
python3 scripts/lint_pii.py --strict   # exit 1 if anything is found
```

Advisory by design: a case may legitimately quote an obviously-fake number, so
this makes anonymization a conscious choice rather than a gate.
