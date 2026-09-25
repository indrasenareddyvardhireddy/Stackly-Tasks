"""
Mini Expense Tracker using File Handling

Data is stored in expenses.csv.
"""

import csv
from pathlib import Path
from datetime import datetime


FILE_NAME = Path("expenses.csv")

FIELDS = [
    "id",
    "date",
    "category",
    "description",
    "amount"
]


def initialize_file():
    """Create the CSV file if it does not exist."""

    if not FILE_NAME.exists():
        with FILE_NAME.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()


def get_non_empty_input(message):
    """Get input and prevent empty values."""

    while True:
        value = input(message).strip()

        if value:
            return value

        print("Input cannot be empty. Please try again.")


def get_valid_date():
    """Validate date format."""

    while True:
        date_input = input("Enter date (YYYY-MM-DD): ").strip()

        if not date_input:
            print("Date cannot be empty.")
            continue

        try:
            datetime.strptime(date_input, "%Y-%m-%d")
            return date_input

        except ValueError:
            print("Invalid date. Use YYYY-MM-DD format.")


def get_valid_amount():
    """Validate expense amount."""

    while True:
        amount_input = input("Enter amount: ").strip()

        if not amount_input:
            print("Amount cannot be empty.")
            continue

        try:
            amount = float(amount_input)

            if amount <= 0:
                print("Amount must be greater than zero.")
                continue

            return amount

        except ValueError:
            print("Please enter a valid number.")


def read_expenses():
    """Read all expenses from the CSV file."""

    initialize_file()

    try:
        with FILE_NAME.open("r", newline="") as file:
            return list(csv.DictReader(file))

    except (OSError, csv.Error) as error:
        print(f"Error reading file: {error}")
        return []


def write_expenses(expenses):
    """Write expenses back to the CSV file."""

    try:
        with FILE_NAME.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(expenses)

        return True

    except OSError as error:
        print(f"Error writing file: {error}")
        return False


def add_expense():
    """Add a new expense."""

    expenses = read_expenses()

    expense_ids = [
        int(expense["id"])
        for expense in expenses
        if expense["id"].isdigit()
    ]

    new_id = max(expense_ids, default=0) + 1

    date = get_valid_date()
    category = get_non_empty_input("Enter category: ")
    description = get_non_empty_input("Enter description: ")
    amount = get_valid_amount()

    expense = {
        "id": str(new_id),
        "date": date,
        "category": category,
        "description": description,
        "amount": f"{amount:.2f}"
    }

    expenses.append(expense)

    if write_expenses(expenses):
        print("Expense added successfully.")


def view_expenses():
    """Display all expenses."""

    expenses = read_expenses()

    if not expenses:
        print("No expenses found.")
        return

    print("\n" + "=" * 80)
    print("ALL EXPENSES")
    print("=" * 80)

    print(
        f"{'ID':<5}"
        f"{'Date':<15}"
        f"{'Category':<15}"
        f"{'Description':<25}"
        f"{'Amount':<10}"
    )

    print("-" * 80)

    for expense in expenses:
        print(
            f"{expense['id']:<5}"
            f"{expense['date']:<15}"
            f"{expense['category']:<15}"
            f"{expense['description']:<25}"
            f"₹{expense['amount']:<9}"
        )


def get_expense_by_id(expenses, expense_id):
    """Find an expense by ID."""

    for expense in expenses:
        if expense["id"] == expense_id:
            return expense

    return None


def update_expense():
    """Update an existing expense."""

    expenses = read_expenses()

    if not expenses:
        print("No expenses available.")
        return

    view_expenses()

    expense_id = get_non_empty_input(
        "\nEnter expense ID to update: "
    )

    expense = get_expense_by_id(expenses, expense_id)

    if expense is None:
        print("Expense not found.")
        return

    print("\nEnter new details:")

    expense["date"] = get_valid_date()
    expense["category"] = get_non_empty_input("Enter category: ")
    expense["description"] = get_non_empty_input(
        "Enter description: "
    )

    amount = get_valid_amount()
    expense["amount"] = f"{amount:.2f}"

    if write_expenses(expenses):
        print("Expense updated successfully.")


def delete_expense():
    """Delete an expense."""

    expenses = read_expenses()

    if not expenses:
        print("No expenses available.")
        return

    view_expenses()

    expense_id = get_non_empty_input(
        "\nEnter expense ID to delete: "
    )

    expense = get_expense_by_id(expenses, expense_id)

    if expense is None:
        print("Expense not found.")
        return

    expenses.remove(expense)

    if write_expenses(expenses):
        print("Expense deleted successfully.")


def show_total():
    """Calculate total expenses."""

    expenses = read_expenses()

    total = 0

    for expense in expenses:
        try:
            total += float(expense["amount"])
        except ValueError:
            continue

    print(f"\nTotal Expenses: ₹{total:.2f}")


def main():
    """Main menu."""

    initialize_file()

    while True:

        print("\n========== EXPENSE TRACKER ==========")
        print("1. Add Expense")
        print("2. View Expenses")
        print("3. Update Expense")
        print("4. Delete Expense")
        print("5. Show Total Expenses")
        print("6. Exit")

        choice = input("Enter your choice: ").strip()

        if choice == "1":
            add_expense()

        elif choice == "2":
            view_expenses()

        elif choice == "3":
            update_expense()

        elif choice == "4":
            delete_expense()

        elif choice == "5":
            show_total()

        elif choice == "6":
            print("Thank you for using Expense Tracker.")
            break

        else:
            print("Invalid choice. Please select 1-6.")


if __name__ == "__main__":
    main()