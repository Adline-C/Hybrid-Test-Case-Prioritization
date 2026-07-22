"""
dashboard/api.py
================
FastAPI application that exposes the current test prioritization ranking
and a before/after comparison view.

Endpoints
---------
GET /api/health          – simple liveness check
GET /api/ranking         – prioritized (scored) test order, highest first
GET /api/ranking/before  – default (alphabetical) order that pytest uses
GET /api/comparison      – both orders side-by-side in one response

This module is intentionally read-only: it never modifies
coverage_map.json, test_history.json, or any database table.
"""

from __future__ import annotations

import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.prioritize_runner import build_ranked_list

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Hybrid Test Prioritization Dashboard API",
    description="Exposes the current test scoring/ranking computed by the prioritization engine.",
    version="1.0.0",
)

# Allow the plain-HTML frontend (opened as file://) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RankedTest(BaseModel):
    rank: int
    name: str
    score: int
    overlap: bool           # True if test touches a recently-changed file
    failures_in_last_5: int
    history: list[bool]     # full pass/fail history stored for this test

class RankingResponse(BaseModel):
    changed_files: list[str]
    tests: list[RankedTest]

class ComparisonEntry(BaseModel):
    before_rank: int        # alphabetical position
    after_rank: int         # prioritized position
    name: str
    score: int
    moved_by: int           # positive = promoted, negative = demoted

class ComparisonResponse(BaseModel):
    before: list[str]       # test names in alphabetical order
    after: list[str]        # test names in prioritized order
    detail: list[ComparisonEntry]

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_ranking() -> tuple[list[str], list[dict]]:
    """
    Returns (changed_files, ranked_dicts).
    Reads coverage_map.json + test_history.json from the repo root
    (the directory from which the server is started).
    """
    from core.ingestion import get_latest_changed_files
    changed_files = get_latest_changed_files(".")
    ranked = build_ranked_list()
    return changed_files, ranked

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    """Liveness check – always returns 200 OK."""
    return {"status": "ok"}


@app.get("/api/ranking", response_model=RankingResponse)
def get_ranking():
    """
    Returns all known tests ranked by their prioritization score
    (highest score = most likely to catch a newly introduced bug).

    Scoring formula:
      +2 if the test's covered files overlap with the latest git commit's changed files
      +1 for each failure in the most recent 5 runs
    """
    changed_files, ranked = _get_ranking()

    tests = [
        RankedTest(
            rank=i + 1,
            name=entry["name"],
            score=entry["score"],
            overlap=entry["overlap"],
            failures_in_last_5=entry["failures_in_last_5"],
            history=entry["history"],
        )
        for i, entry in enumerate(ranked)
    ]
    return RankingResponse(changed_files=changed_files, tests=tests)


@app.get("/api/ranking/before", response_model=RankingResponse)
def get_before_ranking():
    """
    Returns the same tests in alphabetical order — the default ordering
    pytest uses without prioritization.  Used for the 'before' side of
    the comparison view.
    """
    changed_files, ranked = _get_ranking()

    # Sort alphabetically to simulate vanilla pytest collection order
    before_ranked = sorted(ranked, key=lambda x: x["name"])

    tests = [
        RankedTest(
            rank=i + 1,
            name=entry["name"],
            score=entry["score"],
            overlap=entry["overlap"],
            failures_in_last_5=entry["failures_in_last_5"],
            history=entry["history"],
        )
        for i, entry in enumerate(before_ranked)
    ]
    return RankingResponse(changed_files=changed_files, tests=tests)


@app.get("/api/comparison", response_model=ComparisonResponse)
def get_comparison():
    """
    Returns a side-by-side comparison of the alphabetical (before) order
    vs. the prioritized (after) order, along with how many positions each
    test was promoted or demoted.
    """
    changed_files, ranked = _get_ranking()

    # Alphabetical = "before" order
    before_list = [e["name"] for e in sorted(ranked, key=lambda x: x["name"])]
    # Prioritized = "after" order
    after_list = [e["name"] for e in ranked]

    # Build position lookups (1-indexed)
    before_pos = {name: i + 1 for i, name in enumerate(before_list)}
    after_pos  = {name: i + 1 for i, name in enumerate(after_list)}

    # Score lookup
    score_map = {e["name"]: e["score"] for e in ranked}

    detail = [
        ComparisonEntry(
            before_rank=before_pos[name],
            after_rank=after_pos[name],
            name=name,
            score=score_map[name],
            moved_by=before_pos[name] - after_pos[name],  # positive = moved earlier
        )
        for name in before_list
    ]

    return ComparisonResponse(before=before_list, after=after_list, detail=detail)


