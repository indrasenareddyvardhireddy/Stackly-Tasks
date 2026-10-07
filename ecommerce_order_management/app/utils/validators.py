import re
from fastapi import HTTPException

def validate_phone(value: str) -> str:
    if not re.fullmatch(r"[6-9][0-9]{9}", value):
        raise HTTPException(422, "Phone must be 10 digits and start with 6, 7, 8, or 9")
    return value

def validate_pincode(value: str) -> str:
    if not re.fullmatch(r"[0-9]{6}", value):
        raise HTTPException(422, "Pincode must be exactly 6 digits")
    return value
