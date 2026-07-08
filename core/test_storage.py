import unittest
from unittest.mock import MagicMock, patch
import pytest
from core.storage import init_db, save_test_run, save_coverage_map, get_historical_runs, get_coverage_map

@patch("core.storage.psycopg2.connect")
def test_init_db(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    conn_params = {"host": "localhost", "database": "testdb"}
    init_db(conn_params)
    
    mock_connect.assert_called_once_with(**conn_params)
    assert mock_cur.execute.call_count == 2
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()

@patch("core.storage.psycopg2.connect")
def test_save_test_run(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    conn_params = {"host": "localhost"}
    save_test_run("test_login", True, ["sample_app/main.py"], conn_params)
    
    mock_cur.execute.assert_called_once()
    query, params = mock_cur.execute.call_args[0]
    assert "INSERT INTO test_runs" in query
    assert params[0] == "test_login"
    assert params[1] is True
    # The third param should be a Json wrapper or matched format
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()

@patch("core.storage.psycopg2.connect")
def test_save_coverage_map(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    conn_params = {"host": "localhost"}
    save_coverage_map("test_login", ["sample_app/main.py", "sample_app/utils.py"], conn_params)
    
    # Assert DELETE was called once, followed by 2 INSERTs
    assert mock_cur.execute.call_count == 3
    first_call_query = mock_cur.execute.call_args_list[0][0][0]
    assert "DELETE FROM coverage_map" in first_call_query
    
    second_call_query, second_call_params = mock_cur.execute.call_args_list[1][0]
    assert "INSERT INTO coverage_map" in second_call_query
    assert second_call_params == ("test_login", "sample_app/main.py")
    
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()

@patch("core.storage.psycopg2.connect")
def test_get_historical_runs(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    # Mock database rows (test_name, passed, executed_at)
    mock_cur.fetchall.return_value = [
        ("test_login", True, "2026-06-29 20:00:00"),
        ("test_login", False, "2026-06-29 20:05:00"),
        ("test_courses", True, "2026-06-29 20:01:00")
    ]
    
    conn_params = {"host": "localhost"}
    history = get_historical_runs(conn_params, limit=5)
    
    assert history == {
        "test_login": [True, False],
        "test_courses": [True]
    }
    
    mock_cur.execute.assert_called_once()
    mock_conn.close.assert_called_once()

@patch("core.storage.psycopg2.connect")
def test_get_coverage_map(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    mock_cur.fetchall.return_value = [
        ("test_courses", "sample_app/main.py"),
        ("test_login", "sample_app/main.py"),
        ("test_login", "sample_app/utils.py")
    ]
    
    conn_params = {"host": "localhost"}
    cov_map = get_coverage_map(conn_params)
    
    assert cov_map == {
        "test_courses": ["sample_app/main.py"],
        "test_login": ["sample_app/main.py", "sample_app/utils.py"]
    }
    
    mock_cur.execute.assert_called_once()
    mock_conn.close.assert_called_once()
