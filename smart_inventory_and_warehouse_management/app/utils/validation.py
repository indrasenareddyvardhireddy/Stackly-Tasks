import re
from fastapi import HTTPException

def validate_phone(phone:str):
    if not re.fullmatch(r"[6-9][0-9]{9}", phone): raise HTTPException(422,"Phone must be 10 digits and start with 6-9")

def validate_gst(gst:str):
    if not re.fullmatch(r"[0-9A-Z]{15}", gst): raise HTTPException(422,"GST number must contain 15 alphanumeric uppercase characters")
