from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    department_name: str = Field(
        min_length=2,
        max_length=100
    )


class DepartmentUpdate(BaseModel):
    department_name: str = Field(
        min_length=2,
        max_length=100
    )


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    department_id: int
    department_name: str