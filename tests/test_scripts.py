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


# --------------------------------------------------------------------------- #
# spotcheck_judge
# --------------------------------------------------------------------------- #
import spotcheck_judge  # noqa: E402


def _row(case, overall, response="resp", source="good"):
    return {"eval": "safety-boundaries", "case": case, "source": source,
            "response": response, "judge": {"overall": overall, "reasons": "why"}}


def test_judged_rows_filters_out_unjudged():
    rows = [_row("a", "pass"), {"case": "b", "judge": None}, {"case": "c"}]
    assert [r["case"] for r in spotcheck_judge.judged_rows(rows)] == ["a"]


def test_sample_rows_reproducible_and_bounds():
    rows = [_row(str(i), "pass") for i in range(20)]
    a = spotcheck_judge.sample_rows(rows, 5, seed=1)
    b = spotcheck_judge.sample_rows(rows, 5, seed=1)
    assert [r["case"] for r in a] == [r["case"] for r in b]  # deterministic
    assert len(a) == 5
    assert len(spotcheck_judge.sample_rows(rows, 0, seed=1)) == 20   # <=0 => all
    assert len(spotcheck_judge.sample_rows(rows, 99, seed=1)) == 20  # >=len => all


def test_run_spotcheck_records_labels_via_injected_ask():
    rows = [_row("a", "pass"), _row("b", "fail"), _row("c", "pass")]
    answers = iter(["y", "note-1", "n", "note-2", "s"])  # agree, disagree, skip
    labels = spotcheck_judge.run_spotcheck(rows, {"a": "hi"}, lambda _p: next(answers))
    assert [l["human_agrees"] for l in labels] == [True, False, None]
    assert labels[0]["note"] == "note-1"
    assert labels[2]["note"] == ""  # skipped rows aren't prompted for a note


def test_summarize_counts_agreement_and_error_direction():
    labels = [
        {"human_agrees": True, "judge_passed": True},
        {"human_agrees": False, "judge_passed": True},   # judge too lenient
        {"human_agrees": False, "judge_passed": False},  # judge too strict
        {"human_agrees": None, "judge_passed": True},    # skipped, ignored
    ]
    s = spotcheck_judge.summarize(labels)
    assert s["reviewed"] == 3 and s["agreed"] == 1
    assert s["judge_false_pass"] == 1 and s["judge_false_fail"] == 1
