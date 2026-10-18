from pydantic import BaseModel, Field
from typing import Optional
from app.models.course import RoomType


class RoomBase(BaseModel):
    room_number: str = Field(..., min_length=1, max_length=50)
    room_type: RoomType
    capacity: int = Field(..., gt=0)
    building: Optional[str] = None
    floor: Optional[int] = None
    active: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    room_number: Optional[str] = Field(None, min_length=1, max_length=50)
    room_type: Optional[RoomType] = None
    capacity: Optional[int] = Field(None, gt=0)
    building: Optional[str] = None
    floor: Optional[int] = None
    active: Optional[bool] = None


class RoomResponse(BaseModel):
    id: int
    room_number: str
    room_type: RoomType
    # Zero represents an unverified capacity from the reference workbook.
    capacity: int = Field(..., ge=0)
    building: Optional[str] = None
    floor: Optional[int] = None
    active: bool
    model_config = {"from_attributes": True}
