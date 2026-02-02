"""
Audit Logging Middleware

Logs every API request for SOC 2 compliance.
Records: user, org, method, path, status, IP, latency.
"""

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("audit")

# Paths to skip (health checks, static assets)
SKIP_PATHS = {"/health", "/healthz", "/ready", "/favicon.ico"}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Logs every API request with timing, user context, and response status.

    Log format is structured for ingestion by SIEM tools.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response: Response | None = None
        error: str | None = None

        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = (time.monotonic() - start) * 1000
            status_code = response.status_code if response else 500

            # Extract user info from request state (set by RBAC middleware)
            user_id = getattr(request.state, "user_id", None)
            org_id = getattr(request.state, "org_id", None)
            user_email = getattr(request.state, "user_email", None)

            # Client IP (handle proxies)
            client_ip = request.headers.get(
                "x-forwarded-for", request.client.host if request.client else "unknown"
            )
            if "," in client_ip:
                client_ip = client_ip.split(",")[0].strip()

            log_data = {
                "method": request.method,
                "path": path,
                "status": status_code,
                "latency_ms": round(latency_ms, 2),
                "client_ip": client_ip,
                "user_id": str(user_id) if user_id else None,
                "org_id": str(org_id) if org_id else None,
                "user_email": user_email,
                "user_agent": request.headers.get("user-agent", ""),
                "content_length": request.headers.get("content-length", "0"),
            }

            if error:
                log_data["error"] = error

            # Use structured logging
            if status_code >= 500:
                logger.error("api_request", extra=log_data)
            elif status_code >= 400:
                logger.warning("api_request", extra=log_data)
            else:
                logger.info("api_request", extra=log_data)
