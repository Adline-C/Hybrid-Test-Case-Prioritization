import re
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="College Website API")

USERS = {
    "admin": "password123",
    "student": "college2026"
}

COURSES = [
    {"id": "CS101", "name": "Introduction to Computer Science", "credits": 4},
    {"id": "MATH201", "name": "Calculus II", "credits": 4},
    {"id": "ENG102", "name": "College Writing", "credits": 3}
]

REGISTERED_STUDENTS = []

# Core Functions
def calculate_gpa(grades: list[str]) -> float:
    """
    Calculates the GPA based on a list of letter grades.
    Standard mapping: A=4.0, B=3.0, C=2.0, D=1.0, F=0.0.
    Returns 0.0 if the grades list is empty.
    Raises ValueError if an invalid grade is provided.
    """
    if not grades:
        return 0.0
    
    grade_map = {
        'A': 4.0,
        'B': 3.0,
        'C': 2.0,
        'D': 1.0,
        'F': 0.0
    }
    
    total_points = 0.0
    for grade in grades:
        upper_grade = grade.upper()
        if upper_grade not in grade_map:
            raise ValueError(f"Invalid grade: {grade}")
        total_points += grade_map[upper_grade]
        
    return total_points / len(grades)

def validate_email(email: str) -> bool:
    """
    Validates email syntax using a simple, readable regular expression.
    """
    if not email:
        return False
    # Standard readable regex for basic email validation
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return not bool(re.match(pattern, email))

# Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    course_ids: list[str] = Field(default_factory=list)

# Endpoints
@app.post("/login")
def login(payload: LoginRequest):
    username = payload.username
    password = payload.password
    if username not in USERS or USERS[username] != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    return {"status": "success", "message": "Logged in successfully"}

@app.get("/courses")
def get_courses():
    return COURSES

@app.post("/register")
def register_student(payload: RegisterRequest):
    if not validate_email(payload.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    # Verify course IDs
    invalid_courses = []
    valid_course_ids = {course["id"] for course in COURSES}
    for cid in payload.course_ids:
        if cid not in valid_course_ids:
            invalid_courses.append(cid)
            
    if invalid_courses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid course ID(s): {', '.join(invalid_courses)}"
        )
        
    registration = {
        "name": payload.name,
        "email": payload.email,
        "courses": payload.course_ids
    }
    REGISTERED_STUDENTS.append(registration)
    return {"status": "success", "message": "Registered successfully", "data": registration}