import tempfile
import shutil
import subprocess
import glob
import sys

class AnalyzeRequest(BaseModel):
    repo_url: str

@app.post("/api/analyze", response_model=RankingResponse)
def analyze_repo(payload: AnalyzeRequest):
    """
    Clones a public GitHub repository, installs its requirements (if present),
    runs pytest with coverage to build test mapping files, and scores/prioritizes
    its test cases. Returns the ranked test suite list.
    """
    repo_url = payload.repo_url.strip()
    if not repo_url:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty")

    # 1. Create a temp directory
    temp_dir = tempfile.mkdtemp()
    try:
        # 2. Clone the repository using GitPython
        import git
        from fastapi import HTTPException
        try:
            git.Repo.clone_from(repo_url, temp_dir, depth=2)
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to clone repository. Make sure it is public and valid. Error: {str(e)}"
            )

        # 3. Check for pytest tests
        test_files = (
            glob.glob(os.path.join(temp_dir, "**/test_*.py"), recursive=True) +
            glob.glob(os.path.join(temp_dir, "**/*_test.py"), recursive=True)
        )
        if not test_files:
            raise HTTPException(status_code=400, detail="No pytest tests found in this repository")

        # 4. Install dependencies from requirements.txt if present
        req_path = os.path.join(temp_dir, "requirements.txt")
        if os.path.exists(req_path):
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--user", "-r", req_path],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=180
                )
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=400, detail="Dependency installation timed out after 3 minutes.")
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode("utf-8", errors="ignore")
                raise HTTPException(status_code=400, detail=f"Dependency installation failed: {err_msg}")

        # 5. Inject a temporary conftest.py to instrument test coverage and outcomes
        conftest_content = """
import os
import json
import pytest
import coverage

cov = None

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    global cov
    cov = coverage.Coverage(source=[os.getcwd()])
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
        cwd = os.getcwd()
        for filepath in data.measured_files():
            rel_path = os.path.relpath(filepath, cwd).replace("\\\\", "/")
            if not rel_path.startswith("test_") and not "test_" in rel_path and not rel_path.endswith("conftest.py"):
                covered_files.append(rel_path)
        item.config._covered_files_map[item.nodeid] = covered_files

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call":
        item.config._run_results[item.nodeid] = rep.passed

def pytest_sessionfinish(session, exitstatus):
    if hasattr(session.config, "_covered_files_map"):
        with open("coverage_map.json", "w") as f:
            json.dump(session.config._covered_files_map, f, indent=4)
    if hasattr(session.config, "_run_results"):
        history = {}
        for nodeid, passed in session.config._run_results.items():
            history[nodeid] = [passed]
        with open("test_history.json", "w") as f:
            json.dump(history, f, indent=4)
"""
        with open(os.path.join(temp_dir, "conftest.py"), "w") as f:
            f.write(conftest_content)

        # 6. Run pytest on the cloned repo to generate coverage and history files
        try:
            subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=temp_dir,
                check=False, # We want to collect fail results, not stop execution
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to execute tests: {str(e)}")

        temp_cov_path = os.path.join(temp_dir, "coverage_map.json")
        temp_hist_path = os.path.join(temp_dir, "test_history.json")

        if not os.path.exists(temp_cov_path) or not os.path.exists(temp_hist_path):
            raise HTTPException(
                status_code=400, 
                detail="Test execution finished but failed to generate prioritization telemetry."
            )

        # 7. Execute prioritization engine
        from core.ingestion import get_latest_changed_files, get_test_cases
        from core.engine import prioritize_tests

        changed_files = get_latest_changed_files(temp_dir)
        test_cases = get_test_cases(map_path=temp_cov_path, history_path=temp_hist_path)
        ranked = prioritize_tests(test_cases, changed_files)

        tests = [
            RankedTest(
                rank=i + 1,
                name=entry["name"],
                score=entry["score"],
                overlap=entry["overlap"],
                failures_in_last_5=entry["failures_in_last_5"],
                history=entry["history"]
            )
            for i, entry in enumerate(ranked)
        ]

        return RankingResponse(changed_files=changed_files, tests=tests)

    finally:
        # 8. Clean up temp folder
        shutil.rmtree(temp_dir, ignore_errors=True)

