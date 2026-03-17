"""

"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.middleware import register_middleware
from app.routers.health import router as health_router
from app.routers.market_data import router as market_data_router


configure_logging()
logger=get_logger(__name__)

# Lifespan — startup and shutdown

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    logger.info(
        "application_starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )

    # star the background scheduler
    from app.scheduler import scheduler
    scheduler.start()
    logger.info(
        "scheduler_started",
        jobs=[job.id for job in scheduler.get_jobs()],
    )

    logger.info("application_ready")
    yield


    #shutdown
    logger.info("application_shutting_down")

    #gracefully stop the scheduler - waits for running jobs to finsh
    from app.scheduler import scheduler
    scheduler.shutdown(wait=True)
    logger.info("scheduler_stopped")


    logger.info("application_stopped")



app=FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## AI Assistant for Intraday Gold Trading (NY Session)

A production-ready AI-powered assistant for discretionary XAUUSD traders.

    """,
    docs_url="/docs",
    redoc_url="/redoc",
    # openapi_url="/openapi.json",
    lifespan=lifespan,
)

#middleware
register_middleware(app)

#routers
app.include_router(health_router)
app.include_router(market_data_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    """ API root - redirects to docs in development"""
    return JSONResponse({
        "message":f"welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "docs": "/docs",
        "health":"/health",
    })