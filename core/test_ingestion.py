import os
import json
import pytest
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
    # Since we initialized Git and have made commits, we can query our own git repo
    changed = get_latest_changed_files(".")
    assert isinstance(changed, list)
    # The last commit (Commit 4) added core/engine.py and core/test_engine.py
    # Let's verify that these are in the list of changed files
    normalized = [f.replace("\\", "/") for f in changed]
    assert "core/engine.py" in normalized
    assert "core/test_engine.py" in normalized
