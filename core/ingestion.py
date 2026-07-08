import os
import json
import git
from core.engine import CaseMetadata

def get_latest_changed_files(repo_path: str = ".") -> list[str]:
    """
    Retrieves the list of files modified or added in the latest commit.
    If the repository has no commits or is invalid, returns an empty list.
    """
    try:
        repo = git.Repo(repo_path)
        if not repo.head.is_valid():
            return []
        
        commit = repo.head.commit
        # If it's the initial commit (no parents), list all files tracked
        if not commit.parents:
            changed_files = []
            for entry in commit.tree.traverse():
                if entry.type == 'blob':
                    changed_files.append(entry.path)
            return changed_files
            
        # Get diffs against the primary parent commit
        parent = commit.parents[0]
        diffs = parent.diff(commit)
        
        changed_files = set()
        for diff in diffs:
            if diff.a_path:
                changed_files.add(diff.a_path)
            if diff.b_path:
                changed_files.add(diff.b_path)
                
        return list(changed_files)
    except Exception as e:
        print(f"Error reading git repo: {e}")
        return []

def load_coverage_map(map_path: str = "coverage_map.json") -> dict:
    """
    Loads the coverage mapping data from the specified JSON file.
    Returns a dict mapping test names to list of files they cover.
    """
    if not os.path.exists(map_path):
        return {}
    try:
        with open(map_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading coverage map: {e}")
        return {}

def load_run_history(history_path: str = "test_history.json") -> dict:
    """
    Loads the pass/fail execution history of the tests.
    Returns a dict mapping test names to lists of booleans (True = Pass, False = Fail).
    """
    if not os.path.exists(history_path):
        return {}
    try:
        with open(history_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading run history: {e}")
        return {}

def get_test_cases(map_path: str = "coverage_map.json", history_path: str = "test_history.json") -> list[CaseMetadata]:
    """
    Integrates coverage mapping and historical execution data to build
    a list of CaseMetadata instances representing the test cases.
    """
    coverage_map = load_coverage_map(map_path)
    run_history = load_run_history(history_path)
    
    # We want to represent all tests found in either the coverage map or history.
    # Typically, coverage_map is the source of truth for active test cases.
    all_tests = set(coverage_map.keys()) | set(run_history.keys())
    
    test_cases = []
    for test_name in sorted(all_tests):
        covered = coverage_map.get(test_name, [])
        history = run_history.get(test_name, [])
        test_cases.append(
            CaseMetadata(
                name=test_name,
                covered_files=covered,
                history=history
            )
        )
    return test_cases
