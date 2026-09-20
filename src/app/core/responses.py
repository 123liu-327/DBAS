from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int
    message: str
    data: T | None = None


def ok(data: T | None = None, *, message: str = "success", code: int = 200) -> ApiResponse[T]:
    return ApiResponse(code=code, message=message, data=data)
