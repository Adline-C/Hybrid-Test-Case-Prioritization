import os
import json
import git
from core.engine import CaseMetadata

def get_latest_changed_files(repo_path: str = ".") -> list[str]:
    """
    Retrieves the list of files modified or added in the latest commit.
    If the latest commit only modifies non-Python files (.md, .rst, .txt, etc.),
    falls back to analyzing the most recent commit that actually modified .py files.
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
                
        # Check if any changed file is a Python file (.py)
        has_py = any(f.endswith(".py") for f in changed_files)
        if not has_py:
            # Fallback to the most recent commit that modified .py files
            try:
                py_commits = list(repo.iter_commits(max_count=1, paths="*.py"))
                if py_commits:
                    py_commit = py_commits[0]
                    if py_commit.parents:
                        py_diffs = py_commit.parents[0].diff(py_commit)
                    else:
                        py_diffs = py_commit.diff(git.NULL_TREE)
                    py_changed = set()
                    for diff in py_diffs:
                        if diff.a_path:
                            py_changed.add(diff.a_path)
                        if diff.b_path:
                            py_changed.add(diff.b_path)
                    if py_changed:
                        return list(py_changed)
            except Exception as sub_e:
                print(f"Error fetching py commit fallback: {sub_e}")

        return list(changed_files)
    except Exception as e:
        print(f"Error reading git repo: {e}")
        return []



def get_head_commit_meta(repo_path: str = ".") -> dict:
    """
    Returns {sha, repo_name} for the HEAD commit. Safe fallbacks if git is unavailable.
    """
    abs_path = os.path.abspath(repo_path)
    repo_name = os.path.basename(abs_path.rstrip("\\/")) or "repository"
    try:
        repo = git.Repo(repo_path)
        if repo.working_tree_dir:
            repo_name = os.path.basename(os.path.abspath(repo.working_tree_dir))
        if not repo.head.is_valid():
            return {"sha": "HEAD", "repo_name": repo_name}
        return {"sha": repo.head.commit.hexsha[:7], "repo_name": repo_name}
    except Exception:
        return {"sha": "HEAD", "repo_name": repo_name}

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

def normalize_test_name(name: str) -> str:
    """
    Standardizes test names (e.g. converting 'test_main.py::...' to 'sample_app/test_main.py::...')
    so that history logs and coverage maps align regardless of where pytest was run from.
    """
    name = name.replace("\\", "/")
    if "test_main.py::" in name and not name.startswith("sample_app/"):
        return "sample_app/" + name
    return name

def get_test_cases(map_path: str = "coverage_map.json", history_path: str = "test_history.json", use_db: bool = False, conn_params: dict = None) -> list[CaseMetadata]:
    """
    Integrates coverage mapping and historical execution data to build
    a list of CaseMetadata instances representing the test cases.
    If use_db is True, queries the PostgreSQL database; otherwise, loads from JSON.
    """
    if use_db:
        try:
            from core.storage import get_coverage_map, get_historical_runs
            raw_coverage = get_coverage_map(conn_params)
            raw_history = get_historical_runs(conn_params)
        except Exception as e:
            print(f"Error reading from database: {e}. Falling back to JSON files.")
            raw_coverage = load_coverage_map(map_path)
            raw_history = load_run_history(history_path)
    else:
        raw_coverage = load_coverage_map(map_path)
        raw_history = load_run_history(history_path)

    # Normalize keys to align test cases
    coverage_map = {normalize_test_name(k): v for k, v in raw_coverage.items()}
    run_history = {normalize_test_name(k): v for k, v in raw_history.items()}
    
    # We want to represent all tests found in either the coverage map or history.
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
