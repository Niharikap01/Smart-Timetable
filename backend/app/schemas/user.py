from pydantic import BaseModel, Field, field_validator
from typing import Optional


def _validate_bcrypt_password_size(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes.")
    return password


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)

    @field_validator("password")
    @classmethod
    def password_size(cls, password: str) -> str:
        return _validate_bcrypt_password_size(password)


class CoordinatorCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=10, max_length=100)

    @field_validator("password")
    @classmethod
    def password_size(cls, password: str) -> str:
        return _validate_bcrypt_password_size(password)


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_coordinator: bool = False
    active: bool
    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None
