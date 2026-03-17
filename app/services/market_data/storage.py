"""

Writes fetched OHLCV DataFrames into the market_data table in PostgreSQL.
 
Key behaviour:
  - Uses INSERT ... ON CONFLICT DO NOTHING so re-running a fetch
    never creates duplicates (the unique constraint on symbol + timeframe
    + timestamp handles this automatically)
  - Operates synchronously — called from the scheduler which runs
    in a background thread, not inside an async FastAPI route
 
All database operations here use the sync engine from database.py
because APScheduler jobs run in threads, not async event loops.

"""


from datetime import datetime
from decimal import Decimal
from typing import Optional
from unittest import result

import pandas as pd
from sqlalchemy import exc, insert
from sqlalchemy.orm import Session

from app.database import SyncSessionLocal
from app.core.logging import get_logger
from app.models.base import MarketData

logger = get_logger(__name__)


# save candles
def save_candles(df: pd.DataFrame) -> int:
    """
    
    Insert a DataFrame of OHLCV candles into the market_data table.
    Skips any rows that already exist (upsert-safe).
 
    Args:
        df: DataFrame from fetcher.py with columns:
            timestamp, open, high, low, close, volume, symbol, timeframe, source
 
    Returns:
        Number of rows successfully inserted.
 
    Example:
        df = fetch_ohlcv("XAUUSD", "5m")
        inserted = save_candles(df)
        print(f"Saved {inserted} new candles")
    
    """

    if df.empty:
        logger.warning("save_candles_empty_dataframe")
        return 0
    

    required_columns = {"timestamp", "open", "high", "low", "close", "symbol", "timeframe", }
    missing  = required_columns - set(df.columns)
    if missing:
        logger.error("save_candles_missing_columns", missing=list(missing))
        return 0
    
    rows = _dataframe_to_rows(df)
    inserted = 0

    with SyncSessionLocal() as session:
        try:
            for row in rows:
                # INSERT ... ON CONFLICT DO NOTHING
                # The unique constraint uq_market_data handles deduplication

                stmt = (
                    insert(MarketData)
                    .values(**row)
                    .prefix_with("OR IGNORE")
                )

                from sqlalchemy.dialects.postgresql import insert as pg_insert
                pg_stmt = (
                    pg_insert(MarketData)
                    .values(**row)
                    .on_conflict_do_nothing(
                        index_elements=None,
                        constraint="uq_market_data"
                    )
                )

                result = session.execute(pg_stmt)
                if result.rowcount > 0:
                    inserted += 1

            session.commit()

            logger.info(
                "candles_saved",
                symbol=df["symbol"].iloc[0],
                timeframe=df["timeframe"].iloc[0],
                total_rows=len(rows),
                insterted=inserted,
                skipped=len(rows) - inserted
            )

        except Exception as exc:
            session.rollback()
            logger.error("save_candles_failed", error=str(exc))
            raise

    return inserted

def save_all_symbols(data: dict[str, pd.DataFrame]) -> dict[str, int]:
    """
    Save candles for multiple at once
 
    Args:
        data: Dict fetcher.fetch_all_symbols()
            e.g. {"XAUUSD": df, "DXY": df, "US10Y": df}
 
    Returns:
        Dict of symbols -> rows inserted
 
    Example:
        data = fetch_all_symbols("5m")
        results = save_all_symbols(data)
        # {"XAUUSD": 288, "DXY": 285, "US10Y": 290}
    """

    results = {}
    for symbol, df in data.items():
        try:
            inserted = save_candles(df)
            results[symbol] = inserted
        except Exception as exc:
            logger.error("save_symbol_failed", symbol=symbol, error=str(exc))
            results[symbol] = 0

    return results

# Query helpers — used by indicators.py and routers

def load_candles(
    symbol: str,
    timeframe: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 1000
) -> pd.DataFrame:
    
    """
    Load candles from the database into a DataFrame.
    Used by indicators.py to compute ATR, VWAP etc.
 
    Args:
        symbol:    e.g. "XAUUSD"
        timeframe: e.g. "5m"
        start:     Filter rows after this datetime
        end:       Filter rows before this datetime
        limit:     Max rows to return (default 1000)
 
    Returns:
        DataFrame sorted by timestamp ascending.
 
    Example:
        df = load_candles("XAUUSD", "5m", limit=500)
    """

    from sqlalchemy import select, and_

    with SyncSessionLocal() as session:
        query = (
            select(MarketData)
            .where(
                and_(
                    MarketData.symbol == symbol,
                    MarketData.timeframe == timeframe,
                )
            )
            .order_by(MarketData.timestamp.asc())
            .limit(limit)
        )

        if start:
            query = query.where(MarketData.timestamp >= start)
        
        if end:
            query = query.where(MarketData.timestamp <= end)

        rows = session.execute(query).scalars().all()

    if not rows:
        return pd.DataFrame() 
    
    data = [
        {
            "timestamp": r.timestamp,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume) if r.volume else 0.0,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
        }
        for r in rows
    ]

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def get_latest_candle(symbol: str, timeframe: str) -> Optional[MarketData]:
    """
    Return the most recent candle for a symbol and timeframe.
    Used by the dashboard live price endpoint.
    """

    from sqlalchemy import select

    with SyncSessionLocal() as session:
        row = (
            session.execute(
                select(MarketData)
                .where(MarketData.symbol == symbol)
                .where(MarketData.timeframe == timeframe)
                .order_by(MarketData.timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
    
    if not row:
        return None

    return{
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "timestamp": row.timestamp.isoformat(),
        "open": float(row.open),
        "high": float(row.high),
        "low": float(row.low),
        "close": float(row.close),
        "volume": float(row.volume) if row.volume else 0.0,
    }


# Internal helpers

def _dataframe_to_rows(df: pd.DataFrame) -> list[dict]:
    """
    Convert a DataFrame to a list of dicts ready for SQLAlchemy insert.
    Handles type conversion from pandas types to Python native types.
    """

    rows = []
    for _, row in df.iterrows():
            rows.append({
                "symbol": str(row["symbol"]),
                "timeframe": str(row["timeframe"]),
                "timestamp": row["timestamp"].to_pydatetime() if hasattr(row["timestamp"], "to_pydatetime") else row["timestamp"],
                "open": Decimal(str(round(float(row["open"]), 5))),
                "high": Decimal(str(round(float(row["high"]), 5))),
                "low": Decimal(str(round(float(row["low"]), 5))),
                "close": Decimal(str(round(float(row["close"]), 5))),
                "volume": Decimal(str(round(float(row["volume"]), 5))) if row.get("volume") else None,
            })  

    return rows