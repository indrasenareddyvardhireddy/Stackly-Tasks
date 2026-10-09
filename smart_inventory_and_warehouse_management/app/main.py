from fastapi import FastAPI
from app.routers import auth,catalog,warehouse,inventory,suppliers,customers,purchase_orders,sales_orders,returns,reports,audit,bonus
app=FastAPI(title="Smart Inventory & Warehouse Management System",version="1.0.0",description="End-to-end inventory, warehouse, purchasing, sales, returns, reporting and audit backend.")
app.include_router(auth.router);app.include_router(catalog.router);app.include_router(warehouse.router);app.include_router(inventory.router);app.include_router(suppliers.router);app.include_router(customers.router);app.include_router(purchase_orders.router);app.include_router(sales_orders.router);app.include_router(returns.router);app.include_router(reports.router);app.include_router(audit.router);app.include_router(bonus.router)
@app.get("/",tags=["Health"])
def root():return {"message":"Smart Inventory API is running"}
@app.get("/health",tags=["Health"])
def health():return {"status":"ok"}
