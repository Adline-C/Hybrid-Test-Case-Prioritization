import os
import json
import pytest
import coverage

cov = None

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    global cov
    # Monitor both "sample_app" package and the "main" module to support
    # executing pytest from either the repository root or inside sample_app/
    cov = coverage.Coverage(source=["sample_app", "main"])
    config._covered_files_map = {}
    config._run_results = {}

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    global cov
    if cov:
        cov.erase()
        cov.start()
    
    yield
    
    if cov:
        cov.stop()
        cov.save()
        data = cov.get_data()
        covered_files = []
        
        # Determine repo root to normalize paths consistently
        cwd = os.getcwd()
        repo_root = os.path.dirname(cwd) if os.path.basename(cwd) == "sample_app" else cwd
        
        for filepath in data.measured_files():
            # Convert absolute path to a relative path from the repository root
            rel_path = os.path.relpath(filepath, repo_root).replace("\\", "/")
            
            # If pytest is executed from inside sample_app, prefix paths with sample_app/
            if not rel_path.startswith("sample_app/") and os.path.basename(cwd) == "sample_app":
                rel_path = f"sample_app/{rel_path}"
                
            # Only track coverage for files within sample_app, excluding test files
            if rel_path.startswith("sample_app/") and not rel_path.endswith("test_main.py") and not rel_path.endswith("conftest.py"):
                covered_files.append(rel_path)
        
        item.config._covered_files_map[item.nodeid] = covered_files

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call":
        item.config._run_results[item.nodeid] = rep.passed

def pytest_sessionfinish(session, exitstatus):
    # Save coverage map to local JSON for fallback
    if hasattr(session.config, "_covered_files_map"):
        with open("coverage_map.json", "w") as f:
            json.dump(session.config._covered_files_map, f, indent=4)
            
    # Load and update run history in local JSON for fallback
    if hasattr(session.config, "_run_results"):
        history_file = "test_history.json"
        history = {}
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    history = json.load(f)
            except Exception:
                history = {}
                
        for nodeid, passed in session.config._run_results.items():
            if nodeid not in history:
                history[nodeid] = []
            history[nodeid].append(passed)
            history[nodeid] = history[nodeid][-5:]
            
        with open(history_file, "w") as f:
            json.dump(history, f, indent=4)

    # Wire to PostgreSQL if configured/available
    try:
        from core.storage import save_test_run, save_coverage_map
        from core.ingestion import get_latest_changed_files
        
        cwd = os.getcwd()
        repo_root = os.path.dirname(cwd) if os.path.basename(cwd) == "sample_app" else cwd
        changed_files = get_latest_changed_files(repo_root)
        
        # Save coverage map to PostgreSQL
        if hasattr(session.config, "_covered_files_map"):
            for nodeid, covered_files in session.config._covered_files_map.items():
                save_coverage_map(nodeid, covered_files)
                
        # Save run results to PostgreSQL
        if hasattr(session.config, "_run_results"):
            for nodeid, passed in session.config._run_results.items():
                save_test_run(nodeid, passed, changed_files)
    except Exception as e:
        print(f"\n[PostgreSQL Storage] Could not write execution log to database: {e}")

