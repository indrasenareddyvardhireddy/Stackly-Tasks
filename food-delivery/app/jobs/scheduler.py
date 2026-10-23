"""APScheduler jobs - started automatically with the application (see main.py)."""
import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models import Coupon, Delivery, DeliveryPartner, Notification, Order
from app.services import assignment_service
from app.services.order_service import broadcast_order, reject_or_cancel
from app.utils.timeutil import now

log = logging.getLogger("jobs")
AUTO_REJECT_MINUTES = 5
INACTIVE_PARTNER_MINUTES = 10


def _run(fn):
    """Run a job with its own DB session; never let an exception kill the scheduler."""
    def wrapper():
        db = SessionLocal()
        try:
            fn(db)
        except Exception:
            db.rollback()
            log.exception("job %s failed", fn.__name__)
        finally:
            db.close()
    wrapper.__name__ = fn.__name__
    return wrapper


def auto_reject_orders(db):
    cutoff = now() - timedelta(minutes=AUTO_REJECT_MINUTES)
    ids = [o.id for o in db.query(Order.id).filter(Order.status == "Placed", Order.placed_at <= cutoff)]
    for oid in ids:
        order = db.query(Order).filter(Order.id == oid).with_for_update().first()
        if order.status != "Placed":  # restaurant responded in the meantime
            db.rollback()
            continue
        reason = "Restaurant did not respond"
        reject_or_cancel(db, order, "Rejected", None, reason)  # user=None -> changed_by "System"
        db.add(Notification(target_role="customer", user_id=order.customer_id, order_id=order.id,
                            message=f"Your order {order.order_number} was rejected: {reason}. "
                                    f"{'Refund initiated.' if order.payment_status == 'Refunded' else ''}"))
        db.commit()
        broadcast_order(order, f"Your order was automatically rejected: {reason}")


def expire_offers(db):
    assignment_service.expire_offers(db)


def retry_unassigned(db):
    assignment_service.retry_unassigned(db)


def set_inactive_partners_offline(db):
    cutoff = now() - timedelta(minutes=INACTIVE_PARTNER_MINUTES)
    busy = [d.partner_id for d in db.query(Delivery.partner_id).filter(Delivery.status == "Active")]
    q = db.query(DeliveryPartner).filter(DeliveryPartner.is_online.is_(True),
                                         (DeliveryPartner.last_location_at.is_(None)) |
                                         (DeliveryPartner.last_location_at < cutoff))
    for p in q:
        if p.id not in busy:  # never drop a partner mid-delivery
            p.is_online = False
    db.commit()


def deactivate_expired_coupons(db):
    db.query(Coupon).filter(Coupon.is_active.is_(True), Coupon.valid_to < now()).update(
        {"is_active": False}, synchronize_session=False)
    db.commit()


def build_scheduler() -> BackgroundScheduler:
    s = BackgroundScheduler()
    s.add_job(_run(auto_reject_orders), "interval", minutes=1, id="auto_reject", max_instances=1, coalesce=True)
    s.add_job(_run(expire_offers), "interval", seconds=10, id="offer_expiry", max_instances=1, coalesce=True)
    s.add_job(_run(retry_unassigned), "interval", minutes=1, id="unassigned_orders", max_instances=1, coalesce=True)
    s.add_job(_run(set_inactive_partners_offline), "interval", minutes=5, id="inactive_partners",
              max_instances=1, coalesce=True)
    s.add_job(_run(deactivate_expired_coupons), "interval", days=1, id="coupon_expiry", max_instances=1,
              coalesce=True, next_run_time=now())  # also runs once at startup
    return s
