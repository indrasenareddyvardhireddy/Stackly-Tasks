"""Pure-logic tests (no database needed): python -m pytest -q"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.coupon_service import compute_discount
from app.utils.geo import haversine_km, travel_minutes
from app.utils.pricing import calculate_bill, delivery_fee, partner_earning

OFF_PEAK = datetime(2026, 10, 21, 16, 0)
PEAK = datetime(2026, 10, 21, 13, 0)


def test_haversine_zero_and_known_distance():
    assert haversine_km(17.4486, 78.3908, 17.4486, 78.3908) == pytest.approx(0, abs=1e-9)
    # Hyderabad -> Secunderabad is roughly 8-10 km straight-line
    assert 7 < haversine_km(17.4486, 78.3908, 17.4399, 78.4983) < 13


def test_travel_time_at_20kmph():
    assert travel_minutes(10) == pytest.approx(30)


@pytest.mark.parametrize("km,fee", [(1, 20), (3, 20), (3.1, 28), (4, 28), (4.01, 36), (6.5, 52)])
def test_delivery_fee_rounds_extra_km_up(km, fee):
    assert delivery_fee(km, OFF_PEAK) == fee


def test_surge_pricing_bonus():
    assert delivery_fee(2, PEAK) == 30.0


def test_bill_formula():
    bill = calculate_bill(item_total=500, discount=100, packaging=10, distance_km=5, tip=20, at=OFF_PEAK)
    # taxable 400 -> gst 20 ; delivery 20 + 2*8 = 36 ; platform 5
    assert bill["gst_amount"] == 20
    assert bill["delivery_fee"] == 36
    assert bill["grand_total"] == 400 + 10 + 36 + 5 + 20 + 20


def test_partner_earnings_ignore_coupons():
    assert partner_earning(4, tip=10) == 25 + 24 + 10


def make(**kw):
    base = dict(discount_type="Percentage", discount_value=20, max_discount=100)
    return SimpleNamespace(**{**base, **kw})


def test_percentage_discount_is_capped():
    assert compute_discount(make(), 1000) == 100
    assert compute_discount(make(), 300) == 60


def test_flat_discount_never_exceeds_item_total():
    assert compute_discount(make(discount_type="Flat", discount_value=150, max_discount=None), 99) == 99
