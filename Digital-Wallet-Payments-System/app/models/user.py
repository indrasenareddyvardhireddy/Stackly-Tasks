from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, enum_col
from app.models.enums import KYCStatus, OTPPurpose, Role


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(10), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(enum_col(Role), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    pin_hash = Column(String(255), nullable=True)
    pin_failed_attempts = Column(Integer, nullable=False, default=0)
    pin_locked_until = Column(DateTime, nullable=True)

    wallet = relationship("Wallet", back_populates="owner", uselist=False)
    merchant = relationship("Merchant", back_populates="user", uselist=False)
    kyc = relationship("KYC", back_populates="user", uselist=False, foreign_keys="KYC.user_id")
    bank_accounts = relationship("BankAccount", back_populates="user")
    requests_sent = relationship("MoneyRequest", back_populates="requester", foreign_keys="MoneyRequest.requester_id")
    requests_received = relationship("MoneyRequest", back_populates="payer", foreign_keys="MoneyRequest.payer_id")


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    business_name = Column(String(150), nullable=False)
    business_category = Column(String(80), nullable=False)
    merchant_code = Column(String(20), unique=True, nullable=False)

    user = relationship("User", back_populates="merchant")
    payments = relationship("MerchantPayment", back_populates="merchant")


class KYC(Base, TimestampMixin):
    __tablename__ = "kyc"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    pan_number = Column(String(10), unique=True, nullable=False)
    aadhaar_last4 = Column(String(4), nullable=False)
    full_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    status = Column(enum_col(KYCStatus), nullable=False, default=KYCStatus.PENDING)
    rejection_reason = Column(String(255), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="kyc", foreign_keys=[user_id])


class OTP(Base, TimestampMixin):
    __tablename__ = "otps"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    purpose = Column(enum_col(OTPPurpose), nullable=False)
    otp_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    is_used = Column(Boolean, nullable=False, default=False)
