"""
Health check endpoints.
 
GET /health         — Liveness probe. Is the app process running?
GET /health/ready   — Readiness probe. Can the app serve traffic? (checks DB)
GET /health/info    — App metadata. What version is deployed?
 
These endpoints are used by:
  - Docker HEALTHCHECK
  - AWS load balancer health checks
  - Your own monitoring to confirm the app is alive
"""


from datetime import datetime, timezone
from fastapi import APIRouter

from app.config import settings
from app.core.logging import get_logger
from app.database import check_db_connection

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])



# Helper — builds a consistent response envelope
def _ok_response(message: str="ok", **kwargs) -> dict:
    return{
        "success": True,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

def _error_response(message:str, **kwargs) -> dict:
    return{
        "success": False,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

# Endpoints

@router.get("", methods=["GET", "HEAD"],summary="Liveness probe",)
async def health_check():
    """
    Confirms the app process is running.
    Does NOT check the database.
    Always returns 200 immediately.
    """

    logger.debug("health_check_liveness")
    return _ok_response("API is alive")


@router.get("/ready", summary="Readiness probe")
async def health_ready():
    """
    Confirms the app can serve traffic.
    Checks that the database is reachable.
    Returns 200 if ready, 503 if not.
    """

    db_ok = await check_db_connection()

    if db_ok:
        logger.info("health_check_ready", db="ok")
        return _ok_response(
            "API is ready",
            checks={"database": "ok"},
        )
    

    logger.warning("health_check_not_ready", db="unreachable")

    from fastapi import HTTPException
    raise HTTPException(
        status_code=503,
        detail=_error_response(
            "API not ready",
            checks={"database":"unreachable"},
        ),
    )


@router.get("/info", summary="Application info")
async def health_info():
    """
    Returns app version, environment, and trading session config.
    Useful for confirming which build is running.
    """

    logger.debug("health_check_info")
    return _ok_response(
        "Applicatoin info",
        app={
            "name":settings.APP_NAME,
            "version":settings.APP_VERSION,
            "environment": settings.APP_ENV,
        },

        trading={
            "instrument":"XAUUSD",
            "session":"New York",
            "session_hours_est": f"{settings.NY_SESSION_START} - {settings.NY_SESSION_END}",
            "timezone": settings.TIMEZONE,
        },
    )

