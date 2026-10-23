from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import CUSTOMER, get_current_user, require_roles
from app.database import get_db
from app.models import Rating, Restaurant, User
from app.schemas.schemas import RatingIn
from app.services.order_service import get_order_or_404
from app.services.restaurant_service import get_restaurant_or_404
from app.utils.common import row_dict

router = APIRouter(tags=["Ratings"])


@router.post("/orders/{order_id}/rating", status_code=201)
def rate_order(order_id: int, data: RatingIn, db: Session = Depends(get_db),
               user: User = Depends(require_roles(CUSTOMER))):
    order = get_order_or_404(db, order_id, lock=True)
    if order.customer_id != user.id:
        raise HTTPException(403, "Only the order's customer can rate it")
    if order.status != "Delivered":
        raise HTTPException(400, "You can rate an order only after it is Delivered")
    if db.query(Rating).filter(Rating.order_id == order.id).first():
        raise HTTPException(409, "This order has already been rated")
    rating = Rating(order_id=order.id, customer_id=user.id, restaurant_id=order.restaurant_id,
                    partner_id=order.delivery_partner_id, **data.model_dump())
    db.add(rating)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This order has already been rated")
    avg, count = db.query(func.avg(Rating.restaurant_rating), func.count(Rating.id)).filter(
        Rating.restaurant_id == order.restaurant_id).one()
    restaurant = db.get(Restaurant, order.restaurant_id)
    restaurant.average_rating = round(float(avg), 2)  # auto-update average
    restaurant.rating_count = count
    db.commit()
    return row_dict(rating)


@router.get("/restaurants/{restaurant_id}/ratings")
def restaurant_ratings(restaurant_id: int, skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
                       db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    r = get_restaurant_or_404(db, restaurant_id)
    q = db.query(Rating).filter(Rating.restaurant_id == restaurant_id)
    return {"average_rating": r.average_rating, "total": q.count(), "skip": skip, "limit": limit,
            "items": [{k: v for k, v in row_dict(x).items() if k not in ("partner_id", "customer_id")}
                      for x in q.order_by(Rating.id.desc()).offset(skip).limit(limit)]}
