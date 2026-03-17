"""

FastAPI routes for market data.
 
Endpoints:
  GET  /api/v1/market-data/candles          → Query stored candles
  GET  /api/v1/market-data/latest           → Latest candle per symbol
  GET  /api/v1/market-data/indicators       → Latest indicator values
  POST /api/v1/market-data/fetch            → Manually trigger a data fetch
  GET  /api/v1/market-data/symbols          → List tracked symbols
  GET  /api/v1/market-data/session-levels   → Today's session high/low levels

"""


from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import get_logger
from app.config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/market-data", tags=["Market Data"])

VALID_SYMBOLS = ["XAUUSD", "DXY", "US10Y"]
VALID_TIMEFRAMES = ["1m", "5m", "15m"]


# Response models

class CandleResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None



class IndicatorResponse(BaseModel):
    symbol: str
    timeframe: str
    date: str
    atr_14: Optional[float] = None
    vwap: Optional[float] = None
    asian_session_high: Optional[float] = None
    asian_session_low: Optional[float] = None
    london_session_high: Optional[float] = None
    london_session_low: Optional[float] = None
    ny_session_high: Optional[float] = None
    ny_session_low: Optional[float] = None
    daily_high: Optional[float] = None
    daily_low: Optional[float] = None
    prev_day_high: Optional[float] = None
    prev_day_low: Optional[float] = None
    prev_day_close: Optional[float] = None


