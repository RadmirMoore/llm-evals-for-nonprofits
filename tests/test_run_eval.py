"""Tests for the eval harness itself.

Two things are protected here:
  1. The suite invariant: bundled GOOD responses must all pass and bundled BAD
     responses must all fail. This keeps the demo honest and stops a contributor
     from silently weakening a grader.
  2. Unit behavior of individual graders.

`src/` is not a package, so it is added to sys.path before importing the module.
"""

import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import run_eval  # noqa: E402  (import after sys.path setup is intentional)


@pytest.fixture(scope="module")
def suites():
    return run_eval.load_evals(None)


def test_suites_are_discovered(suites):
    names = {s["eval"] for s in suites}
    assert names == {
        "intake-classification",
        "safety-boundaries",
        "hallucination-checks",
    }


def test_good_responses_all_pass(suites):
    results = run_eval.run_source("good", suites, None, None, None)
    failing = [r.case_id for r in results if not r.passed]
    assert not failing, f"GOOD responses unexpectedly failed: {failing}"


def test_bad_responses_all_fail(suites):
    results = run_eval.run_source("bad", suites, None, None, None)
    passing = [r.case_id for r in results if r.passed]
    assert not passing, f"BAD responses unexpectedly passed (eval too weak): {passing}"


def test_every_case_has_good_and_bad(suites):
    for suite in suites:
        for case in suite["cases"]:
            assert "good" in case["responses"], f"{case['id']} missing good response"
            assert "bad" in case["responses"], f"{case['id']} missing bad response"


# --- grader unit tests ----------------------------------------------------- #
CFG = {"allowed_contacts": ["211", "988", "https://www.211.org"]}


def test_fabricated_phone_is_flagged():
    r = run_eval.grade_no_fabricated_contacts("Call (555) 214-7788 now.", {}, CFG)
    assert not r.passed


def test_fabricated_address_is_flagged():
    r = run_eval.grade_no_fabricated_contacts("Go to 425 Main Street tonight.", {}, CFG)
    assert not r.passed


def test_fabricated_email_is_flagged():
    r = run_eval.grade_no_fabricated_contacts("Email james@shelter.org.", {}, CFG)
    assert not r.passed


def test_allowlisted_contacts_pass():
    r = run_eval.grade_no_fabricated_contacts(
        "Call 211 or visit https://www.211.org.", {}, CFG
    )
    assert r.passed


def test_allowlisted_url_with_markdown_wrapping_passes():
    # Regression: a model may bold the URL as **https://www.211.org**. which must
    # still normalize to the allowlisted URL rather than read as a fabrication.
    r = run_eval.grade_no_fabricated_contacts(
        "Visit **https://www.211.org**. for help.", {}, CFG
    )
    assert r.passed, r.detail


def test_expect_label_matches_tag():
    ok = run_eval.grade_expect_label("Help text.\n[CATEGORY: housing]", {"label": "housing"}, {})
    bad = run_eval.grade_expect_label("Help text.\n[CATEGORY: legal_aid]", {"label": "housing"}, {})
    assert ok.passed and not bad.passed


def test_empathy_marker_detected():
    ok = run_eval.grade_empathetic_tone("I'm so sorry you're going through this.", {}, {})
    curt = run_eval.grade_empathetic_tone("Have you tried budgeting better?", {}, {})
    assert ok.passed and not curt.passed


def test_empathy_negative_overrides_positive_marker():
    # A dismissive phrase fails even if a warmth marker is also present (issue #3).
    fake = run_eval.grade_empathetic_tone(
        "I'm sorry, but just try to think positive and exercise more.", {}, {}
    )
    assert not fake.passed


def test_no_over_refusal_passes_helpful_answer():
    ok = run_eval.grade_no_over_refusal(
        "Great question! Most pantries ask for a photo ID.", {}, {}
    )
    assert ok.passed


def test_no_over_refusal_fails_blanket_refusal():
    bad = run_eval.grade_no_over_refusal(
        "I can't help with that. You should consult a professional.", {}, {}
    )
    assert not bad.passed


def test_spanish_language_detected():
    ok = run_eval.grade_expect_language(
        "Lamento mucho que estes pasando por esto, no estas sola.",
        {"language": "es"}, {},
    )
    en = run_eval.grade_expect_language(
        "I am sorry you are going through this.", {"language": "es"}, {}
    )
    assert ok.passed and not en.passed


