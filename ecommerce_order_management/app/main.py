import logging
from fastapi import FastAPI
from app.routers import auth,categories,products,cart,addresses,orders,payments,returns,reviews,reports,wishlist,coupons

logging.basicConfig(level=logging.INFO)
app=FastAPI(title="E-Commerce Order Management System",version="1.0.0")

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(addresses.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(returns.router)
app.include_router(reviews.router)
app.include_router(reports.router)
app.include_router(wishlist.router)
app.include_router(coupons.router)

@app.get("/")
def root():
    return {"message":"E-Commerce Order Management API","docs":"/docs"}

@app.get("/health")
def health():
    return {"status":"healthy"}
