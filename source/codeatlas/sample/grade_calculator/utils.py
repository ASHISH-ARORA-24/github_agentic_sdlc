# Utility functions for the grade calculator.
# These are pure calculation functions — they take inputs and return outputs
# with no side effects. Keeping them separate from main.py means they can
# be tested and reused independently.

from datetime import date


def calculate_average(marks: list[float]) -> float:
    """
    Calculates the average of a list of marks.

    Divides the sum of all marks by the number of marks.
    Used by get_student_report in main.py to compute the overall score
    before determining the letter grade.
    """
    return sum(marks) / len(marks)


def calculate_grade(average: float) -> str:
    """
    Converts a numeric average into a letter grade.

    Grading scale:
    - 90 and above -> A
    - 75 to 89     -> B
    - 60 to 74     -> C
    - 50 to 59     -> D
    - Below 50     -> F

    Returns a single uppercase letter representing the grade.
    """
    if average >= 90:
        return "A"
    elif average >= 75:
        return "B"
    elif average >= 60:
        return "C"
    elif average >= 50:
        return "D"
    else:
        return "F"


class StudentProfile:
    """
    Stores personal details about a student.

    Kept separate from grade calculation logic because student profile
    data (name, age) is a different concern from academic performance.
    This class is used in main.py to enrich the student report with
    profile information alongside the calculated grade.
    """

    def __init__(self, name: str, age: int) -> None:
        """
        Initialises the student profile with a name and age.

        These are stored as instance variables so other methods
        on this class can access them via self.
        """
        self.name = name
        self.age = age

    def get_summary(self) -> str:
        """
        Returns a readable one-line summary of the student's profile.

        Used by get_student_report in main.py to include profile
        information in the final report dictionary.
        """
        return f"{self.name}, age {self.age}"


def get_today_date() -> str:
    """
    Returns today's date as a formatted string (YYYY-MM-DD).

    This function is intentionally never called by any other function
    in the project. It exists to demonstrate orphan function detection
    in the Neo4j knowledge graph — a node with no incoming CALLS edges.
    """
    return date.today().isoformat()
