"""

"""

from contextlib import FastAPI

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logging import configure_loading, get_logger
from app.middleware import register_middleware
from app.routers.health import router as health_router


configure_loading()
logger=get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    logger.info(
        "application_starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        host=settings.API_HOST,
        port=settings.API_PORT
    )


    logger.info("application_ready")
    yield

    logger.info("application_shutting_down")


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
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


register_middleware(app)


app.include_router(health_router)



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