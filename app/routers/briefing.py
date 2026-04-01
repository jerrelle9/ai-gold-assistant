"""
FastAPI routes for the daily pre-market briefing.
 
Endpoints:
  GET  /api/v1/briefing/latest           → Most recent briefing
  POST /api/v1/briefing/generate         → Manually generate today's briefing
"""


from fastapi import APIRouter, HTTPException
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/briefing", tags=["Briefing"])

@router.get("/latest", summary="Latest pre-market briefing")
async def get_latest_briefing():
    """
    Returns the most recent pre-market briefing.
    Generated automatically at 4:00 AM EST each trading day.
    """

    from app.services.briefing.generator import get_latest_briefing
    briefing = get_latest_briefing()

    if not briefing:
        raise HTTPException(
            status_code=404,
            detail=(
                "No briefing found. Try POST /briefing/generate to create one, "
                "or wait for the 4:00 AM EST scheduled generation"
            ),
        )


    return {"success": True, "briefing": briefing}

@router.post("/generate", summary="Manually generate today's briefing")
async def generate_briefing():
    """
    Manually trigger briefing generation for today.
 
    Useful for:
      - Testing the briefing system
      - Regenerating after market data updates
      - Running outside of the 4:00 AM scheduled time
 
    Requires market data and indicators to be loaded first.
    OpenAI narrative requires OPENAI_API_KEY in .env.
    Without an API key, a structured text summary is generated instead.
    """

    try:
        from app.services.briefing.generator import generate_daily_briefing
        briefing = generate_daily_briefing()

        if not briefing:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate briefing. Ensure market data is loaded first. ",
            )

        return{
            "success": True,
            "message": "Briefing generated successfully.",
            "briefing": briefing,
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("manual_briefing_generation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))








