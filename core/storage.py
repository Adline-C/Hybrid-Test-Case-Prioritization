import os
import json
import psycopg2
from psycopg2.extras import Json

def get_connection(conn_params: dict = None) -> psycopg2.extensions.connection:
    """
    Establishes and returns a connection to the PostgreSQL database.
    If conn_params is not provided, reads connection parameters from environment variables.
    """
    if conn_params is None:
        conn_params = {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": os.environ.get("DB_PORT", "5432"),
            "database": os.environ.get("DB_NAME", "postgres"),
            "user": os.environ.get("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", "postgres")
        }
    return psycopg2.connect(**conn_params)

def init_db(conn_params: dict = None):
    """
    Creates the required PostgreSQL tables if they do not exist.
    """
    conn = get_connection(conn_params)
    try:
        with conn.cursor() as cur:
            # Table 1: test_runs
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id SERIAL PRIMARY KEY,
                    test_name VARCHAR(255) NOT NULL,
                    passed BOOLEAN NOT NULL,
                    executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    files_changed JSONB
                );
            """)
            
            # Table 2: coverage_map
            cur.execute("""
                CREATE TABLE IF NOT EXISTS coverage_map (
                    id SERIAL PRIMARY KEY,
                    test_name VARCHAR(255) NOT NULL,
                    file_path VARCHAR(255) NOT NULL,
                    CONSTRAINT unique_test_file UNIQUE (test_name, file_path)
                );
            """)
            conn.commit()
    finally:
        conn.close()

def save_test_run(test_name: str, passed: bool, files_changed: list[str], conn_params: dict = None):
    """
    Saves a single test execution run result to the database.
    """
    conn = get_connection(conn_params)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO test_runs (test_name, passed, files_changed) VALUES (%s, %s, %s);",
                (test_name, passed, Json(files_changed))
            )
            conn.commit()
    finally:
        conn.close()

def save_coverage_map(test_name: str, covered_files: list[str], conn_params: dict = None):
    """
    Saves the list of files touched by a specific test, replacing existing mapping entries.
    """
    conn = get_connection(conn_params)
    try:
        with conn.cursor() as cur:
            # Delete outdated coverage files mapping
            cur.execute("DELETE FROM coverage_map WHERE test_name = %s;", (test_name,))
            # Insert the new mapped files
            for file_path in covered_files:
                cur.execute(
                    "INSERT INTO coverage_map (test_name, file_path) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                    (test_name, file_path)
                )
            conn.commit()
    finally:
        conn.close()

def get_historical_runs(conn_params: dict = None, limit: int = 5) -> dict[str, list[bool]]:
    """
    Gets the execution history of recent test runs, returning a dict of test_name -> list of pass/fail booleans.
    Ordered chronologically (oldest to newest, i.e., index -1 is most recent).
    """
    conn = get_connection(conn_params)
    try:
        with conn.cursor() as cur:
            # Retrieve recent runs per test case using a partition query
            cur.execute("""
                WITH ranked_runs AS (
                    SELECT test_name, passed, executed_at,
                           ROW_NUMBER() OVER (PARTITION BY test_name ORDER BY executed_at DESC) as rnk
                    FROM test_runs
                )
                SELECT test_name, passed, executed_at
                FROM ranked_runs
                WHERE rnk <= %s
                ORDER BY test_name, executed_at ASC;
            """, (limit,))
            
            rows = cur.fetchall()
            history = {}
            for test_name, passed, _ in rows:
                if test_name not in history:
                    history[test_name] = []
                history[test_name].append(passed)
            return history
    finally:
        conn.close()

def get_coverage_map(conn_params: dict = None) -> dict[str, list[str]]:
    """
    Retrieves all test-to-file coverage mappings from the database.
    """
    conn = get_connection(conn_params)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT test_name, file_path FROM coverage_map ORDER BY test_name, file_path;")
            rows = cur.fetchall()
            cov_map = {}
            for test_name, file_path in rows:
                if test_name not in cov_map:
                    cov_map[test_name] = []
                cov_map[test_name].append(file_path)
            return cov_map
    finally:
        conn.close()
