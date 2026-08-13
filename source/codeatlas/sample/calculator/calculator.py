# A simple calculator script.
# This file exists as a sample repository for testing CodeAtlas indexing,
# embedding, and question answering on a small, well-understood codebase.


def add(a: float, b: float) -> float:
    """
    Returns the sum of two numbers.

    Used to combine two numeric values into a single total.
    For example, adding item prices to get a subtotal.
    """
    return a + b


def subtract(a: float, b: float) -> float:
    """
    Returns the difference between two numbers.

    Subtracts b from a. Used when calculating the remaining
    balance after a deduction, discount, or payment.
    """
    return a - b


def multiply(a: float, b: float) -> float:
    """
    Returns the product of two numbers.

    Used to calculate totals where a unit price is multiplied
    by a quantity, for example pricing 5 items at 3.00 each.
    """
    return a * b


if __name__ == "__main__":
    # Example usage of the calculator functions
    print("Addition of 5 and 3:", add(5, 3))          # Output: 8
    print("Subtraction of 5 from 10:", subtract(10, 5))  # Output: 5
    print("Multiplication of 4 and 2.5:", multiply(4, 2.5))  # Output: 10.0