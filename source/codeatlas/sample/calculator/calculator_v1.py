# Class-based version of the calculator.
# Same three operations as calculator.py but organised inside a class.
# This file exists to test how the CodeAtlas AST crawler handles
# functions that live inside a class rather than at the top level.


class Calculator:
    """
    A simple calculator class that groups arithmetic operations together.

    Grouping related functions into a class makes the code easier to
    organise and extend. For example, you could later subclass this
    to add scientific or financial calculator variants.
    """

    def add(self, a: float, b: float) -> float:
        """
        Returns the sum of two numbers.

        Used to combine two numeric values into a single total.
        For example, adding item prices to get a subtotal.
        """
        return a + b

    def subtract(self, a: float, b: float) -> float:
        """
        Returns the difference between two numbers.

        Subtracts b from a. Used when calculating the remaining
        balance after a deduction, discount, or payment.
        """
        return a - b

    def multiply(self, a: float, b: float) -> float:
        """
        Returns the product of two numbers.

        Used to calculate totals where a unit price is multiplied
        by a quantity, for example pricing 5 items at 3.00 each.
        """
        return a * b


if __name__ == "__main__":
    # Example usage of the Calculator class
    calc = Calculator()
    print("Addition of 5 and 3:", calc.add(5, 3))
    print("Subtraction of 5 from 10:", calc.subtract(10, 5))
    print("Multiplication of 4 and 2.5:", calc.multiply(4, 2.5))
