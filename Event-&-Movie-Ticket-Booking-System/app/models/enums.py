from enum import Enum


class Role(str, Enum):
    ADMIN = "Admin"
    ORGANIZER = "Organizer"
    CUSTOMER = "Customer"
    STAFF = "Staff"


class SeatCategory(str, Enum):
    SILVER = "Silver"
    GOLD = "Gold"
    RECLINER = "Recliner"


class EventCategory(str, Enum):
    MOVIE = "Movie"
    CONCERT = "Concert"
    COMEDY = "Comedy"
    SPORTS = "Sports"
    WORKSHOP = "Workshop"


class AgeRating(str, Enum):
    U = "U"
    UA = "UA"
    A = "A"


class EventStatus(str, Enum):
    DRAFT = "Draft"
    PUBLISHED = "Published"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"


class ShowStatus(str, Enum):
    SCHEDULED = "Scheduled"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"


class BookingStatus(str, Enum):
    PENDING = "Pending Payment"
    CONFIRMED = "Confirmed"
    CANCELLED = "Cancelled"
    EXPIRED = "Expired"


class PaymentMethod(str, Enum):
    UPI = "UPI"
    CARD = "Card"
    NET_BANKING = "Net Banking"


class PaymentStatus(str, Enum):
    SUCCESS = "Success"
    FAILED = "Failed"
    REFUNDED = "Refunded"


class SimulateStatus(str, Enum):
    SUCCESS = "Success"
    FAILED = "Failed"


class RefundReason(str, Enum):
    CUSTOMER = "Customer Cancellation"
    SHOW = "Show Cancellation"
    LATE = "Late Payment"


class SeatState(str, Enum):
    AVAILABLE = "Available"
    LOCKED = "Locked"
    BOOKED = "Booked"
    UNAVAILABLE = "Unavailable"
    YOURS = "Yours"


class WaitlistStatus(str, Enum):
    WAITING = "Waiting"
    NOTIFIED = "Notified"
    CLOSED = "Closed"


class EventSortBy(str, Enum):
    SHOW_DATE = "show_date"
    PRICE = "price"
    TITLE = "title"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


REFUND_PROCESSED = "Processed"
