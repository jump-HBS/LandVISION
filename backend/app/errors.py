# -*- coding: utf-8 -*-
"""
统一错误码与全局异常处理器。

响应格式（企业级约定）：
    {"code": "机器可读错误码", "message": "面向用户的中文提示", "detail": {...}}
"""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("landvision.errors")

# 业务错误码
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
VALIDATION_ERROR = "VALIDATION_ERROR"
INVALID_PARAMS = "INVALID_PARAMS"
RATE_LIMITED = "RATE_LIMITED"
UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
INTERNAL_ERROR = "INTERNAL_ERROR"

_STATUS_TO_CODE = {
    400: INVALID_PARAMS,
    401: UNAUTHORIZED,
    403: FORBIDDEN,
    404: NOT_FOUND,
    409: CONFLICT,
    422: INVALID_PARAMS,
    429: RATE_LIMITED,
    501: NOT_IMPLEMENTED,
}


def register_exception_handlers(app: FastAPI) -> None:
    """在 FastAPI 应用上注册统一异常处理。"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code = _STATUS_TO_CODE.get(exc.status_code, INVALID_PARAMS)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": str(exc.detail),
                "detail": {"path": request.url.path, "method": request.method},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(str(p) for p in e.get("loc", [])), "message": e.get("msg", "")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "code": VALIDATION_ERROR,
                "message": "参数校验失败，请检查请求体或查询参数",
                "detail": {"errors": errors},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "code": INTERNAL_ERROR,
                "message": "服务器内部错误，请稍后重试或联系管理员",
                "detail": {"path": request.url.path},
            },
        )
