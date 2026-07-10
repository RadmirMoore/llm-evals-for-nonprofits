"""Tests for the contributor tooling in scripts/ (PII linter + case scaffolder).

Both `src/` and `scripts/` are added to sys.path so the modules import.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_eval        # noqa: E402
import lint_pii        # noqa: E402
import scaffold_case   # noqa: E402


# --------------------------------------------------------------------------- #
# lint_pii
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text, kind", [
    ("call 415-555-0199 please", "phone"),
    ("email me at a@b.org", "email"),
    ("see https://example.com/x", "url"),
    ("123 Main Street, apt 4", "address"),
])
def test_scan_text_flags_contacts(text, kind):
    kinds = {k for k, _ in lint_pii.scan_text(text)}
    assert kind in kinds


def test_scan_text_clean():
    assert lint_pii.scan_text("I need help paying my rent this month") == []


def test_bundled_cases_have_no_pii_in_input_or_notes():
    # Keeps the shipped suite honest: nothing that looks like a real contact.
    assert lint_pii.find_pii(run_eval.load_evals(None)) == []


def test_find_pii_reports_field_and_case():
    suites = [{"eval": "s", "cases": [
        {"id": "c1", "input": "reach me at 212-555-0000", "notes": "clean"},
    ]}]
    findings = lint_pii.find_pii(suites)
    assert len(findings) == 1
    assert findings[0]["case"] == "c1" and findings[0]["field"] == "input"


# --------------------------------------------------------------------------- #
# scaffold_case
# --------------------------------------------------------------------------- #
def test_build_case_is_valid_and_has_placeholders():
    case = scaffold_case.build_case("intake-011", "hola", category="housing",
                                    language="es")
    suite = {"eval": "demo", "cases": [case]}
    run_eval.validate_suite(suite, "demo")  # must not raise
    assert case["language"] == "es"
    assert any(c["type"] == "expect_label" and c["label"] == "housing"
               for c in case["checks"])
    assert any(c["type"] == "empathetic_tone" for c in case["checks"])
    assert "TODO" in case["responses"]["good"]


def test_build_case_no_category_no_empathy():
    case = scaffold_case.build_case("x-1", "hi", category=None, empathy=False)
    assert case["checks"] == []


def test_append_to_suite_and_reject_duplicate(tmp_path):
    suite_path = tmp_path / "s.json"
    suite_path.write_text(json.dumps(
        {"eval": "s", "cases": [{"id": "a", "input": "x"}]}), encoding="utf-8")

    scaffold_case.append_to_suite(suite_path, scaffold_case.build_case("b", "hi"))
    reloaded = json.loads(suite_path.read_text(encoding="utf-8"))
    assert {c["id"] for c in reloaded["cases"]} == {"a", "b"}

    with pytest.raises(SystemExit):
        scaffold_case.append_to_suite(suite_path, scaffold_case.build_case("b", "hi"))
