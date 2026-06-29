import re

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
    return bool(re.match(pattern, email))
