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
    When sample_app/main.py changed:
      test_login    → overlap(+2) + 2 failures(+2) = 4
      test_courses  → overlap(+2) + 0 failures     = 2
      test_register → no overlap  + 1 failure(+1)  = 1
    """
    ranked = build_ranked_list()

    assert ranked[0]["name"] == "test_login"
    assert ranked[0]["score"] == 4
    assert ranked[0]["overlap"] is True

    assert ranked[1]["name"] == "test_courses"
    assert ranked[1]["score"] == 2

    assert ranked[2]["name"] == "test_register"
    assert ranked[2]["score"] == 1
    assert ranked[2]["overlap"] is False


@patch("core.prioritize_runner.get_test_cases", return_value=_make_cases())
@patch("core.prioritize_runner.get_latest_changed_files", return_value=[])
def test_build_ranked_list_no_changes(mock_git, mock_cases):
    """When no files changed, overlap is never triggered; only history scores remain."""
    ranked = build_ranked_list()

    # test_login has 2 failures → score 2
    # test_courses has 0 failures → score 0
    # test_register has 1 failure → score 1
    scores = {r["name"]: r["score"] for r in ranked}
    assert scores["test_login"] == 2
    assert scores["test_courses"] == 0
    assert scores["test_register"] == 1
    # Must be sorted descending
    assert ranked[0]["score"] >= ranked[1]["score"] >= ranked[2]["score"]


@patch("core.prioritize_runner.get_test_cases", return_value=[])
@patch("core.prioritize_runner.get_latest_changed_files", return_value=[])
def test_build_ranked_list_empty(mock_git, mock_cases):
    """If no test cases exist yet, an empty list is returned without crashing."""
    ranked = build_ranked_list()
    assert ranked == []
