"""
FastAPI routes for chart pattern detection.
 
Endpoints:
  GET  /api/v1/patterns/recent           → Recent detected patterns
  GET  /api/v1/patterns/types            → List of supported pattern types
  POST /api/v1/patterns/detect           → Manually trigger pattern detection
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/patterns", tags=["Patterns"])

VALID_SYMBOLS = ["XAUUSD", "DXY", "US10Y"]
VALID_TIMEFRAMES = ["1m", "5m", "15m"]
VALID_PATTERN_TYPES = [
    "liquidity_sweep",
    "break_of_structure",
    "fair_value_gap",
    "range_breakout",
    "volume_spike",
]

class DetectRequest(BaseModel):
    symbol:str="XAUUSD"
    timeframe: str="5m"


@router.get("/types", summary="List supported pattern types")
async def get_pattern_types():
    """Returns all pattern types the system can detect."""
    return{
        "success": True,
        "patterns":{
            "liquidity_sweep": "Price spikes beyond a key level then reverses — stop hunt",
            "break_of_structure": "Price closes beyond a prior swing high or low",
            "fair_value_gap": "Three-candle price imbalance — potential fill zone",
            "range_breakout": "Price breaks above or below the Asian session range",
            "volume_spike": "Abnormally high volume candle — institutional activity",
        },
    }


@router.get("/recent", summary="Recent detected patterns")
async def get_recent_patterns(
    symbol: str = Query("XAUUSD", description="Symbol to filter by"),
    limit: int  = Query(20, ge=1, le=100),
    pattern_type: Optional[str] = Query(None, description="Filter by pattern type"),
):
    """Returns recently detected patterns from the database."""

    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Invalid symbol. choose from: {VALID_SYMBOLS}")
    
    if pattern_type and pattern_type not in VALID_PATTERN_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid pattern type. Choose from {VALID_PATTERN_TYPES}")
    
    from app.services.patterns.detector import get_recent_patterns
    patterns = get_recent_patterns(symbol=symbol, limit=limit, pattern_type=pattern_type)

    return{
        "success": True,
        "count": len(patterns),
        "symbol": symbol,
        "patterns": patterns,
    }


@router.post("/detect", summary="Manually trigger pattern detection")
async def trigger_detection(request: DetectRequest):
    """
    Manually run pattern detection on the latest candles.
    Useful for testing or forcing a detection outside of the scheduler.
    Results are saved to the database and alerts are created.
    """

    if request.symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Invalid symbol. Choose from: {VALID_SYMBOLS}")
    
    if request.symbol not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe. Choose from: {VALID_TIMEFRAMES}")
    
    try: 
        from app.services.market_data.storage import load_candles
        from app.services.market_data.indicators import get_latest_indicators
        from app.services.patterns.detector import detect_all_patterns, save_patterns
        from app.services.alerts.manager import create_pattern_alert

        # load latest candles
        df = load_candles(request.symbol, request.timeframe, limit=100)

        if df.empty:
            raise HTTPException(
                status_code=404,
                detail="No candle data found. Run market data fetch first."
            )
        

        # load session levels for range breakout detection
        indicators = get_latest_indicators(request.symbol, request.timeframe)
        asian_high = indicators.get("asian_session_high") if indicators else None
        asian_low = indicators.get("asian_session_low") if indicators else None


        #  run detection
        patterns = detect_all_patterns(
            df=df,
            symbol=request.symbol,
            timeframe=request.timeframe,
            asian_high=asian_high,
            asian_low=asian_low,
        )

        # save patterns and create alerts
        saved = save_patterns(patterns)
        alert_ids = []
        for pattern in patterns:
            alert_id = create_pattern_alert(pattern)
            if alert_id:
                alert_ids.append(alert_id)


        return {
            "success": True,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "candles_analyzed": len(df),
            "patterns_detected": len(patterns),
            "patterns_saved": saved,
            "alerts_created": len(alert_ids),
            "patterns": patterns,
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("pattern_detection_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    


        
        