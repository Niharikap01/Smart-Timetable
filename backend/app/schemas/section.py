from pydantic import BaseModel, Field
from typing import Optional


class SectionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    semester: int = Field(..., ge=1, le=8)
    strength: int = Field(..., gt=0)
    program: str = Field(default="CSE", min_length=1, max_length=100)
    year: int = Field(..., ge=1, le=4)
    active: bool = True


class SectionCreate(SectionBase):
    pass


class SectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    semester: Optional[int] = Field(None, ge=1, le=8)
    strength: Optional[int] = Field(None, gt=0)
    program: Optional[str] = Field(None, min_length=1, max_length=100)
    year: Optional[int] = Field(None, ge=1, le=4)
    active: Optional[bool] = None


class SectionResponse(BaseModel):
    id: int
    name: str
    semester: int
    # Zero is a deliberate "not yet verified" seed value. It is readable so
    # an administrator can fill it in, but creation/update still require > 0.
    strength: int = Field(..., ge=0)
    program: str
    year: int
    active: bool
    model_config = {"from_attributes": True}
