"""

Computes technical indicators from OHLCV candles and stores
results in the technical_indicators table.
 
Indicators computed:
  - ATR(14)              Average True Range — measures volatility
  - VWAP                 Volume Weighted Average Price
  - Asian session high/low   00:00–08:00 EST
  - London session high/low  03:00–08:00 EST
  - NY session high/low      08:00–17:00 EST
  - Daily high/low
  - Previous day high/low/close
 
Session times are defined in New York (EST/EDT) timezone.
All timestamps stored in database are UTC.

"""


from datetime import datetime, date
from typing import Optional
from decimal import Decimal

import pandas as pd
import numpy as np
import pytz

from app.core.logging import get_logger
from app.database import SyncSessionLocal
from app.models.base import TechnicalIndicator
from app.services.market_data.storage import load_candles

logger = get_logger(__name__)

NY_TZ = pytz.timezone("America/New_York")
UTC_TZ = pytz.utc  

# Session hours in New York time (hour, minute)
SESSION_HOURS = {

    "asian":  {"start": (18, 0), "end": (3, 0)},   
    "london": {"start": (3, 0),  "end": (8, 0)},   
    "ny":     {"start": (8, 0),  "end": (17, 0)}, 
}


# Main computation entry point
def compute_and_save_indicators(
    symbol: str,
    timeframe: str,
    target_date: Optional[datetime] = None,
) -> Optional[dict]:
    
    """
    Compute all indicators for a symbol/timeframe on a given date
    and save them to the technical_indicators table.
 
    Args:
        symbol:      e.g. "XAUUSD"
        timeframe:   e.g. "5m"
        target_date: Date to compute indicators for. Defaults to today.
 
    Returns:
        Dict of computed indicator values, or None if insufficient data.
 
    Example:
        result = compute_and_save_indicators("XAUUSD", "5m")
        print(result["atr_14"])
    """

    if target_date is None:
        target_date = datetime.now(NY_TZ).date()
    
    logger.info(
        "computing_indicators",
        symbol=symbol,
        timeframe=timeframe,
        date=str(target_date),
    )

    # Load candles for the target date + previous day (needed for prev_day values)
    target_dt=datetime.combine(target_date, datetime.min.time())
    start_dt = target_dt - pd.Timedelta(days=2)

    df = load_candles(symbol, timeframe, start=start_dt, limit=2000)

    if df.empty or len(df) < 14:
        logger.warning(
            "insufficient_data_for_indicators",
            symbol=symbol,
            timeframe=timeframe,
            rows=len(df),
        )
        return None
    

    # Convert timestamps to NY timezone for session filtering
    df["timestamp_ny"] = df["timestamp"].dt.tz_convert(NY_TZ)
    df["date_ny"] = df["timestamp_ny"].dt.date

    today_df = df[df["date_ny"] == target_date].copy()
    df["date_ny"] = sorted(df["date_ny"].unique())

    prev_date = None
    for d in prev_date:
        if d < target_date:
            prev_date = d

    prev_df = df[df["date_ny"] == prev_date].copy() if prev_date else pd.DataFrame()

    if today_df.empty:
        logger.warning(
            "no_data_for_target_date",
            symbol=symbol,
            date=str(target_date),
        )
        return None
    
    indicators = {}
    indicators.update(_compute_atr(df))
    indicators.update(_compute_vwap(today_df))
    indicators.update(_compute_session_levels(today_df))
    indicators.update(_compute_daily_levels(today_df))
    indicators.update(_compute_prev_day_levels(prev_df))


    _save_indicators(symbol, timeframe, target_date, indicators)

    logger.info(

        "indicators_saved",
        symbol=symbol,
        timeframe=timeframe,
        date=str(target_date),
        indicators=list(indicators.keys()),
    )

    return indicators

            
def _compute_atr(df: pd.DataFrame, period: int = 14) -> dict:
    """"
    
    Average True Range (ATR) — measures market volatility.
 
    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = rolling mean of True Range over `period` candles.
 
    Higher ATR = more volatile session (wider stops needed).
    Lower ATR = quieter market (tighter ranges expected).

    """

    if len(df) < period + 1:
        return {"atr_14": None}
    
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean().iloc[-1]

    return {"atr_14": round(float(atr), 5) if not np.isnan(atr) else None}
    



def _compute_vwap(df: pd.DataFrame) -> dict:
    """
    Volume Weighted Average Price (VWAP).
 
    VWAP = cumulative(typical_price * volume) / cumulative(volume)
    Typical price = (high + low + close) / 3
 
    VWAP is the institutional benchmark price for the session.
    Price above VWAP = bullish bias.
    Price below VWAP = bearish bias.
    """
    if df.empty or "volume" not in df.columns:
        return {"vwap": None}
    
    df = df.copy()
    df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
    df["tp_volume"] = df["typical_price"] * df["volume"]

    cumulative_tp_vol = df["tp_volume"].cumsum()
    cumulative_vol = df["volume"].cumsum()

    vwap_series = cumulative_tp_vol / cumulative_vol
    vwap = vwap_series.iloc[-1]


    return {"vwap": round(float(vwap), 5) if not np.isnan(vwap) else None}


