import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AddMoneySource, OTPPurpose, SimulateStatus
from app.schemas.common import Amount, Otp, Phone, Pin

WEAK_PINS = {"1212", "2580", "1004", "2000", "1122", "6969", "1357", "2468"}


def validate_pin_strength(pin: str) -> str:
    digits = [int(c) for c in pin]
    steps = {digits[i + 1] - digits[i] for i in range(3)}
    if len(set(pin)) == 1 or steps == {1} or steps == {-1} or pin in WEAK_PINS:
        raise ValueError("PIN is too simple (e.g. 1234, 1111, 0000). Choose a harder PIN")
    return pin


class KYCRequest(BaseModel):
    pan_number: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    aadhaar_last4: str = Field(pattern=r"^\d{4}$")
    full_name: str = Field(min_length=2, max_length=100)
    date_of_birth: date

    @field_validator("date_of_birth")
    @classmethod
    def adult(cls, v):
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError("You must be at least 18 years old")
        return v


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class SetPinRequest(BaseModel):
    pin: Pin

    @field_validator("pin")
    @classmethod
    def strong(cls, v):
        return validate_pin_strength(v)


class ChangePinRequest(BaseModel):
    old_pin: Pin
    new_pin: Pin

    @field_validator("new_pin")
    @classmethod
    def strong(cls, v):
        return validate_pin_strength(v)


class ResetPinRequest(BaseModel):
    otp: Otp
    new_pin: Pin

    @field_validator("new_pin")
    @classmethod
    def strong(cls, v):
        return validate_pin_strength(v)


class OTPSendRequest(BaseModel):
    purpose: OTPPurpose


class OTPVerifyRequest(BaseModel):
    purpose: OTPPurpose
    otp: Otp


class AddMoneyRequest(BaseModel):
    amount: Amount
    source: AddMoneySource
    simulate_status: SimulateStatus = SimulateStatus.SUCCESS


class TransferRequest(BaseModel):
    receiver_phone: Phone
    amount: Amount
    note: Optional[str] = Field(default=None, max_length=255)
    pin: Pin
    otp: Optional[Otp] = None


class MerchantPaymentRequest(BaseModel):
    merchant_code: str = Field(pattern=r"^MER-\d{4,}$")
    amount: Amount
    pin: Pin
    note: Optional[str] = Field(default=None, max_length=255)


class RefundRequest(BaseModel):
    amount: Amount
    reason: Optional[str] = Field(default=None, max_length=255)


class MoneyRequestCreate(BaseModel):
    payer_phone: Phone
    amount: Amount
    note: Optional[str] = Field(default=None, max_length=255)


class MoneyRequestPay(BaseModel):
    pin: Pin
    otp: Optional[Otp] = None


class BankAccountCreate(BaseModel):
    account_holder_name: str = Field(min_length=2, max_length=100)
    account_number: str = Field(pattern=r"^\d{9,18}$")
    ifsc_code: str = Field(pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")
    bank_name: str = Field(min_length=2, max_length=100)
    is_primary: bool = False
    otp: Otp


class WithdrawalRequest(BaseModel):
    bank_account_id: int
    amount: Amount
    pin: Pin
