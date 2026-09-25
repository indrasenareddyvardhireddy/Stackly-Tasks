"""
ATM Simulation System

"""

balance = 10000.00

CORRECT_PIN = "1234"

MAX_ATTEMPTS = 3


def authenticate():
    """Authenticate the user using PIN."""

    attempts = 0

    while attempts < MAX_ATTEMPTS:

        pin = input("Enter your 4-digit PIN: ").strip()

        if not pin:
            print("PIN cannot be empty.")
            continue

        if len(pin) != 4 or not pin.isdigit():
            print("PIN must contain exactly 4 digits.")
            continue

        if pin == CORRECT_PIN:
            print("Login successful.")
            return True

        attempts += 1

        remaining = MAX_ATTEMPTS - attempts

        if remaining > 0:
            print(
                f"Incorrect PIN. "
                f"Attempts remaining: {remaining}"
            )

    print("Maximum PIN attempts exceeded.")
    return False


def check_balance():
    """Display current balance."""

    print(f"\nAvailable Balance: ₹{balance:.2f}")


def get_positive_amount(message):
    """Get a valid positive amount."""

    while True:

        amount_input = input(message).strip()

        if not amount_input:
            print("Amount cannot be empty.")
            continue

        try:
            amount = float(amount_input)

            if amount <= 0:
                print(
                    "Amount must be greater than zero."
                )
                continue

            return amount

        except ValueError:
            print("Please enter a valid number.")


def deposit():
    """Deposit money into the account."""

    global balance

    amount = get_positive_amount(
        "Enter deposit amount: "
    )

    balance += amount

    print(
        f"₹{amount:.2f} deposited successfully."
    )

    check_balance()


def withdraw():
    """Withdraw money from the account."""

    global balance

    amount = get_positive_amount(
        "Enter withdrawal amount: "
    )

    if amount > balance:

        print("Insufficient balance.")
        return

    balance -= amount

    print(
        f"₹{amount:.2f} withdrawn successfully."
    )

    check_balance()


def main():
    """Main ATM application."""

    print("========== WELCOME TO ATM ==========")

    if not authenticate():
        return

    while True:

        print("\n========== ATM MENU ==========")
        print("1. Check Balance")
        print("2. Deposit")
        print("3. Withdraw")
        print("4. Exit")

        choice = input(
            "Enter your choice: "
        ).strip()

        if choice == "1":

            check_balance()

        elif choice == "2":

            deposit()

        elif choice == "3":

            withdraw()

        elif choice == "4":

            print(
                "Thank you for using the ATM."
            )
            break

        else:

            print(
                "Invalid choice. Please select 1-4."
            )


if __name__ == "__main__":
    main()