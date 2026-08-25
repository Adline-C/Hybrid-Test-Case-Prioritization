"""
prioritize_runner.py
====================
Standalone script that:
  1. Reads the latest changed files from git (via GitPython).
  2. Reads the coverage map and run history (from JSON files, or Postgres if configured).
  3. Runs the scoring engine to rank all known tests.
  4. Prints the ranked test node IDs to stdout (one per line).
  5. Optionally writes a pytest --collect-only-style argument file that
     the CI step can pass directly to pytest.

Usage:
    python -m core.prioritize_runner
    python -m core.prioritize_runner --output-file prioritized_tests.txt

The script is intentionally self-contained and side-effect-free (no DB writes).
It only reads data so it is safe to re-run at any time.
"""

import argparse
import sys
import os

from core.ingestion import get_latest_changed_files, get_test_cases
from core.engine import prioritize_tests


def build_ranked_list(repo_path: str = ".", use_db: bool = False, conn_params: dict = None, w_c: float = 2.0, w_h: float = 1.0) -> list[dict]:
    """
    Orchestrates the full prioritization pipeline:
      - Detect which files changed in the latest git commit.
      - Load all known test cases (coverage + history).
      - Score and rank them.

    Returns the ranked list of score dicts (highest score first).
    """
    # Step 1 – which files changed in the latest commit?
    changed_files = get_latest_changed_files(repo_path)

    # Step 2 – build CaseMetadata list from coverage + history
    test_cases = get_test_cases(use_db=use_db, conn_params=conn_params)

    # Step 3 – run the scoring engine
    ranked = prioritize_tests(test_cases, changed_files, w_c=w_c, w_h=w_h)
    return ranked


def main():
    parser = argparse.ArgumentParser(
        description="Prioritize test cases for regression testing."
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the git repository root (default: current directory).",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="If provided, write ranked test node IDs to this file (one per line).",
    )
    parser.add_argument(
        "--use-db",
        action="store_true",
        help="Load history and coverage from PostgreSQL instead of JSON files.",
    )
    args = parser.parse_args()

    ranked = build_ranked_list(repo_path=args.repo_path, use_db=args.use_db)

    if not ranked:
        print("[prioritize_runner] No test cases found. Run the sample_app tests first to populate coverage data.")
        sys.exit(0)

    # Print the ranking table to stdout for visibility
    print(f"\n{'Rank':<6} {'Score':<8} {'Overlap':<10} {'Recent Fails':<14} Test Name")
    print("-" * 90)
    for rank, entry in enumerate(ranked, start=1):
        overlap_flag = "YES" if entry["overlap"] else "no"
        print(
            f"{rank:<6} {entry['score']:<8} {overlap_flag:<10} {entry['failures_in_last_5']:<14} {entry['name']}"
        )

    # Write just the test node IDs to a file if requested
    if args.output_file:
        with open(args.output_file, "w") as f:
            for entry in ranked:
                f.write(entry["name"] + "\n")
        print(f"\n[prioritize_runner] Ranked test order written to: {args.output_file}")

    return ranked


if __name__ == "__main__":
    main()
