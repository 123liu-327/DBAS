from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.storage import StorageError

HTTP_ERROR_MESSAGES = {
    400: "请求参数不正确",
    401: "身份验证失败",
    403: "没有权限执行此操作",
    404: "请求的接口不存在",
    405: "请求方法不被允许",
    409: "请求与当前数据状态冲突",
    413: "上传内容过大",
    415: "不支持的内容类型",
    422: "请求参数校验失败",
}


def validation_error_message(error: dict) -> str:
    """Convert a Pydantic error into stable, user-facing Chinese text."""
    error_type = str(error.get("type", ""))
    context = error.get("ctx") or {}

    if error_type == "missing":
        return "该字段为必填项"
    if error_type in {"date_type", "date_parsing", "date_from_datetime_parsing"}:
        return "请输入有效日期，日期必须真实存在且格式为 YYYY-MM-DD"
    if error_type in {"datetime_type", "datetime_parsing"}:
        return "请输入有效的日期时间"
    if error_type in {"int_type", "int_parsing"}:
        return "请输入有效整数"
    if error_type in {"float_type", "float_parsing"}:
        return "请输入有效数字"
    if error_type in {"string_type", "string_unicode"}:
        return "请输入有效字符串"
    if error_type == "list_type":
        return "请输入数组"
    if error_type == "dict_type":
        return "请输入对象"
    if error_type == "bool_type":
        return "请输入布尔值"
    if error_type == "string_too_short":
        return f"长度不能少于 {context.get('min_length')} 个字符"
    if error_type == "string_too_long":
        return f"长度不能超过 {context.get('max_length')} 个字符"
    if error_type in {"too_short", "list_too_short"}:
        return f"至少需要 {context.get('min_length')} 项"
    if error_type in {"too_long", "list_too_long"}:
        return f"最多允许 {context.get('max_length')} 项"
    if error_type == "greater_than":
        return f"必须大于 {context.get('gt')}"
    if error_type == "greater_than_equal":
        return f"必须大于或等于 {context.get('ge')}"
    if error_type == "less_than":
        return f"必须小于 {context.get('lt')}"
    if error_type == "less_than_equal":
        return f"必须小于或等于 {context.get('le')}"
    if error_type == "literal_error":
        return f"只允许以下值：{context.get('expected')}"
    if error_type == "enum":
        return f"请选择有效值：{context.get('expected')}"
    if error_type == "string_pattern_mismatch":
        return "格式不正确"
    if error_type == "extra_forbidden":
        return "不允许提交该字段"
    if error_type == "json_invalid":
        return "JSON 格式不正确"
    if error_type == "value_error":
        message = str(error.get("msg", ""))
        prefix = "Value error, "
        if message.startswith(prefix):
            message = message[len(prefix):]
        if message and any("\u4e00" <= char <= "\u9fff" for char in message):
            return message
    return "请求参数格式不正确"


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
    detail = str(exc.detail)
    if any("\u4e00" <= char <= "\u9fff" for char in detail):
        message = detail
    else:
        message = HTTP_ERROR_MESSAGES.get(exc.status_code, "请求处理失败")
    return error_response(exc.status_code, "HTTP_ERROR", message)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part not in {"body", "query", "path"})
    return error_response(
        422, "VALIDATION_ERROR", validation_error_message(first), field or None
    )


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
