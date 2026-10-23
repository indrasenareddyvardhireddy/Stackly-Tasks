from sqlalchemy import inspect


def row_dict(obj, exclude=()):
    """Plain dict of a model's columns (FastAPI's encoder handles datetime/time)."""
    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs if c.key not in exclude}


ACTIVE_ORDER_STATUSES = ["Accepted", "Preparing", "Ready for Pickup", "Picked Up", "Out for Delivery"]
