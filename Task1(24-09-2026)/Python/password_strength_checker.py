class WeakPasswordError(Exception):
    """Custom exception for weak passwords."""
    pass


def check_password(password):
    if len(password) < 8:
        raise WeakPasswordError(
            "Password must contain at least 8 characters."
        )

    if not any(char.isupper() for char in password):
        raise WeakPasswordError(
            "Password must contain at least one uppercase letter."
        )

    if not any(char.islower() for char in password):
        raise WeakPasswordError(
            "Password must contain at least one lowercase letter."
        )

    if not any(char.isdigit() for char in password):
        raise WeakPasswordError(
            "Password must contain at least one number."
        )

    if not any(char in "!@#$%^&*()_+-=" for char in password):
        raise WeakPasswordError(
            "Password must contain at least one special character."
        )

    return True


def main():
    print("===== Password Strength Checker =====")

    try:
        password = input("Enter your password: ")

        check_password(password)

        print("Password is Strong.")

    except WeakPasswordError as error:
        print(f"Weak Password: {error}")

    except Exception as error:
        print(f"Unexpected error: {error}")


if __name__ == "__main__":
    main()