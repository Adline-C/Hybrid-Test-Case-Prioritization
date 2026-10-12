"""
Tests for core/prioritize_runner.py.
Uses mocked ingestion so no real git repo or JSON files are required.
"""
import pytest
from unittest.mock import patch, MagicMock
from core.engine import CaseMetadata
from core.prioritize_runner import build_ranked_list


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_cases():
    """Return a small list of CaseMetadata with interesting variation."""
    return [
        CaseMetadata("test_login",    ["sample_app/main.py"],  [True, False, False]),
        CaseMetadata("test_courses",  ["sample_app/main.py"],  [True, True]),
        CaseMetadata("test_register", ["sample_app/utils.py"], [False]),
    ]


# ── tests ───────────────────────────────────────────────────────────────────────

@patch("core.prioritize_runner.get_test_cases", return_value=_make_cases())
@patch("core.prioritize_runner.get_latest_changed_files", return_value=["sample_app/main.py"])
def test_build_ranked_list_basic(mock_git, mock_cases):
    """
    When sample_app/main.py changed (normalized 0–3):
      test_login    → C=1, H=0.4 → S = 3*(2*1 + 1*0.4)/3 = 2.4
      test_courses  → C=1, H=0.0 → S = 3*(2*1 + 0)/3     = 2.0
      test_register → C=0, H=0.2 → S = 3*(0 + 1*0.2)/3   = 0.2
    """
    ranked = build_ranked_list()

    assert ranked[0]["name"] == "test_login"
    assert ranked[0]["score"] == pytest.approx(2.4)
    assert ranked[0]["overlap"] is True

    assert ranked[1]["name"] == "test_courses"
    assert ranked[1]["score"] == pytest.approx(2.0)

    assert ranked[2]["name"] == "test_register"
    assert ranked[2]["score"] == pytest.approx(0.2)
    assert ranked[2]["overlap"] is False


@patch("core.prioritize_runner.get_test_cases", return_value=_make_cases())
@patch("core.prioritize_runner.get_latest_changed_files", return_value=[])
def test_build_ranked_list_no_changes(mock_git, mock_cases):
    """When no files changed, overlap is never triggered; only history scores remain."""
    ranked = build_ranked_list()

    # No overlap: S = 3 * (w_h * H) / (w_c + w_h) with defaults 2 and 1
    # test_login H=0.4 → 0.4; test_courses H=0 → 0; test_register H=0.2 → 0.2
    scores = {r["name"]: r["score"] for r in ranked}
    assert scores["test_login"] == pytest.approx(0.4)
    assert scores["test_courses"] == pytest.approx(0.0)
    assert scores["test_register"] == pytest.approx(0.2)
    # Must be sorted descending
    assert ranked[0]["score"] >= ranked[1]["score"] >= ranked[2]["score"]


@patch("core.prioritize_runner.get_test_cases", return_value=[])
@patch("core.prioritize_runner.get_latest_changed_files", return_value=[])
def test_build_ranked_list_empty(mock_git, mock_cases):
    """If no test cases exist yet, an empty list is returned without crashing."""
    ranked = build_ranked_list()
    assert ranked == []
