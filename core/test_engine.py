import pytest
from core.engine import CaseMetadata, score_test, prioritize_tests


def test_priority_overlap_only():
    # Overlap C=1, no failures H=0 → S = 3 * (2*1 + 1*0) / 3 = 2.0
    tc = CaseMetadata(
        name="test_login",
        covered_files=["sample_app/main.py", "sample_app/utils.py"],
        history=[True, True, True]
    )
    changed = ["sample_app/main.py"]
    result = score_test(tc, changed)
    assert result["score"] == pytest.approx(2.0)
    assert result["overlap"] is True
    assert result["failures_in_last_5"] == 0


def test_priority_failures_only():
    # No overlap C=0, 3 failures H=0.6 → S = 3 * (0 + 1*0.6) / 3 = 0.6
    tc = CaseMetadata(
        name="test_courses",
        covered_files=["sample_app/main.py"],
        history=[True, False, True, False, False]
    )
    changed = ["sample_app/auth.py"]
    result = score_test(tc, changed)
    assert result["score"] == pytest.approx(0.6)
    assert result["overlap"] is False
    assert result["failures_in_last_5"] == 3


def test_priority_mixed():
    # Overlap C=1, 2 failures H=0.4 → S = 3 * (2*1 + 1*0.4) / 3 = 2.4
    tc = CaseMetadata(
        name="test_register",
        covered_files=["sample_app/main.py"],
        history=[False, True, False, True, True]
    )
    changed = ["sample_app/main.py"]
    result = score_test(tc, changed)
    assert result["score"] == pytest.approx(2.4)
    assert result["overlap"] is True
    assert result["failures_in_last_5"] == 2


def test_priority_history_length():
    # Last 5 runs: [FAIL, PASS, FAIL, FAIL, PASS] → 3 failures, no overlap → S = 0.6
    tc = CaseMetadata(
        name="test_gpa",
        covered_files=["sample_app/utils.py"],
        history=[False, False, True, False, False, True]
    )
    changed = ["sample_app/auth.py"]
    result = score_test(tc, changed)
    assert result["score"] == pytest.approx(0.6)
    assert result["failures_in_last_5"] == 3


def test_priority_sorting():
    tc1 = CaseMetadata("test_a", ["file_a"], [True, True])  # overlap, H=0 → 2.0
    tc2 = CaseMetadata("test_b", ["file_b"], [False, False])  # no overlap, H=0.4 → 0.4
    tc3 = CaseMetadata("test_c", ["file_c"], [False, False, False])  # no overlap, H=0.6 → 0.6
    tc4 = CaseMetadata("test_d", ["file_a"], [False])  # overlap, H=0.2 → 2.2

    test_cases = [tc1, tc2, tc3, tc4]
    changed = ["file_a"]

    ranked = prioritize_tests(test_cases, changed)

    assert ranked[0]["name"] == "test_d"
    assert ranked[1]["name"] == "test_a"
    assert ranked[2]["name"] == "test_c"
    assert ranked[3]["name"] == "test_b"

    assert [r["score"] for r in ranked] == pytest.approx([2.2, 2.0, 0.6, 0.4])


def test_priority_custom_weights():
    # Overlap C=1, 2 failures H=0.4, w_c=3.5, w_h=0.5
    # S = 3.5 * 1 + 0.5 * 0.4 = 3.7
    tc = CaseMetadata(
        name="test_custom",
        covered_files=["sample_app/main.py"],
        history=[False, True, False, True, True]
    )
    changed = ["sample_app/main.py"]
    result = score_test(tc, changed, w_c=3.5, w_h=0.5)
    assert result["score"] == pytest.approx(3.7)
    assert result["overlap"] is True
    assert result["failures_in_last_5"] == 2


def test_score_max_bounded():
    tc = CaseMetadata(
        name="test_max",
        covered_files=["a.py"],
        history=[False, False, False, False, False],
    )
    result = score_test(tc, ["a.py"], w_c=5.0, w_h=5.0)
    assert 0.0 <= result["score"] <= 10.0
    assert result["score"] == pytest.approx(10.0)


def test_zero_weights_yield_zero_score():
    tc = CaseMetadata(name="test_zero", covered_files=["a.py"], history=[False])
    result = score_test(tc, ["a.py"], w_c=0.0, w_h=0.0)
    assert result["score"] == 0.0