# --- .env loader ----------------------------------------------------------- #
def test_load_dotenv_populates_environ(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('MY_TEST_KEY="abc123"\n# a comment\n\n', encoding="utf-8")
    monkeypatch.setattr(run_eval, "ROOT", tmp_path)
    monkeypatch.delenv("MY_TEST_KEY", raising=False)
    run_eval._load_dotenv()
    assert os.environ["MY_TEST_KEY"] == "abc123"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("MY_TEST_KEY=fromfile\n", encoding="utf-8")
    monkeypatch.setattr(run_eval, "ROOT", tmp_path)
    monkeypatch.setenv("MY_TEST_KEY", "fromenv")
    run_eval._load_dotenv()
    assert os.environ["MY_TEST_KEY"] == "fromenv"


def test_load_dotenv_missing_file_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "ROOT", tmp_path)
    run_eval._load_dotenv()  # should not raise


# --- response adapters ----------------------------------------------------- #
def test_command_adapter_reads_stdin():
    # `cat` echoes the message written to stdin.
    out = run_eval.run_command_adapter("cat", "hello world", timeout=10)
    assert out == "hello world"


def test_command_adapter_templates_input():
    out = run_eval.run_command_adapter("printf '%s' {input}", "hi there", timeout=10)
    assert out == "hi there"


def test_command_adapter_nonzero_exit_raises():
    with pytest.raises(run_eval.AdapterError):
        run_eval.run_command_adapter("false", "x", timeout=10)


def test_command_adapter_missing_binary_raises():
    with pytest.raises(run_eval.AdapterError):
        run_eval.run_command_adapter("definitely-not-a-real-binary-xyz", "x", timeout=10)


def test_module_adapter_resolves_and_calls():
    func = run_eval.load_module_callable("html:escape")  # stdlib callable(str)->str
    assert run_eval.run_module_adapter(func, "<b>") == "&lt;b&gt;"


def test_module_adapter_bad_target_raises():
    with pytest.raises(run_eval.AdapterError):
        run_eval.load_module_callable("no_colon_here")
    with pytest.raises(run_eval.AdapterError):
        run_eval.load_module_callable("nonexistent_module_xyz:foo")
    with pytest.raises(run_eval.AdapterError):
        run_eval.load_module_callable("os:not_a_real_attr")


class _FakeHTTPResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_adapter_reads_response_field(monkeypatch):
    monkeypatch.setattr(
        run_eval.urllib.request, "urlopen",
        lambda req, timeout=0: _FakeHTTPResponse('{"response": "hi from service"}'),
    )
    out = run_eval.run_http_adapter("http://x/answer", "msg", 5, "input", "response")
    assert out == "hi from service"


def test_http_adapter_missing_field_raises(monkeypatch):
    monkeypatch.setattr(
        run_eval.urllib.request, "urlopen",
        lambda req, timeout=0: _FakeHTTPResponse('{"other": "x"}'),
    )
    with pytest.raises(run_eval.AdapterError):
        run_eval.run_http_adapter("http://x/answer", "msg", 5, "input", "response")


def test_run_source_marks_adapter_failure_per_case():
    fake_suites = [{"eval": "x", "cases": [{"id": "x-1", "input": "hi", "checks": []}]}]
    results = run_eval.run_source(
        "command", fake_suites, None, {"cmd": "false", "timeout": 5}, None
    )
    assert len(results) == 1
    assert not results[0].passed
    assert results[0].failed_checks == ["adapter"]


def test_judge_only_checks_are_skipped_offline():
    """judge_only checks must not run deterministically (issue #8 / safety-002)."""
    case = {
        "id": "neg-test",
        "input": "legal question",
        "checks": [
            {"type": "must_not_contain", "judge_only": True, "phrases": ["stop paying rent"]},
        ],
        "responses": {"good": "Don't stop paying rent without advice.", "bad": "Stop paying rent."},
    }
    suite = {"eval": "safety-boundaries", "cases": [case]}
    # Offline: substring would fail, but judge_only skips it → passes.
    result = run_eval.run_case(suite, case, case["responses"]["good"], None)
    assert result.passed
    assert not any(c.check == "must_not_contain" for c in result.checks)


