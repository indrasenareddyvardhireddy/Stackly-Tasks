"""
Unit tests for the business rules. They need no MySQL / Redis:
    pytest -q
"""
from decimal import Decimal

from app.utils.billing import calculate_bill
from app.utils.qr import sign_value, verify_value
from app.utils.refund_policy import customer_refund_amount, refund_percentage
from app.utils.seat_rules import find_single_gap_violations


# ---------------------------------------------------------------- bill
def test_bill_two_tickets():
    bill = calculate_bill([Decimal("200"), Decimal("200")])
    assert bill["ticket_total"] == Decimal("400.00")
    assert bill["convenience_fee"] == Decimal("60.00")          # Rs.30 per ticket
    assert bill["gst_amount"] == Decimal("82.80")               # 18% of (400 + 60)
    assert bill["grand_total"] == Decimal("542.80")


def test_bill_single_ticket_rounding():
    bill = calculate_bill([Decimal("149.99")])
    assert bill["gst_amount"] == Decimal("32.40")               # 18% of 179.99 = 32.3982
    assert bill["grand_total"] == bill["ticket_total"] + bill["convenience_fee"] + bill["gst_amount"]


# ---------------------------------------------------------------- cancellation policy
def test_refund_policy_bands():
    assert refund_percentage(48) == Decimal("1.00")
    assert refund_percentage(24.01) == Decimal("1.00")
    assert refund_percentage(24) == Decimal("0.50")
    assert refund_percentage(5) == Decimal("0.50")
    assert refund_percentage(2) == Decimal("0.50")
    assert refund_percentage(1.99) is None
    assert refund_percentage(-1) is None


def test_refund_amount_excludes_fee_and_gst():
    # ticket_total 400 -> 100% = 400, 50% = 200 (fee + GST are never refunded)
    assert customer_refund_amount(Decimal("400"), 30) == Decimal("400.00")
    assert customer_refund_amount(Decimal("400"), 10) == Decimal("200.00")
    assert customer_refund_amount(Decimal("400"), 1) is None


# ---------------------------------------------------------------- single empty seat rule
ROW = [1, 2, 3, 4, 5, 6, 7, 8]      # seat ids of one row, in seat order


def test_single_gap_next_to_taken_seat_is_rejected():
    # I pick 1,2,3 ; seat 5 is taken -> seat 4 would be a lonely empty seat
    assert find_single_gap_violations(ROW, {1, 2, 3}, {5}) == [4]


def test_single_gap_on_the_other_side():
    assert find_single_gap_violations(ROW, {6, 7, 8}, {4}) == [5]


def test_no_gap_when_seats_are_adjacent_to_taken_seat():
    assert find_single_gap_violations(ROW, {1, 2, 3, 4}, {5}) == []


def test_gap_of_two_empty_seats_is_allowed():
    assert find_single_gap_violations(ROW, {1, 2}, {5}) == []


def test_row_edge_is_not_a_taken_seat():
    assert find_single_gap_violations(ROW, {2, 3}, set()) == []


def test_free_seat_between_two_of_my_seats_is_allowed():
    assert find_single_gap_violations(ROW, {1, 3}, set()) == []


# ---------------------------------------------------------------- signed QR
def test_qr_roundtrip_and_tamper():
    value = sign_value("BKG-20261020-0001", "secret")
    assert verify_value(value, "secret") == "BKG-20261020-0001"
    assert verify_value(value, "other-secret") is None                       # wrong key
    assert verify_value("BKG-20261020-0002." + value.split(".")[1], "secret") is None   # forged number
    assert verify_value("garbage", "secret") is None
    assert verify_value("", "secret") is None


# ---------------------------------------------------------------- Razorpay signatures
from app.utils.razorpay_sig import payment_signature, verify_payment_signature, verify_webhook_signature


def test_razorpay_payment_signature():
    sig = payment_signature("order_ABC", "pay_XYZ", "key_secret")
    assert verify_payment_signature("order_ABC", "pay_XYZ", sig, "key_secret")
    assert not verify_payment_signature("order_ABC", "pay_OTHER", sig, "key_secret")     # different payment
    assert not verify_payment_signature("order_ABC", "pay_XYZ", sig, "wrong_secret")     # wrong key
    assert not verify_payment_signature("order_ABC", "pay_XYZ", "", "key_secret")        # missing signature
    assert not verify_payment_signature("order_ABC", "pay_XYZ", "deadbeef", "key_secret")


def test_razorpay_webhook_signature():
    import hashlib, hmac
    body = b'{"event":"payment.captured"}'
    good = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, good, "whsec")
    assert not verify_webhook_signature(body + b" ", good, "whsec")                      # tampered body
    assert not verify_webhook_signature(body, good, "other")
    assert not verify_webhook_signature(body, "", "whsec")
    assert not verify_webhook_signature(body, good, "")                                  # secret not configured
