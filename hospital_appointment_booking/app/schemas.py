from datetime import date, time
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str
    password: str = Field(min_length=8)
    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        if len(v) != 10 or not v.isdigit(): raise ValueError("Phone must be exactly 10 digits")
        return v

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str
    role: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class DepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None

class DoctorIn(BaseModel):
    user_id: int
    name: str
    department_id: int
    specialization: str
    qualification: str
    experience_years: int = Field(ge=0)
    consultation_fee: float = Field(gt=0)
    slot_duration_minutes: int = Field(default=15)
    is_active: bool = True
    @field_validator("slot_duration_minutes")
    @classmethod
    def duration_valid(cls, v):
        if v not in (10, 15, 20, 30): raise ValueError("Slot duration must be 10, 15, 20, or 30")
        return v

class ScheduleIn(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None

class LeaveIn(BaseModel):
    leave_date: date
    reason: str | None = None

class AppointmentIn(BaseModel):
    doctor_id: int
    appointment_date: date
    slot_time: time
    reason: str = Field(min_length=3, max_length=2000)

class RescheduleIn(BaseModel):
    appointment_date: date
    slot_time: time

class ConsultationIn(BaseModel):
    symptoms: str
    diagnosis: str
    prescription: str | None = None
    advice: str | None = None
    follow_up_date: date | None = None

class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class AdminCreateDoctorIn(BaseModel):
    # Login account details
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str
    password: str = Field(min_length=8)

    # Doctor profile details
    department_id: int
    specialization: str = Field(min_length=2)
    qualification: str = Field(min_length=2)
    experience_years: int = Field(ge=0)
    consultation_fee: float = Field(gt=0)
    slot_duration_minutes: int = 15
    is_active: bool = True

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if len(value) != 10 or not value.isdigit():
            raise ValueError("Phone must contain exactly 10 digits")
        return value

    @field_validator("slot_duration_minutes")
    @classmethod
    def validate_slot_duration(cls, value):
        if value not in (10, 15, 20, 30):
            raise ValueError("Slot duration must be 10, 15, 20, or 30 minutes")
        return value
