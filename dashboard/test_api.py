"""
Tests for dashboard/api.py.

All ingestion + prioritization calls are mocked so the tests run
without needing real JSON files or a git repository.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from core.engine import CaseMetadata
from dashboard.api import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

MOCK_CASES = [
    CaseMetadata("test_login",    ["sample_app/main.py"], [True, False, False]),
    CaseMetadata("test_courses",  ["sample_app/main.py"], [True, True]),
    CaseMetadata("test_register", ["sample_app/utils.py"], [False]),
]

MOCK_CHANGED = ["sample_app/main.py"]

# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------

def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

# ---------------------------------------------------------------------------
# /api/ranking
# ---------------------------------------------------------------------------

@patch("dashboard.api.build_ranked_list")
@patch("dashboard.api._get_ranking")
def test_ranking_returns_sorted_by_score(mock_get_ranking, mock_runner):
    # _get_ranking is the helper we mock directly
    from core.engine import prioritize_tests
    ranked = prioritize_tests(MOCK_CASES, MOCK_CHANGED)
    mock_get_ranking.return_value = (MOCK_CHANGED, ranked)

    resp = client.get("/api/ranking")
    assert resp.status_code == 200
    data = resp.json()

    tests = data["tests"]
    assert len(tests) == 3

    # First test should be test_login: overlap(+2) + 2 failures(+2) = 4
    assert tests[0]["name"] == "test_login"
    assert tests[0]["score"] == 4
    assert tests[0]["overlap"] is True
    assert tests[0]["failures_in_last_5"] == 2
    assert tests[0]["rank"] == 1

    # Scores must be non-increasing
    scores = [t["score"] for t in tests]
    assert scores == sorted(scores, reverse=True)

    assert data["changed_files"] == MOCK_CHANGED

# ---------------------------------------------------------------------------
# /api/ranking/before
# ---------------------------------------------------------------------------

@patch("dashboard.api._get_ranking")
def test_before_ranking_is_alphabetical(mock_get_ranking):
    from core.engine import prioritize_tests
    ranked = prioritize_tests(MOCK_CASES, MOCK_CHANGED)
    mock_get_ranking.return_value = (MOCK_CHANGED, ranked)

    resp = client.get("/api/ranking/before")
    assert resp.status_code == 200
    data = resp.json()

    names = [t["name"] for t in data["tests"]]
    assert names == sorted(names)

# ---------------------------------------------------------------------------
# /api/comparison
# ---------------------------------------------------------------------------

@patch("dashboard.api._get_ranking")
def test_comparison_structure(mock_get_ranking):
    from core.engine import prioritize_tests
    ranked = prioritize_tests(MOCK_CASES, MOCK_CHANGED)
    mock_get_ranking.return_value = (MOCK_CHANGED, ranked)

    resp = client.get("/api/comparison")
    assert resp.status_code == 200
    data = resp.json()

    # Both lists must contain every test
    assert set(data["before"]) == set(data["after"])
    assert len(data["before"]) == 3

    # detail must have one entry per test
    assert len(data["detail"]) == 3

    # Each detail entry has the required fields
    for entry in data["detail"]:
        assert "before_rank" in entry
        assert "after_rank" in entry
        assert "moved_by" in entry
        assert entry["moved_by"] == entry["before_rank"] - entry["after_rank"]

@patch("dashboard.api._get_ranking")
def test_comparison_moved_by_calculation(mock_get_ranking):
    from core.engine import prioritize_tests
    ranked = prioritize_tests(MOCK_CASES, MOCK_CHANGED)
    mock_get_ranking.return_value = (MOCK_CHANGED, ranked)

    resp = client.get("/api/comparison")
    data = resp.json()
    detail_by_name = {d["name"]: d for d in data["detail"]}

    # test_login is rank 1 in prioritized but not rank 1 alphabetically
    # so moved_by should be positive (it moved earlier)
    login = detail_by_name["test_login"]
    assert login["after_rank"] == 1          # highest scorer goes first
    assert login["moved_by"] >= 0            # promoted vs alphabetical
