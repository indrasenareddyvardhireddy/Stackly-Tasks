import enum

from sqlalchemy import Enum as SAEnum


class Role(str, enum.Enum):
    ADMIN = "Admin"
    AGENT = "Agent"
    CUSTOMER = "Customer"


class Availability(str, enum.Enum):
    ONLINE = "Online"
    OFFLINE = "Offline"


# Declaration order matters: MySQL sorts ENUM columns by this order (Low < ... < Urgent)
class Priority(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class TicketStatus(str, enum.Enum):
    OPEN = "Open"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    WAITING = "Waiting on Customer"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


# Tickets counting toward an agent's workload
OPEN_STATUSES = [TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]
# Tickets whose SLA clock is still relevant
ACTIVE_STATUSES = [TicketStatus.OPEN] + OPEN_STATUSES
FINISHED_STATUSES = [TicketStatus.RESOLVED, TicketStatus.CLOSED]


def sa_enum(enum_cls, name: str):
    """Store the enum *values* (e.g. 'In Progress') in a native MySQL ENUM column."""
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e], native_enum=True)
