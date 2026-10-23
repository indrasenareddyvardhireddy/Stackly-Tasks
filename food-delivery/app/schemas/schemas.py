from datetime import datetime, time
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

PHONE = r"^\d{10}$"
PINCODE = r"^\d{6}$"
Lat = Field(..., ge=-90, le=90)
Lng = Field(..., ge=-180, le=180)


# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., pattern=PHONE)
    password: str = Field(..., min_length=6, max_length=72)
    role: Literal["customer", "restaurant_owner", "delivery_partner", "admin"]
    vehicle_type: Optional[Literal["Bike", "Scooter", "Bicycle"]] = None
    vehicle_number: Optional[str] = Field(None, min_length=4, max_length=30)

    @model_validator(mode="after")
    def partner_needs_vehicle(self):
        if self.role == "delivery_partner" and not (self.vehicle_type and self.vehicle_number):
            raise ValueError("vehicle_type and vehicle_number are required for delivery partners")
        return self


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# ---------- Restaurant ----------
class RestaurantIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    cuisine_type: str = Field(..., min_length=1, max_length=80)
    address: str = Field(..., min_length=1, max_length=255)
    latitude: float = Lat
    longitude: float = Lng
    opening_time: time
    closing_time: time
    delivery_radius_km: float = Field(5, gt=0, le=50)
    min_order_value: float = Field(0, ge=0)
    avg_preparation_minutes: int = Field(20, ge=1, le=240)

    @model_validator(mode="after")
    def times(self):
        if self.opening_time >= self.closing_time:
            raise ValueError("opening_time must be before closing_time")
        return self


class RestaurantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    cuisine_type: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None
    delivery_radius_km: Optional[float] = Field(None, gt=0, le=50)
    min_order_value: Optional[float] = Field(None, ge=0)
    avg_preparation_minutes: Optional[int] = Field(None, ge=1, le=240)
    is_active: Optional[bool] = None


class OpenStatusIn(BaseModel):
    is_temporarily_closed: bool


class CategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class MenuItemIn(BaseModel):
    category_id: int
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    is_veg: bool = True
    packaging_charge: float = Field(0, ge=0)
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    is_veg: Optional[bool] = None
    packaging_charge: Optional[float] = Field(None, ge=0)


class AvailabilityIn(BaseModel):
    is_available: bool


# ---------- Address ----------
class AddressIn(BaseModel):
    label: Literal["Home", "Work", "Other"]
    address_line: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=80)
    pincode: str = Field(..., pattern=PINCODE)
    latitude: float = Lat
    longitude: float = Lng
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: Optional[Literal["Home", "Work", "Other"]] = None
    address_line: Optional[str] = Field(None, min_length=1, max_length=255)
    city: Optional[str] = None
    pincode: Optional[str] = Field(None, pattern=PINCODE)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


# ---------- Cart ----------
class CartItemIn(BaseModel):
    menu_item_id: int
    quantity: int = Field(1, ge=1, le=10)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, le=10)


class ApplyCouponIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)


# ---------- Coupon ----------
class CouponIn(BaseModel):
    code: str = Field(..., min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    description: Optional[str] = None
    discount_type: Literal["Percentage", "Flat"]
    discount_value: float = Field(..., gt=0)
    max_discount: Optional[float] = Field(None, gt=0)
    min_order_value: float = Field(0, ge=0)
    restaurant_id: Optional[int] = None
    valid_from: datetime
    valid_to: datetime
    total_usage_limit: Optional[int] = Field(None, ge=1)
    per_user_limit: Optional[int] = Field(None, ge=1)
    first_order_only: bool = False

    @model_validator(mode="after")
    def rules(self):
        if self.discount_type == "Percentage" and not (1 <= self.discount_value <= 100):
            raise ValueError("Percentage coupons must have discount_value between 1 and 100")
        if self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self


class CouponUpdate(BaseModel):
    description: Optional[str] = None
    discount_value: Optional[float] = Field(None, gt=0)
    max_discount: Optional[float] = Field(None, gt=0)
    min_order_value: Optional[float] = Field(None, ge=0)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    total_usage_limit: Optional[int] = Field(None, ge=1)
    per_user_limit: Optional[int] = Field(None, ge=1)
    first_order_only: Optional[bool] = None


# ---------- Orders ----------
class OrderIn(BaseModel):
    address_id: int
    payment_method: Literal["COD", "Online"]
    tip_amount: float = Field(0, ge=0)


class AcceptIn(BaseModel):
    estimated_preparation_minutes: int = Field(..., ge=1, le=240)


class RejectIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255)


class CancelIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


# ---------- Partner ----------
class AvailabilityToggleIn(BaseModel):
    is_online: bool


class LocationIn(BaseModel):
    latitude: float = Lat
    longitude: float = Lng


class DeliverIn(BaseModel):
    otp: str = Field(..., pattern=r"^\d{4}$")


# ---------- Rating ----------
class RatingIn(BaseModel):
    restaurant_rating: int = Field(..., ge=1, le=5)
    partner_rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)
