import pytest
from core.engine import CaseMetadata, score_test, prioritize_tests

def test_priority_overlap_only():
    # Test case has overlap with changed files (+2), no failures in history
    tc = CaseMetadata(
        name="test_login",
        covered_files=["sample_app/main.py", "sample_app/utils.py"],
        history=[True, True, True]
    )
    changed = ["sample_app/main.py"]
    result = score_test(tc, changed)
    assert result["score"] == 2
    assert result["overlap"] is True
    assert result["failures_in_last_5"] == 0

def test_priority_failures_only():
    # Test case has no overlap, but 3 failures in history (+3)
    tc = CaseMetadata(
        name="test_courses",
        covered_files=["sample_app/main.py"],
        history=[True, False, True, False, False]
    )
    changed = ["sample_app/auth.py"]
    result = score_test(tc, changed)
    assert result["score"] == 3
    assert result["overlap"] is False
    assert result["failures_in_last_5"] == 3

def test_priority_mixed():
    # Test case has overlap (+2) and 2 failures (+2) -> total score 4
    tc = CaseMetadata(
        name="test_register",
        covered_files=["sample_app/main.py"],
        history=[False, True, False, True, True]
    )
    changed = ["sample_app/main.py"]
    result = score_test(tc, changed)
    assert result["score"] == 4
    assert result["overlap"] is True
    assert result["failures_in_last_5"] == 2

def test_priority_history_length():
    # Test case has 6 runs, 4 failures overall, but only 3 of them are in the last 5 runs.
    # Chronological history (oldest to newest):
    # [FAIL, FAIL, PASS, FAIL, FAIL, PASS]
    # The last 5 runs are: [FAIL, PASS, FAIL, FAIL, PASS] -> 3 failures.
    tc = CaseMetadata(
        name="test_gpa",
        covered_files=["sample_app/utils.py"],
        history=[False, False, True, False, False, True]
    )
    changed = ["sample_app/auth.py"]
    result = score_test(tc, changed)
    assert result["score"] == 3
    assert result["failures_in_last_5"] == 3

def test_priority_sorting():
    tc1 = CaseMetadata("test_a", ["file_a"], [True, True])  # score 0
    tc2 = CaseMetadata("test_b", ["file_b"], [False, False])  # score 2
    tc3 = CaseMetadata("test_c", ["file_c"], [False, False, False])  # score 3
    tc4 = CaseMetadata("test_d", ["file_a"], [False])  # overlap (2) + failure (1) = 3
    
    test_cases = [tc1, tc2, tc3, tc4]
    changed = ["file_a"]
    
    ranked = prioritize_tests(test_cases, changed)
    
    # Expected scores:
    # tc4: overlap with file_a (+2) + 1 failure (+1) = 3
    # tc3: no overlap (+0) + 3 failures (+3) = 3
    # tc2: no overlap (+0) + 2 failures (+2) = 2
    # tc1: overlap with file_a (+2) + 0 failures (+0) = 2
    # Ranked order: tc3/tc4 (scores of 3), then tc2/tc1 (scores of 2)
    # Since stable sort is used:
    # tc3 comes before tc4 because tc3 was originally before tc4.
    # tc2 comes before tc1 because tc2 was originally before tc1 (wait, tc1 was before tc2, let's trace:
    # tc1 is index 0 (score 2), tc2 is index 1 (score 2).
    # Since they both have score 2, and stable sort preserves order, tc1 should come before tc2.)
    
    assert ranked[0]["name"] == "test_c"  # score 3
    assert ranked[1]["name"] == "test_d"  # score 3
    assert ranked[2]["name"] == "test_a"  # score 2
    assert ranked[3]["name"] == "test_b"  # score 2
    
    assert [r["score"] for r in ranked] == [3, 3, 2, 2]


def test_priority_custom_weights():
    # Test case has overlap and 2 failures
    tc = CaseMetadata(
        name="test_custom",
        covered_files=["sample_app/main.py"],
        history=[False, True, False, True, True]
    )
    changed = ["sample_app/main.py"]
    # Run with w_c = 3.5, w_h = 0.5
    result = score_test(tc, changed, w_c=3.5, w_h=0.5)
    # Expected: overlap boost (3.5) + (2 failures * 0.5) = 4.5
    assert result["score"] == 4.5
    assert result["overlap"] is True
    assert result["failures_in_last_5"] == 2

