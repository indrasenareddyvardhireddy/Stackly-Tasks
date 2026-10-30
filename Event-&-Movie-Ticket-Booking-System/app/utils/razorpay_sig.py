"""Razorpay HMAC-SHA256 signature helpers (pure functions)."""
import hashlib
import hmac


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def payment_signature(order_id: str, payment_id: str, secret: str) -> str:
    """Signature Razorpay Checkout returns: HMAC_SHA256(order_id|payment_id, key_secret)."""
    return _hmac_hex(secret, f"{order_id}|{payment_id}".encode())


def verify_payment_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    if not (order_id and payment_id and signature and secret):
        return False
    return hmac.compare_digest(payment_signature(order_id, payment_id, secret), signature)


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """X-Razorpay-Signature = HMAC_SHA256(raw request body, webhook_secret)."""
    if not (signature and secret):
        return False
    return hmac.compare_digest(_hmac_hex(secret, raw_body), signature)
