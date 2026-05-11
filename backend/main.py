import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.routes import posts, narratives, alerts, analytics, influencers, websocket
from app.api.routes import ingestion as ingestion_routes
from app.workers.background_tasks import run_periodic_tasks

log = structlog.get_logger()

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
    ]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Malaysia AI Social Monitor", version=settings.APP_VERSION)
    bg_task = asyncio.create_task(run_periodic_tasks())
    yield
    # Graceful shutdown: stop ingestion scheduler first, then cancel tasks
    try:
        from app.ingestion.scheduler import get_scheduler
        get_scheduler().stop()
    except Exception:
        pass
    bg_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        pass
    log.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered social media monitoring platform for Malaysia",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    log.info(
        "HTTP",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    )
    return response


# Routes
app.include_router(posts.router, prefix=settings.API_V1_PREFIX)
app.include_router(narratives.router, prefix=settings.API_V1_PREFIX)
app.include_router(alerts.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(influencers.router, prefix=settings.API_V1_PREFIX)
app.include_router(ingestion_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(websocket.router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
