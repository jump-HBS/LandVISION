# -*- coding: utf-8 -*-
"""
HTTP 中间件：请求追踪 / 安全响应头 / 限流 / 操作审计。

组件：
  RequestIDMiddleware  为每个请求分配 X-Request-ID（日志排查链路用）
  SecurityHeadersMiddleware  补全安全响应头（X-Frame-Options / X-Content-Type-Options 等）
  RateLimitMiddleware  按 IP 滑动窗口限流（内存实现，单机部署够用；集群换 Redis）
  AuditMiddleware      记录审计日志（内存环形缓冲 + 文件日志），供 /api/system/audit 查询
"""
import logging
import time
import uuid
from collections import deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import settings

logger = logging.getLogger("landvision.middleware")

# 内存审计环形缓冲（进程内可见，重启清空；生产应落库）
AUDIT_BUFFER: deque = deque(maxlen=500)
_audit_lock = Lock()


def record_audit(entry: dict) -> None:
    """把一条审计记录写入内存缓冲与日志文件。"""
    if not settings.audit_enabled:
        return
    with _audit_lock:
        AUDIT_BUFFER.append(entry)
    audit_logger = logging.getLogger("landvision.audit")
    audit_logger.info(
        "%s %s %s %s %d %dms",
        entry["time"], entry["ip"], entry["method"], entry["path"],
        entry["status"], entry["duration_ms"],
    )


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流：默认每 IP 每分钟 settings.rate_limit 次（0=关闭）。"""

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = {}
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        limit = settings.rate_limit
        if limit > 0:
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            with self._lock:
                window = self._hits.setdefault(ip, deque())
                while window and now - window[0] > 60:
                    window.popleft()
                if len(window) >= limit:
                    return _json_response(
                        429,
                        {"code": "RATE_LIMITED",
                         "message": f"请求过于频繁（{limit} 次/分钟），请稍后再试",
                         "detail": {}},
                    )
                window.append(now)
        return await call_next(request)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        ip = request.client.host if request.client else "unknown"
        record_audit({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ip": ip,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        })
        return response


def _json_response(status_code: int, content: dict):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status_code, content=content)


def recent_audit(limit: int = 50) -> list[dict]:
    """返回最近 limit 条审计记录（时间倒序）。"""
    with _audit_lock:
        return list(AUDIT_BUFFER)[-limit:][::-1]
