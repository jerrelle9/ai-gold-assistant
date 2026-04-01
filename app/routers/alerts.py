"""
FastAPI routes for trading alerts.
 
Endpoints:
  GET   /api/v1/alerts                   → Recent alerts
  GET   /api/v1/alerts/unread            → Unread alerts only
  GET   /api/v1/alerts/count             → Unread alert count (dashboard badge)
  PATCH /api/v1/alerts/{id}/read         → Mark single alert as read
  PATCH /api/v1/alerts/read-all          → Mark all alerts as read
"""



from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("", summary="Recent alerts")
async def get_alerts(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    alert_type: Optional[str]= Query(None, description="Filter by type: pattern, sentiment, level"),
    limit: int = Query(50, ge=1, le=200),
):
    """Returns recent alerts sorted by most recent first."""

    from app.services.alerts.manager import get_recent_alerts
    alerts = get_recent_alerts(symbol=symbol, limit=limit, alert_type=alert_type)

    return{
        "success": True,
        "count": len(alerts),
        "alerts": alerts,
    }


@router.get("/unread", summary="Unread alerts")
async def get_unread_alerts(
    symbol: Optional[str] = Query(None),
    limit: int=Query(50, ge=1, le=200),
):
    """Returns only unread alerts. Used by dashboard notification panel."""

    from app.services.alerts.manager import get_unread_alerts
    alerts = get_unread_alerts(symbol=symbol, limit=limit)

    return{
        "success": True,
        "count": len(alerts),
        "alerts": alerts,
    }


@router.get("/count", summary="Unread alert count")
async def get_alert_count():
    """Returns count of unread alerts. Used by dashboard notification badge."""

    from app.services.alerts.manager import get_alert_count
    count = get_alert_count(unread_only=True)

    return {
        "success":True,
        "unread_count": count,
    }


@router.patch("/{alert_id}/read", summary="Mark alert as read")
async def mark_read(alert_id: int):
    """Mark a single alert as read."""

    from app.services.alerts.manager import mark_alert_read
    success = mark_alert_read(alert_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    
    return {"success":True, "alert_id":alert_id, "is_read": True}

@router.patch("/read-all", summary="Mark all alerts as read")
async def mark_all_read(symbol: Optional[str] = Query(None)):
    """Mark all unread alerts as read."""
    from app.services.alerts.manager import mark_all_alerts_read
    count = mark_all_alerts_read(symbol=symbol)

    return {
        "success": True,
        "marked_read": count,
    }
