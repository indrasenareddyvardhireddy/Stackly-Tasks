from fastapi import HTTPException

def warehouse_allowed(user,warehouse_id):
    if user.role=="Warehouse Staff" and user.warehouse_id!=warehouse_id: raise HTTPException(403,"You can act only on your assigned warehouse")
