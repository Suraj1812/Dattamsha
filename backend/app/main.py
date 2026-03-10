from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import protected_router, public_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RateLimitMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.services.auth import ensure_bootstrap_admin


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.auto_create_schema:
            init_db()
            with SessionLocal() as db:
                ensure_bootstrap_admin(db, settings)
                db.commit()
        else:
            logger.info("Auto schema creation is disabled; expected managed migrations.")
        yield

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(GZipMiddleware, minimum_size=settings.response_compression_min_size)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_per_minute,
        excluded_paths={
            "/api/v1/health",
            "/api/v1/health/live",
            "/api/v1/health/ready",
            "/docs",
            "/redoc",
            "/openapi.json",
        },
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(public_router, prefix="/api/v1")
    app.include_router(protected_router, prefix="/api/v1")
    return app


app = create_app()