def _compute_session_levels(df: pd.DataFrame) -> dict:
    """
    Compute high and low for each trading session.
 
    Sessions (EST):
      Asian:  6:00 PM (prior day) to 3:00 AM
      London: 3:00 AM to 8:00 AM
      NY:     8:00 AM to 5:00 PM
 
    These levels are critical for discretionary traders:
    - Asian range = overnight consolidation box
    - London open often breaks the Asian range
    - NY session often retests London highs/lows
    """


    result = {}

    session_filters = {
        "asian": lambda ts: (ts.hour >= 18) or (ts.hour < 3),
        "london": lambda ts: 3 <= ts.hour < 8,
        "ny": lambda ts: 8 <= ts.hour < 17,
    }

    for session_name, time_filter in session_filters.items():
        session_df = df[df["timestamp_ny"].apply(
            lambda ts: time_filter(ts)    
        )]

        if not session_df.empty:
            result[f"{session_name}_session_high"] = None
            result[f"{session_name}_session_low"] = None
        else:
            result[f"{session_name}_session_high"] = round(float(session_df["high"].max()), 5)
            result[f"{session_name}_session_low"] = round(float(session_df["low"].min()), 5)
    
    return result


def _compute_daily_levels(df: pd.DataFrame) -> dict:
    """Current day high and low."""

    if df.empty:
        return {"daily_high": None, "daily_low": None}

    return {
        "daily_high": round(float(df["high"].max()), 5),
        "daily_low": round(float(df["low"].min()), 5),
    }


def _compute_prev_day_levels(prev_df: pd.DataFrame) -> dict:
    """
        Previous day high, low, and close.
        These are key support/resistance levels used by most traders.
        Previous day high/low are often targeted for liquidity sweeps.
    """

    if prev_df.empty:
        return {
            "prev_day_high": None,
            "prev_day_low": None,
            "prev_day_close": None,
        }
    
    return{
        "prev_day_high": round(float(prev_df["high"].max()), 5),
        "prev_day_low": round(float(prev_df["low"].min()), 5),
        "prev_day_close": round(float(prev_df["close"].iloc[-1]), 5),
    }



# Database persistence
def _save_indicators(
    symbol: str,
    timeframe: str,
    target_date: date,
    indicators: dict,
) -> None:
    """
    Upsert indicator values into the technical_indicators table.
    If a row already exists for this symbol+timeframe+date, update it.
    """

    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert


    date_dt = datetime.combine(target_date, datetime.min.time())
    date_utc = UTC_TZ.localize(date_dt)

    row = {
        "symbol": symbol,
        "timeframe": timeframe,
        "date": date_utc,
        **{k: Decimal(str(v)) if v is not None else None for k, v in indicators.items()}
    }


    with SyncSessionLocal() as session:
        try:
            stmt = (
                pg_insert(TechnicalIndicator)
                .values(**row)
                .on_conflict_do_update(
                    constraint="uq_indicators",
                    set_={k: v for k, v in row.items() if k not in ("symbol", "timeframe", "date")},
                )
            )
            session.execute(stmt)
            session.commit()   

        except Exception as exc:
            session.rollback()
            logger.error("save_indicators_failed", symbol=symbol, error=str(exc))
            raise

def get_latest_indicators(symbol: str, timeframe: str) -> Optional[dict]:
    """
    Load the most recent indicator row for a symbol/timeframe.
    Used by the dashboard and briefing generator.
    """

    from sqlalchemy import select

    with SyncSessionLocal() as session:
        row = (
            session.execute(
                select(TechnicalIndicator)
                .where(TechnicalIndicator.symbol == symbol)
                .where(TechnicalIndicator.timeframe == timeframe)
                .order_by(TechnicalIndicator.date.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    if not row:
        return None
    
    def _safe_float(val):
        return float(val) if val is not None else None
    
    return {
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "date": row.date.isoformat(),
        "atr_14": _safe_float(row.atr_14),
        "vwap": _safe_float(row.vwap),
        "asian_session_high": _safe_float(row.asian_session_high),
        "asian_session_low": _safe_float(row.asian_session_low),
        "london_session_high": _safe_float(row.london_session_high),
        "london_session_low": _safe_float(row.london_session_low),
        "ny_session_high": _safe_float(row.ny_session_high),
        "ny_session_low": _safe_float(row.ny_session_low),
        "daily_high": _safe_float(row.daily_high),
        "daily_low": _safe_float(row.daily_low),
        "prev_day_high": _safe_float(row.prev_day_high),
        "prev_day_low": _safe_float(row.prev_day_low),
        "prev_day_close": _safe_float(row.prev_day_close),
    }