# Entry point for the grade calculator.
# Imports calculation utilities and the StudentProfile class from utils.py.
# The import line is what creates the graph edge between this file and
# utils.py in the Neo4j knowledge graph.

from utils import calculate_average, calculate_grade, StudentProfile

# Module-level constants — these are global variables tagged to main.py in Neo4j.
# Any function in this file can use these without receiving them as parameters.
DEFAULT_PASS_MARK = 50
DEFAULT_AGE = 18

# Module-level object — an instance of StudentProfile created at file load time.
# This demonstrates a global variable that is an object of a class defined in utils.py.
# Neo4j captures this as: main.py → HAS_VARIABLE → system_profile
#                          main.py → CALLS → StudentProfile
system_profile = StudentProfile("System", DEFAULT_AGE)


def get_student_report(name: str, age: int, marks: list[float]) -> dict:
    """
    Builds a complete grade report for a single student.

    Creates a StudentProfile for personal details, then calls
    calculate_average and calculate_grade from utils.py to compute
    the academic result. Assembles everything into a report dictionary.
    Uses the module-level DEFAULT_PASS_MARK to flag failing students.
    """
    profile = StudentProfile(name, age)
    average = calculate_average(marks)
    grade = calculate_grade(average)

    return {
        "profile": profile.get_summary(),
        "marks": marks,
        "average": average,
        "grade": grade,
        "passed": average >= DEFAULT_PASS_MARK,
    }


if __name__ == "__main__":
    # Example usage — run this file directly to see a sample report
    report = get_student_report("Alice", 20, [85, 90, 78, 92, 88])
    print(f"Student : {report['profile']}")
    print(f"Marks   : {report['marks']}")
    print(f"Average : {report['average']}")
    print(f"Grade   : {report['grade']}")
    print(f"Passed  : {report['passed']}")
