from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.storage import StorageError


class AppError(Exception):
    def __init__(
        self, code: str, message: str, *, status_code: int = 400, field: str | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field


def error_response(
    status_code: int, code: str, message: str, field: str | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "field": field}},
    )


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.field)


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part not in {"body", "query", "path"})
    return error_response(422, "VALIDATION_ERROR", first["msg"], field or None)


async def storage_error_handler(_: Request, __: StorageError) -> JSONResponse:
    return error_response(500, "STORAGE_ERROR", "数据文件读写失败")


async def unexpected_error_handler(_: Request, __: Exception) -> JSONResponse:
    return error_response(500, "INTERNAL_ERROR", "服务器内部错误")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StorageError, storage_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
