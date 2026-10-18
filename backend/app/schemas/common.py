from pydantic import BaseModel
from typing import Any, Optional, List


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    details: Optional[Any] = None


class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None
