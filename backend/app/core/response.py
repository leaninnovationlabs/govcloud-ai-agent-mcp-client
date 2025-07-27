from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class APIError(BaseModel):
    code: str
    message: str
    details: str | None = None


class APIResponse(BaseModel, Generic[T]):
    data: T | None = None
    errors: list[APIError] = []
    success: bool = True

    @classmethod
    def success_response(cls, data: T) -> "APIResponse[T]":
        return cls(data=data, success=True, errors=[])

    @classmethod
    def error_response(
        cls, 
        code: str, 
        message: str, 
        details: str | None = None
    ) -> "APIResponse[None]":
        error = APIError(code=code, message=message, details=details)
        return cls(data=None, success=False, errors=[error])

    @classmethod
    def validation_error_response(cls, errors: list[str]) -> "APIResponse[None]":
        api_errors = [
            APIError(code="VALIDATION_ERROR", message=error) 
            for error in errors
        ]
        return cls(data=None, success=False, errors=api_errors) 