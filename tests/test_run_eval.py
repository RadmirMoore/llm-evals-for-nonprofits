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
