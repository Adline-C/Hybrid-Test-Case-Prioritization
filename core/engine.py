from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class CaseMetadata:
    name: str
    covered_files: List[str] = field(default_factory=list)
    # history: a list of boolean values representing test run results.
    # True indicates PASS, False indicates FAIL.
    # The list is ordered chronologically, with the most recent run at the END of the list.
    history: List[bool] = field(default_factory=list)

def score_test(test_case: CaseMetadata, changed_files: List[str], w_c: float = 2.0, w_h: float = 1.0) -> Dict[str, Any]:
    """
    Calculates the regression prioritization score for a single test case based on:
    1. Overlap of covered files with recently changed files (boost by w_c if there is any overlap).
    2. Number of recent failures in the most recent 5 runs (boost by w_h per failure).
    
    Returns a dictionary with the test name, calculated score, and details.
    """
    score = 0.0
    overlap_found = False
    
    # 1. Overlap Check (boost by w_c)
    # If the test case touches any file that has been recently changed.
    # We use set intersection for efficiency.
    if set(test_case.covered_files) & set(changed_files):
        score += w_c
        overlap_found = True
        
    # 2. History Check (boost by w_h per failure in most recent 5 runs)
    # We examine the last 5 runs (history[-5:]). False represents a FAIL.
    recent_runs = test_case.history[-5:]
    failures_count = recent_runs.count(False)
    score += failures_count * w_h
    
    return {
        "name": test_case.name,
        "score": score,
        "overlap": overlap_found,
        "failures_in_last_5": failures_count,
        "history": test_case.history
    }

def prioritize_tests(test_cases: List[CaseMetadata], changed_files: List[str], w_c: float = 2.0, w_h: float = 1.0) -> List[Dict[str, Any]]:
    """
    Scores all test cases and ranks them from highest to lowest score.
    Uses Python's stable sort so that if scores are equal, the original order is preserved.
    """
    scored = [score_test(tc, changed_files, w_c, w_h) for tc in test_cases]
    # Sort descending by score.
    return sorted(scored, key=lambda x: x["score"], reverse=True)
