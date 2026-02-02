"""
SafeHarbor AI - Main Application Entry Point

The OBBB (One Big Beautiful Bill) Tax Compliance Engine.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db.session import engine
from backend.routers.v1 import admin, auth, calculations, compliance, employees, integrations, organizations, sso

settings = get_settings()

# Initialize Sentry for error monitoring
if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=f"safeharbor@{settings.app_version}",
        traces_sample_rate=0.1 if settings.environment == "production" else 1.0,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    # Database connection pool is lazy-initialized by SQLAlchemy
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description=(
        "SafeHarbor AI is the Active Brain sitting on top of Passive payroll pipes. "
        "We calculate qualified amounts for OBBB tax exemptions: qualified overtime pay, "
        "qualified tips, and qualified senior citizen wages."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
)

# Audit logging middleware (outermost — captures all requests)
from backend.middleware.audit_log import AuditLogMiddleware

app.add_middleware(AuditLogMiddleware)

# Rate limiting middleware
from backend.middleware.rate_limit import RateLimitMiddleware

app.add_middleware(RateLimitMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "safeharbor-api"}


@app.get("/health/ready", tags=["Health"])
async def readiness_check() -> dict[str, str]:
    """Readiness check with dependency verification."""
    # TODO: Add database and Redis connectivity checks
    return {
        "status": "ready",
        "service": "safeharbor-api",
        "version": settings.app_version,
        "environment": settings.environment,
    }


# API v1 routes
app.include_router(
    auth.router,
    prefix=f"{settings.api_v1_prefix}/auth",
    tags=["Auth"],
)
app.include_router(
    organizations.router,
    prefix=f"{settings.api_v1_prefix}/organizations",
    tags=["Organizations"],
)
app.include_router(
    employees.router,
    prefix=f"{settings.api_v1_prefix}/organizations/{{org_id}}/employees",
    tags=["Employees"],
)
app.include_router(
    calculations.router,
    prefix=f"{settings.api_v1_prefix}/organizations/{{org_id}}/calculations",
    tags=["Calculations"],
)
app.include_router(
    integrations.router,
    prefix=f"{settings.api_v1_prefix}/organizations/{{org_id}}/integrations",
    tags=["Integrations"],
)
app.include_router(
    compliance.router,
    prefix=settings.api_v1_prefix,
    tags=["Compliance"],
)
app.include_router(
    admin.router,
    prefix=f"{settings.api_v1_prefix}/organizations/{{org_id}}/admin",
    tags=["Admin"],
)
app.include_router(
    sso.router,
    prefix=f"{settings.api_v1_prefix}/organizations/{{org_id}}",
    tags=["SSO"],
)
