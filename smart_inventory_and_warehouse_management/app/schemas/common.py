from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from decimal import Decimal
from datetime import date, datetime

class ORM(BaseModel):
    model_config=ConfigDict(from_attributes=True)

def positive(v):
    if v <= 0: raise ValueError("must be positive")
    return v

class UserCreate(BaseModel):
    username:str=Field(min_length=3,max_length=100); email:EmailStr; password:str=Field(min_length=8); role:str; warehouse_id:int|None=None
class Login(BaseModel): username:str; password:str
class Token(BaseModel): access_token:str; token_type:str="bearer"
class UserOut(ORM): id:int; username:str; email:EmailStr; role:str; is_active:bool; warehouse_id:int|None

class CategoryCreate(BaseModel): name:str=Field(min_length=1,max_length=100)
class CategoryOut(ORM): id:int; name:str; is_active:bool

class ProductCreate(BaseModel):
    name:str; sku:str; barcode:str|None=None; category_id:int; unit:str; cost_price:Decimal=Field(gt=0); selling_price:Decimal=Field(gt=0); reorder_level:int=Field(ge=0); reorder_quantity:int=Field(gt=0); preferred_supplier_id:int|None=None; is_active:bool=True
    @field_validator("selling_price")
    @classmethod
    def selling_ge_cost(cls,v,info):
        c=info.data.get("cost_price")
        if c is not None and v<c: raise ValueError("selling_price must be >= cost_price")
        return v
class ProductOut(ORM): id:int; name:str; sku:str; barcode:str|None; category_id:int; unit:str; cost_price:Decimal; selling_price:Decimal; reorder_level:int; reorder_quantity:int; preferred_supplier_id:int|None; is_active:bool

class WarehouseCreate(BaseModel): warehouse_code:str; name:str; city:str; address:str; capacity:int=Field(gt=0); manager_id:int|None=None; is_active:bool=True
class WarehouseOut(ORM): id:int; warehouse_code:str; name:str; city:str; address:str; capacity:int; manager_id:int|None; is_active:bool

class SupplierCreate(BaseModel): supplier_code:str; name:str; email:EmailStr; phone:str; gst_number:str; address:str; lead_time_days:int=Field(ge=0); is_active:bool=True
    
class SupplierOut(ORM): id:int; supplier_code:str; name:str; email:EmailStr; phone:str; gst_number:str; address:str; lead_time_days:int; is_active:bool

class CustomerCreate(BaseModel): customer_code:str; name:str; email:EmailStr; phone:str; address:str; credit_limit:Decimal=Field(ge=0); is_active:bool=True
class CustomerOut(ORM): id:int; customer_code:str; name:str; email:EmailStr; phone:str; address:str; credit_limit:Decimal; is_active:bool

class POItemIn(BaseModel): product_id:int; quantity_ordered:int=Field(gt=0); unit_cost:Decimal=Field(gt=0)
class POCreate(BaseModel): supplier_id:int; warehouse_id:int; expected_delivery_date:date|None=None; items:list[POItemIn]=Field(min_length=1)
class POReceiveItem(BaseModel): item_id:int; quantity:int=Field(gt=0)
class POReceive(BaseModel): items:list[POReceiveItem]=Field(min_length=1)
class POOut(ORM): id:int; po_number:str; supplier_id:int; warehouse_id:int; expected_delivery_date:date; received_at:datetime|None; total_amount:Decimal; status:str

class SOItemIn(BaseModel): product_id:int; quantity:int=Field(gt=0)
class SOCreate(BaseModel): customer_id:int; warehouse_id:int; items:list[SOItemIn]=Field(min_length=1)
class DispatchIn(BaseModel): courier_name:str; tracking_number:str
class SOOut(ORM): id:int; so_number:str; customer_id:int; warehouse_id:int; subtotal:Decimal; tax_amount:Decimal; grand_total:Decimal; status:str; courier_name:str|None; tracking_number:str|None; dispatched_at:datetime|None; delivered_at:datetime|None

class ReturnItemIn(BaseModel): product_id:int; quantity:int=Field(gt=0)
class ReturnCreate(BaseModel): items:list[ReturnItemIn]=Field(min_length=1); reason:str
class InspectItem(BaseModel): item_id:int; condition:str
class ReturnInspect(BaseModel): items:list[InspectItem]=Field(min_length=1)
class ReturnDecision(BaseModel): rejection_reason:str|None=None

class AdjustmentCreate(BaseModel): product_id:int; warehouse_id:int; quantity:int; reason:str
