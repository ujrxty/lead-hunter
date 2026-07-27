from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
import time

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import jobs_router
from app.api.routes.ai import router as ai_router
from app.api.routes.session import router as session_router
from app.api.routes.settings import router as settings_router
from app.api.routes.scheduler import router as scheduler_router
from app.api.services.settings_service import settings_service
from app.api.services.scheduler_service import scheduler_service


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting for API protection."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}

    async def dispatch(self, request: Request, call_next):
        # Get client IP (consider X-Forwarded-For in production)
        client_ip = request.client.host if request.client else "unknown"
        current_minute = int(time.time() / 60)
        key = f"{client_ip}:{current_minute}"

        # Clean old entries
        old_keys = [k for k in self.request_counts if not k.endswith(f":{current_minute}")]
        for k in old_keys:
            del self.request_counts[k]

        # Check rate limit
        self.request_counts[key] = self.request_counts.get(key, 0) + 1

        if self.request_counts[key] > self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."}
            )

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    await init_db()
    logger.info("Database initialized")
    # Preload settings cache so first API call doesn't hit DB
    try:
        await settings_service._load_all()
        logger.info("Settings cache loaded")
    except Exception as e:
        logger.warning(f"Settings preload failed: {e}")
    yield
    logger.info("Shutting down...")
    # Stop scheduler gracefully
    if scheduler_service.is_running:
        await scheduler_service.stop()
        logger.info("Scheduler stopped")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# CORS - accept any localhost/127.0.0.1 port so the user can run the frontend
# on whatever dev port they like without editing config.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT"],
    allow_headers=["Content-Type", "Authorization"],
)

# Register routers
app.include_router(jobs_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Upwork Job Intelligence API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