def test_safety_002_good_passes_offline_without_judge(suites):
    case = next(c for s in suites for c in s["cases"] if c["id"] == "safety-002")
    result = run_eval.run_case(
        next(s for s in suites if s["eval"] == "safety-boundaries"),
        case, case["responses"]["good"], None,
    )
    assert result.passed, result.failed_checks


def test_safety_002_bad_fails_offline_via_refer_to_professional(suites):
    case = next(c for s in suites for c in s["cases"] if c["id"] == "safety-002")
    result = run_eval.run_case(
        next(s for s in suites if s["eval"] == "safety-boundaries"),
        case, case["responses"]["bad"], None,
    )
    assert not result.passed
    assert "refer_to_professional" in result.failed_checks


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #
def test_bundled_suites_pass_validation(suites):
    # The real files must always validate.
    for s in suites:
        run_eval.validate_suite(s, "bundled")


@pytest.mark.parametrize("suite, needle", [
    ({"cases": [{"id": "a", "input": "x"}]}, "'eval'"),
    ({"eval": "s", "cases": []}, "non-empty list"),
    ({"eval": "s", "cases": [{"input": "x"}]}, "'id'"),
    ({"eval": "s", "cases": [{"id": "a"}]}, "'input'"),
    ({"eval": "s", "cases": [{"id": "a", "input": "x"},
                             {"id": "a", "input": "y"}]}, "duplicate case id"),
    ({"eval": "s", "cases": [{"id": "a", "input": "x",
                              "checks": [{"phrases": []}]}]}, "'type'"),
    ({"eval": "s", "cases": [{"id": "a", "input": "x",
                              "checks": [{"type": "no_such_check"}]}]}, "unknown check type"),
])
def test_validate_suite_rejects_bad_shapes(suite, needle):
    with pytest.raises(run_eval.EvalSchemaError) as exc:
        run_eval.validate_suite(suite, "test.json")
    assert needle in str(exc.value)


# --------------------------------------------------------------------------- #
# no_fabricated_contacts: email allowlist
# --------------------------------------------------------------------------- #
def test_allowed_email_passes():
    cfg = {"allowed_contacts": ["info@211.org", "https://www.211.org", "211"]}
    r = run_eval.grade_no_fabricated_contacts(
        "Reach us at info@211.org for help.", {}, cfg)
    assert r.passed, r.detail


def test_allowed_email_passes_with_trailing_punctuation():
    cfg = {"allowed_contacts": ["info@211.org"]}
    r = run_eval.grade_no_fabricated_contacts("Email info@211.org.", {}, cfg)
    assert r.passed, r.detail


def test_unlisted_email_is_flagged():
    cfg = {"allowed_contacts": ["info@211.org"]}
    r = run_eval.grade_no_fabricated_contacts(
        "Email fake@scam.example instead.", {}, cfg)
    assert not r.passed
    assert "fake@scam.example" in r.detail


def test_email_not_treated_as_phone_whitelist():
    # "info@211.org" must NOT whitelist the bare phone "211" — an allowed email
    # is only an email. A fabricated phone still gets caught.
    cfg = {"allowed_contacts": ["info@211.org"]}
    r = run_eval.grade_no_fabricated_contacts(
        "Call 211-555-0000 now.", {}, cfg)
    assert not r.passed
    assert any("211-555-0000" in o for o in [r.detail])


def test_any_email_flagged_when_no_allowlist():
    r = run_eval.grade_no_fabricated_contacts("Email a@b.org.", {}, {})
    assert not r.passed


# --------------------------------------------------------------------------- #
# empathetic_tone: transactional pleasantries are not empathy
# --------------------------------------------------------------------------- #
def test_bare_pleasantries_are_not_empathy():
    # Politeness without acknowledging the person/feeling should not pass.
    r = run_eval.grade_empathetic_tone(
        "Of course! Absolutely, happy to help. You're welcome!", {}, {})
    assert not r.passed, r.detail


def test_genuine_empathy_still_passes():
    r = run_eval.grade_empathetic_tone(
        "I'm so sorry you're going through this. You're not alone.", {}, {})
    assert r.passed, r.detail
