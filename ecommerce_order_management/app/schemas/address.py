from pydantic import BaseModel, Field
class AddressCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone: str
    address_line: str = Field(min_length=3, max_length=300)
    city: str
    state: str
    pincode: str
    is_default: bool = False
class AddressResponse(AddressCreate):
    id: int
    model_config = {"from_attributes": True}
