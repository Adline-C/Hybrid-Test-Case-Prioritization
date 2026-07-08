import os
import json
import pytest
import coverage

cov = None

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    global cov
    # Configure coverage to monitor the sample_app directory
    cov = coverage.Coverage(source=["sample_app"])
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
        for filepath in data.measured_files():
            # Convert absolute path to a relative path from the repository root
            rel_path = os.path.relpath(filepath, os.getcwd()).replace("\\", "/")
            # Only track coverage for files within sample_app, excluding test_main.py itself
            if rel_path.startswith("sample_app/") and not rel_path.endswith("test_main.py"):
                covered_files.append(rel_path)
        
        item.config._covered_files_map[item.nodeid] = covered_files

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    # Log test result when the test execution actually finishes (the 'call' phase)
    if rep.when == "call":
        item.config._run_results[item.nodeid] = rep.passed

def pytest_sessionfinish(session, exitstatus):
    # Save coverage map
    if hasattr(session.config, "_covered_files_map"):
        with open("coverage_map.json", "w") as f:
            json.dump(session.config._covered_files_map, f, indent=4)
            
    # Load and update run history
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
            # Retain only the last 5 runs
            history[nodeid] = history[nodeid][-5:]
            
        with open(history_file, "w") as f:
            json.dump(history, f, indent=4)
