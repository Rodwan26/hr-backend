"""
Enterprise Middleware Stack for FastAPI.
Order: CORS → Logging → Performance → SecureHeaders → CSRF → RateLimiting
All middleware exclude /docs, /redoc, /openapi.json from processing where appropriate.
"""
import time
import uuid
import logging
import secrets
from typing import Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import request_id_var
from app.core.config import settings
from app.core.metrics import MetricsManager

logger = logging.getLogger(__name__)

# Paths that should be excluded from security middleware processing
DOCS_PATHS: Tuple[str, ...] = ("/docs", "/redoc", "/openapi.json")
HEALTH_PATHS: Tuple[str, ...] = ("/health", "/readiness", "/liveness", "/metrics", "/")


def is_docs_path(path: str) -> bool:
    """Check if path is a documentation endpoint."""
    return path.startswith(DOCS_PATHS)


def is_exempt_path(path: str) -> bool:
    """Check if path should be exempt from security middleware."""
    return is_docs_path(path) or path in HEALTH_PATHS


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique correlation/request ID to every request for tracing.
    Applied to all requests including docs.
    """
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(settings.request_id_header, str(uuid.uuid4()))
        token = request_id_var.set(request_id)
        
        try:
            response: Response = await call_next(request)
            response.headers[settings.request_id_header] = request_id
            return response
        finally:
            request_id_var.reset(token)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all incoming requests and outgoing responses.
    Excludes docs paths from verbose logging.
    """
    async def dispatch(self, request: Request, call_next):
        # Skip verbose logging for docs paths
        if is_docs_path(request.url.path):
            return await call_next(request)
        
        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={"client": request.client.host if request.client else "unknown"}
        )
        
        response = await call_next(request)
        
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            f"← {request.method} {request.url.path} → {response.status_code}",
            extra={"status": response.status_code}
        )
        
        return response


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Tracks request processing time and records metrics.
    Excludes docs paths from metrics recording.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add processing time header to all responses
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        # Skip metrics for docs paths
        if is_docs_path(request.url.path):
            return response
        
        # Record metrics
        endpoint = request.url.path
        path_parts = endpoint.strip("/").split("/")
        domain = path_parts[1] if len(path_parts) > 1 else "root"
        
        MetricsManager.record_request(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
            domain=domain,
            org_id=getattr(request.state, "organization_id", "anonymous")
        )
        MetricsManager.record_latency(endpoint=endpoint, domain=domain, duration=process_time)
        
        # Log slow requests (> 2 seconds)
        if process_time > 2.0:
            logger.warning(
                f"Slow request: {request.method} {endpoint} took {process_time:.2f}s"
            )
        
        return response


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    Excludes CSP from docs paths to allow CDN resources.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Basic security headers (always applied)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Skip CSP for docs paths (allows CDN resources for Swagger/ReDoc)
        if is_docs_path(request.url.path):
            return response
        
        # Full CSP for production
        csp = {
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline'",
            "style-src": "'self' 'unsafe-inline'",
            "font-src": "'self'",
            "img-src": "'self' data:",
            "connect-src": "'self'",
            "frame-ancestors": "'none'",
            "form-action": "'self'",
        }
        response.headers["Content-Security-Policy"] = "; ".join(f"{k} {v}" for k, v in csp.items())
        
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection using Double Submit Cookie pattern.
    Exempt: docs, health endpoints, and requests with Authorization header (JWT).
    """
    EXEMPT_PATHS = {
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/api/auth/logout",
        "/api/setup/status",
        "/api/setup/initialize",
        "/api/setup/reset",
        "/health",
        "/readiness",
        "/liveness",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/login",
        "/api/health",
    }
    
    async def dispatch(self, request: Request, call_next):
        csrf_cookie = request.cookies.get("csrftoken")
        
        # Check if path is exempt
        is_exempt = (
            request.url.path in self.EXEMPT_PATHS or
            is_docs_path(request.url.path) or
            # JWT requests don't need CSRF protection
            "Authorization" in request.headers
        )
        
        if is_exempt:
            response = await call_next(request)
            # Set CSRF cookie if not present
            if not csrf_cookie:
                token = secrets.token_urlsafe(32)
                response.set_cookie(
                    "csrftoken",
                    token,
                    httponly=False,
                    samesite="lax",
                    secure=settings.environment != "development"
                )
            return response
        
        # Validate CSRF for state-changing requests
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            csrf_header = request.headers.get("X-CSRF-TOKEN")
            
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                logger.warning(
                    f"CSRF validation failed for {request.method} {request.url.path}"
                )
                return Response(
                    content='{"success": false, "message": "CSRF validation failed", "code": "CSRF_ERROR"}',
                    status_code=403,
                    media_type="application/json"
                )
        
        response = await call_next(request)
        
        if not csrf_cookie:
            token = secrets.token_urlsafe(32)
            response.set_cookie(
                "csrftoken",
                token,
                httponly=False,
                samesite="lax",
                secure=settings.environment != "development"
            )
        
        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Basic rate limiting middleware.
    Excludes docs and health paths.
    Note: For production, use slowapi or Redis-based rate limiting.
    """
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for docs and health paths
        if is_exempt_path(request.url.path):
            return await call_next(request)
        
        # Rate limiting is handled by slowapi in main.py
        # This middleware can be extended for custom rate limiting logic
        return await call_next(request)
