"""HMAC signed QR values: '<booking_number>.<signature>'."""
import hashlib
import hmac
from typing import Optional


def _signature(value: str, secret: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]


def sign_value(booking_number: str, secret: str) -> str:
    return f"{booking_number}.{_signature(booking_number, secret)}"


def verify_value(qr_value: str, secret: str) -> Optional[str]:
    """Returns the booking number if the signature is valid, otherwise None."""
    if not qr_value or "." not in qr_value:
        return None
    number, sig = qr_value.rsplit(".", 1)
    if hmac.compare_digest(sig, _signature(number, secret)):
        return number
    return None
