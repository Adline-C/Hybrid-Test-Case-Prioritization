import os
import json
from unittest.mock import MagicMock
from core.ingestion import get_latest_changed_files, load_coverage_map, load_run_history, get_test_cases

def test_load_coverage_map(tmp_path):
    map_file = tmp_path / "cov_map.json"
    dummy_data = {"test_foo": ["file_a.py", "file_b.py"]}
    map_file.write_text(json.dumps(dummy_data))
    
    loaded = load_coverage_map(str(map_file))
    assert loaded == dummy_data
    
    # Missing file should return empty dict safely
    assert load_coverage_map("non_existent_file.json") == {}

def test_load_run_history(tmp_path):
    history_file = tmp_path / "history.json"
    dummy_data = {"test_foo": [True, False, True]}
    history_file.write_text(json.dumps(dummy_data))
    
    loaded = load_run_history(str(history_file))
    assert loaded == dummy_data
    
    # Missing file should return empty dict safely
    assert load_run_history("non_existent_file.json") == {}

def test_get_test_cases(tmp_path):
    map_file = tmp_path / "cov_map.json"
    dummy_map = {
        "test_a": ["file_a.py"],
        "test_b": ["file_b.py"]
    }
    map_file.write_text(json.dumps(dummy_map))
    
    history_file = tmp_path / "history.json"
    dummy_history = {
        "test_a": [True],
        "test_c": [False]  # Test c has history but no coverage data
    }
    history_file.write_text(json.dumps(dummy_history))
    
    cases = get_test_cases(str(map_file), str(history_file))
    assert len(cases) == 3
    
    # Sort order is alphabetic by name
    names = [c.name for c in cases]
    assert names == ["test_a", "test_b", "test_c"]
    
    # check details
    assert cases[0].covered_files == ["file_a.py"]
    assert cases[0].history == [True]
    
    assert cases[1].covered_files == ["file_b.py"]
    assert cases[1].history == []
    
    assert cases[2].covered_files == []
    assert cases[2].history == [False]

def test_git_changed_files():
    # Query our own git repo.  We only assert structural correctness here
    # (a list of strings) rather than pinning specific filenames which change
    # with every new commit.
    changed = get_latest_changed_files(".")
    assert isinstance(changed, list)
    assert len(changed) > 0, "Expected at least one changed file in the latest commit"
    # Every entry must be a non-empty string
    for f in changed:
        assert isinstance(f, str) and len(f) > 0

from unittest.mock import patch

@patch("core.storage.psycopg2.connect")
def test_get_test_cases_use_db(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    # Mock return values for get_coverage_map and get_historical_runs queries
    # First query (get_coverage_map): returns list of (test_name, file_path)
    # Second query (get_historical_runs): returns list of (test_name, passed, executed_at)
    mock_cur.fetchall.side_effect = [
        [("test_login", "sample_app/main.py")],
        [("test_login", True, "2026-06-29 20:00:00")]
    ]
    
    cases = get_test_cases(use_db=True, conn_params={"host": "localhost"})
    assert len(cases) == 1
    assert cases[0].name == "test_login"
    assert cases[0].covered_files == ["sample_app/main.py"]
    assert cases[0].history == [True]

