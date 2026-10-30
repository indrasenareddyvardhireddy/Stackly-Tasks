import secrets
import string


def seat_label(row_label: str, seat_number: int) -> str:
    return f"{row_label}{seat_number}"


def row_sort_key(row_label: str):
    """A, B, ... Z, AA, AB ... in natural order."""
    return (len(row_label), row_label)


def random_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def row_range(start: str, end: str):
    """'A','E' -> ['A','B','C','D','E'] (single letters only)."""
    return [chr(c) for c in range(ord(start), ord(end) + 1)]
