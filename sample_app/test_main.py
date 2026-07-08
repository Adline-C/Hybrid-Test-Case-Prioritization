import pytest
from fastapi.testclient import TestClient
from main import app, calculate_gpa, validate_email, REGISTERED_STUDENTS

client = TestClient(app)

# --- Unit Tests for calculate_gpa ---

def test_calculate_gpa_all_a():
    assert calculate_gpa(["A", "A", "A"]) == 4.0

def test_calculate_gpa_mixed():
    # A=4, B=3, C=2 -> 9 / 3 = 3.0
    assert calculate_gpa(["A", "B", "C"]) == 3.0

def test_calculate_gpa_empty():
    assert calculate_gpa([]) == 0.0

def test_calculate_gpa_invalid():
    with pytest.raises(ValueError):
        calculate_gpa(["A", "Z"])

def test_calculate_gpa_lowercase():
    assert calculate_gpa(["a", "b"]) == 3.5

def test_calculate_gpa_all_f():
    assert calculate_gpa(["F", "F"]) == 0.0


# --- Unit Tests for validate_email ---

def test_validate_email_valid():
    assert validate_email("student@college.edu") is True
    assert validate_email("test.name+alias@domain.co.uk") is True

def test_validate_email_invalid_no_domain():
    assert validate_email("student@") is False

def test_validate_email_invalid_no_at():
    assert validate_email("student.college.edu") is False

def test_validate_email_invalid_short_tld():
    assert validate_email("student@college.c") is False

def test_validate_email_empty():
    assert validate_email("") is False


# --- Integration Tests for Endpoints ---

def test_endpoint_login_success():
    response = client.post("/login", json={"username": "student", "password": "college2026"})
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Logged in successfully"}

def test_endpoint_login_invalid_password():
    response = client.post("/login", json={"username": "student", "password": "wrongpassword"})
    assert response.status_code == 401
    assert "detail" in response.json()

def test_endpoint_login_invalid_user():
    response = client.post("/login", json={"username": "nonexistent", "password": "password"})
    assert response.status_code == 401

def test_endpoint_login_missing_fields():
    response = client.post("/login", json={"username": "student"})
    assert response.status_code == 422


def test_endpoint_courses():
    response = client.get("/courses")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["id"] == "CS101"


def test_endpoint_register_success():
    # Clear previous registrations for clean test state
    REGISTERED_STUDENTS.clear()
    payload = {
        "name": "Alice Smith",
        "email": "alice@college.edu",
        "course_ids": ["CS101", "MATH201"]
    }
    response = client.post("/register", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert len(REGISTERED_STUDENTS) == 1
    assert REGISTERED_STUDENTS[0]["name"] == "Alice Smith"

def test_endpoint_register_invalid_email():
    payload = {
        "name": "Bob",
        "email": "invalid-email",
        "course_ids": ["CS101"]
    }
    response = client.post("/register", json=payload)
    assert response.status_code == 400
    assert "Invalid email format" in response.json()["detail"]

def test_endpoint_register_invalid_course():
    payload = {
        "name": "Charlie",
        "email": "charlie@college.edu",
        "course_ids": ["INVALID_COURSE_ID"]
    }
    response = client.post("/register", json=payload)
    assert response.status_code == 400
    assert "Invalid course ID" in response.json()["detail"]

def test_endpoint_register_empty_courses():
    REGISTERED_STUDENTS.clear()
    payload = {
        "name": "Diana",
        "email": "diana@college.edu",
        "course_ids": []
    }
    response = client.post("/register", json=payload)
    assert response.status_code == 200
    assert len(REGISTERED_STUDENTS) == 1