class FetchRequest(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None


class FetchResponse(BaseModel):
    success: bool
    message: str
    results: dict


# Endpoints

@router.get("/symbols", summary="List tracked symbols")
async def get_symbols():
    """
    Returns the list of symbols and timeframes the system tracks
    """
    return {
        "success": True,
        "symbols": VALID_SYMBOLS,
        "timeframes": VALID_TIMEFRAMES,
        "descriptions":{
            "XAUUSD": "Gold (XAU/USD) - via GC=F futures proxy",
            "DXY": "US Dollar Index",
            "US10Y": "US 10-Year Treasury Yield",
        },
    }


@router.get("/latest", summary="Latest candle for a symbol")
async def get_latest_candle(
    symbol: str = Query(..., description="Symbol: XAUUSD, DXY, or US10Y"),
    timeframe: str = Query("5m", description="Timeframe: 1m, 5m, or 15m"),
):
    """
    Returns the most recent OHLCV candle stored for the given symbol.
    Use this for the dashboard live price display.
    """

    _validate_symbol(symbol)
    _validate_timeframe(timeframe)

    from app.services.market_data.storage import get_latest_candle
    candle = get_latest_candle(symbol, timeframe)

    if not candle:
        raise HTTPException(
            status_code=404,
            detail= f"No data found for {symbol} {timeframe}."
                    f"Try POST /market-data/fetch to load data first."
        )
    
    return {"success": True, "candle": candle}



@router.get("/candles", summary="Query historical candles")
async def get_candles(
    symbol: str = Query(..., description="Symbol: XAUUSD, DXY, or US10Y"),
    timeframe: str = Query("5m", description="Timeframe: 1m, 5m, or 15m"),
    limit: int=Query(100, ge=1, le=1000, description="number of candles to return"),
    start: Optional[datetime] = Query(None, description="Start datetime (ISO format)"),
    end: Optional[datetime] = Query(None, description="End datetime (ISO format)"),
):
    
    """
    Returns historical OHLCV candles from the database.
    Results are sorted oldest to newest.
    """

    _validate_symbol(symbol)
    _validate_timeframe(timeframe)

    from app.services.market_data.storage import load_candles
    df = load_candles(symbol, timeframe, start=start, end=end, limit=limit)

    if df.empty:
        return{
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "count": 0,
            "candles": [],
        }
    
    candles = df.to_dict(orient="records")
    # Convert timestamps to ISO strings

    for c in candles:
        if hasattr(c["timestamp"], "isoformat"):
            c["timestamp"] = c["timestamp"].isoformat()

    
    
    return{
        "success": True,
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(candles),
        "candles": candles,
    }


@router.get("/indicators", summary="Latest technical indicators")
async def get_indicators(
    symbol: str = Query(..., description="Symbol: XAUUSD, DXY, or US10Y"),
    timeframe: str = Query("5m", description="Timeframe: 1m, 5m, or 15m"),
):
    """
    Returns the latest computed indicators for a symbol.
    Includes ATR, VWAP, and all session high/low levels.
    """

    _validate_symbol(symbol)

    from app.services.market_data.indicators import get_latest_indicators
    result = get_latest_indicators(symbol, timeframe)

    if not result:
        raise HTTPException(
            status_code=404,
            detail= f"No indicators found for {symbol} {timeframe}."
                    f"Try POST /market-data/fetch to load data first.",
        )
    
    return {"success": True, "indicators": result}


@router.get("/session-levels", summary="Today's session high/low levels")
async def get_session_levels(
    symbol: str = Query("XAUUSD", description="Symbol to get session levels for"),
):
    """
    Returns Asian, London, and NY session high/low levels for today.
    These are the key levels discretionary traders watch.
    """

    _validate_symbol(symbol)

    from app.services.market_data.indicators import get_latest_indicators
    result = get_latest_indicators(symbol, "5m")  # Session levels stored with 5m timeframe

    if not result:
        raise HTTPException(
            status_code=404,
            detail= "Session levels not yet computed. Fetch data first."
        )

    return {
        "success": True, 
        "symbol": symbol, 
        "date": result["date"],
        "sessions":{
            "asian": {
                "high": result["asian_session_high"],
                "low": result["asian_session_low"],
                "range": _calc_range(
                    result["asian_session_high"], 
                    result["asian_session_low"]
                ),
            },
            "london": {
                "high": result["london_session_high"],
                "low": result["london_session_low"],
                "range": _calc_range(
                    result["london_session_high"], 
                    result["london_session_low"]
                ),
            },
            "ny": {
                "high": result["ny_session_high"],
                "low": result["ny_session_low"],
                "range": _calc_range(
                    result["ny_session_high"], 
                    result["ny_session_low"]
                ),
            },
        },
        "key_levels": {
            "prev_day_high": result["prev_day_high"],
            "prev_day_low": result["prev_day_low"],
            "prev_day_close": result["prev_day_close"],
            "vwap": result["vwap"],
            "atr_14": result["atr_14"],
        },
    }

@router.post("/fetch", summary="Manually trigger data fetch")
async def trigger_fetch(request: FetchRequest):
    """
    Manually trigger a market data fetch outside of the scheduled jobs.
    Useful for:
      - Loading initial data when setting up the system
      - Filling gaps after downtime
      - Testing the data pipeline
 
    If symbol/timeframe are not specified, fetches all symbols and timeframes.
    """

    from app.services.market_data.fetcher import fetch_ohlcv, fetch_all_symbols
    from app.services.market_data.storage import save_candles, save_all_symbols

    symbols = [request.symbol] if request.symbol else VALID_SYMBOLS
    timeframes = [request.timeframe] if request.timeframe else VALID_TIMEFRAMES

    #Validate inputs

    for s in symbols:
        _validate_symbol(s)
    
    for tf in timeframes:
        _validate_timeframe(tf)

    results = {}

    for symbol in symbols:
        results[symbol] = {}
        for timeframe in timeframes:
            try:
                logger.info("manual_fetch_triggered", symbol=symbol, timeframe=timeframe)
                df = fetch_ohlcv(symbol, timeframe)

                if df.empty:
                    results[symbol][timeframe] = {"status": "no_data", "inserted": 0}
                else:
                    inserted = save_candles(df)
                    results[symbol][timeframe] = {
                        "status": "ok", 
                        "fetched": len(df),
                        "inserted": inserted,
                    }
                    
            except Exception as exc:
                logger.error(
                    "manual_fetch_failed",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(exc),
                )
                results[symbol][timeframe] = {
                    "status": "error",
                    "error": str(exc),
                }

    total_inserted = sum(
        v.get("inserted", 0)
        for sym_results in results.values()
        for v in sym_results.values()
    )

    return FetchResponse(
        success=True,
        message=f"Fetch complete. {total_inserted} new candles inserted.",
        results=results,
    )

#Helpers
def _validate_symbol(symbol: str) -> None:
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol '{symbol}'. Must be one of: {VALID_SYMBOLS}",
        )

def _validate_timeframe(timeframe: str) -> None:
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe '{timeframe}'. Must be one of: {VALID_TIMEFRAMES}",
        )
    
def _calc_range(high: Optional[float], low: Optional[float]) -> Optional[float]:
    if high is not None and low is not None:
        return round( high - low, 5)
    return None




