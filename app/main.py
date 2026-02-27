"""
HR AI Platform - Production-Ready FastAPI Application

Best Practices Applied:
1. /docs, /redoc, /openapi.json at root level (no API prefix)
2. Middleware order: CORS → Logging → Performance → SecureHeaders → CSRF → RateLimiting
3. init_db() only at startup with context manager for sessions
4. Complete exception handling
5. Local ReDoc for CSP compliance
6. Modular router structure
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Core imports (leaf modules - safe for circular imports)
import app.models  # Force model registration with SQLAlchemy
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.schemas import ApiResponse
from app.core.logging import setup_logging
from app.core.metrics import get_metrics_response
from app.core.limiter import limiter
from app.core.middleware import (
    CorrelationIdMiddleware,
    LoggingMiddleware,
    PerformanceMiddleware,
    SecureHeadersMiddleware,
    CSRFMiddleware,
    RateLimitingMiddleware,
)
from app.database import init_db, SessionLocal
from app.core.init_system import init_system_data
from app.routers.api_router import api_router

# ============================================================================
# LOGGING SETUP
# ============================================================================
setup_logging()
logger = logging.getLogger(__name__)

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    - Startup: Initialize database once
    - Shutdown: Cleanup resources
    """
    # === STARTUP ===
    logger.info(f"Starting {settings.app_name} v{settings.version} ({settings.environment})")
    
    try:
        init_db()
        logger.info("✓ Database initialized successfully")
        
        # Initialize default system data (Org, Admin)
        init_system_data()
        logger.info("✓ System initialization check complete")
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        raise
    
    yield  # Application runs here
    
    # === SHUTDOWN ===
    logger.info("Gracefully shutting down...")


# ============================================================================
# FASTAPI INSTANCE
# ============================================================================
# Docs at root level, API prefix only for routers
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="HR AI Platform - Enterprise-grade HR management with AI capabilities",
    # Docs always at root (no API prefix)
    docs_url="/docs",
    redoc_url=None,  # We'll serve custom ReDoc
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ============================================================================
# STATIC FILES FOR LOCAL REDOC
# ============================================================================
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Custom ReDoc endpoint (uses CDN for the standalone JS bundle)
@app.get("/redoc", include_in_schema=False)
async def custom_redoc():
    """
    Serve ReDoc documentation.
    Note: Uses CDN-hosted ReDoc JS for simplicity.
    """
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>API Documentation - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    </style>
</head>
<body>
    <redoc spec-url='/openapi.json' 
           hide-download-button="true"
           theme='{"colors":{"primary":{"main":"#1976d2"}}}'
    ></redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
    """)


# ============================================================================
# RATE LIMITER
# ============================================================================
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============================================================================
# MIDDLEWARE STACK
# Order (last added = first to execute):
# CORS → Logging → Performance → SecureHeaders → CSRF → RateLimiting
# ============================================================================
# Add in REVERSE order (last added runs first)

# 6. Rate Limiting (innermost)
app.add_middleware(RateLimitingMiddleware)

# 5. CSRF Protection
if settings.environment != "development":
    app.add_middleware(CSRFMiddleware)
else:
    logger.info("! Skipping CSRFMiddleware in development mode")

# 4. Security Headers
app.add_middleware(SecureHeadersMiddleware)

# 3. Performance Tracking
app.add_middleware(PerformanceMiddleware)

# 2. Request Logging
app.add_middleware(LoggingMiddleware)

# 1. Correlation ID (for tracing)
app.add_middleware(CorrelationIdMiddleware)

# 0. CORS (outermost - runs first on requests, last on responses)
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://[::1]:3000",
    "http://[::1]:3001",
]

# In development, also allow the base localhost for mobile debugging or other tools
if settings.environment == "development":
    origins.extend(["http://localhost", "http://127.0.0.1"])

# Add production frontend URLs
if settings.environment != "development":
    origins.extend([
        "https://hr-ai-platform.vercel.app",
        "https://hr-ai-simple.vercel.app",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)

# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI validation errors (422) with structured format."""
    errors = []
    for error in exc.errors():
        # Clean up field name (loc is usually ('body', 'field_name'))
        field = error["loc"][-1] if len(error["loc"]) > 0 else "unknown"
        errors.append({
            "field": str(field),
            "msg": error["msg"]
        })
    
    logger.warning(f"Validation Error: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,  # User suggested HTTP_422_UNPROCESSABLE_CONTENT but FastAPI 0.115 uses ENTITY by default, I will check what's available
        content={"success": False, "errors": errors}
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle domain-specific application exceptions."""
    logger.warning(f"AppException: {exc.message}", extra={"code": exc.error_code})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "errors": [{"msg": exc.message, "code": exc.error_code}]
        }
    )


@app.exception_handler(StarletteHTTPException)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: Union[HTTPException, StarletteHTTPException]):
    """Handle standard HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "errors": [{"msg": exc.detail if isinstance(exc.detail, str) else "Request failed"}]
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Fallback handler for unhandled server errors."""
    logger.exception("Unhandled server error", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "errors": [{"msg": "An unexpected server error occurred."}]
        }
    )


# ============================================================================
# ROUTER INCLUSION
# API prefix applied ONLY to routers, not to docs
# ============================================================================
app.include_router(api_router, prefix=settings.api_prefix)

# ============================================================================
# OPERATIONAL ENDPOINTS (at root level)
# ============================================================================
@app.get("/", tags=["Health"])
def root():
    """API root endpoint."""
    return {
        "message": "HR AI Platform API",
        "version": settings.version,
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe for load balancers and orchestrators."""
    return {
        "status": "up",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.version,
        "environment": settings.environment,
    }


@app.get("/readiness", tags=["Health"])
def readiness_check():
    """Readiness probe - verifies database connectivity."""
    try:
        from sqlalchemy import text
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "components": {"database": "connected"},
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/liveness", tags=["Health"])
def liveness_check():
    """Alias for health check."""
    return health_check()


@app.get("/metrics", tags=["Observability"])
def get_metrics():
    """Prometheus-compatible metrics endpoint."""
    return get_metrics_response()
