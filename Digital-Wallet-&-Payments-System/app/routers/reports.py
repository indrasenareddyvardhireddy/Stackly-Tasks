from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin, require_merchant, require_user
from app.database import get_db
from app.models import User
from app.services import reports
from app.utils.common import jsonable

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/admin-dashboard")
def admin_dashboard(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return jsonable(reports.admin_dashboard(db))


@router.get("/ledger-summary")
def ledger_summary(from_date: Optional[date] = None, to_date: Optional[date] = None,
                   admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return jsonable(reports.ledger_summary(db, from_date, to_date))


@router.get("/merchant-sales")
def merchant_sales(from_date: Optional[date] = None, to_date: Optional[date] = None,
                   merchant: User = Depends(require_merchant), db: Session = Depends(get_db)):
    return jsonable(reports.merchant_sales(db, merchant, from_date, to_date))


@router.get("/my-spending")
def my_spending(month: Optional[str] = None, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return jsonable(reports.my_spending(db, user, month))
