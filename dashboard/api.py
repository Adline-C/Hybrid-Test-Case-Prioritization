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
