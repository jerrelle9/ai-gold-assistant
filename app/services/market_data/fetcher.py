"""
Fetches OHLCV market data from yfinance for:
  - XAUUSD  → GC=F  (Gold futures — free proxy for spot gold)
  - DXY     → DX-Y.NYB  (US Dollar Index)
  - US10Y   → ^TNX  (10-Year Treasury yield)
  
"""



from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import pytz
import yfinance as yf

from app.core.logging import get_logger

logger = get_logger(__name__)


# Symbol mapping
# yfinance uses different ticker symbols than trading platforms
SYMBOL_MAP = {
    "XAUUSD": "GC=F",  # Gold futures
    "DXY": "DX-Y.NYB",  # US Dollar Index
    "US10Y": "^TNX"     # 10-Year Treasury yield
}


# Timeframe mapping: our internal names → yfinance interval strings
TIMEFRAME_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
}

# yfinance limits on how far back you can fetch per timeframe
# 1m  → max 7 days back
# 5m  → max 60 days back
# 15m → max 60 days back
TIMEFRAME_LOOKBACK_DAYS = {
    "1m": 5,
    "5m": 55,
    "15m": 55
}


NY_TZ = pytz.timezone("America/New_York")


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> pd.DataFrame:
    
    """
    Fetch OHLCV candlestick data from yfinance.
 
    Args:
        symbol:    Internal symbol name — XAUUSD, DXY, or US10Y
        timeframe: Candle timeframe — 1m, 5m, or 15m
        start:     Start datetime (UTC). Defaults to max lookback for timeframe.
        end:       End datetime (UTC). Defaults to now.
 
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
        Empty DataFrame if fetch fails.
 
    Example:
        df = fetch_ohlcv("XAUUSD", "5m")
        print(df.head()
    
    """

    ticker = SYMBOL_MAP.get(symbol)
    if not ticker:
        logger.error(f"unknown_symbol", symbol=symbol, known=list(SYMBOL_MAP.keys()))
        return pd.DataFrame()  # Return empty DataFrame on error
    
    interval = TIMEFRAME_MAP.get(timeframe)
    if not interval:
        logger.error(f"unknown_timeframe", timeframe=timeframe, known=list(TIMEFRAME_MAP.keys()))
        return pd.DataFrame()  


    fetch_start = start
    fetch_end = end

    if fetch_start is None:
        days_back = TIMEFRAME_LOOKBACK_DAYS[timeframe]
        fetch_start = datetime.utcnow() - timedelta(days=days_back)

    if fetch_end is None:
        fetch_end = datetime.utcnow()

    
    logger.info(
        "fetching_market_data",
        symbol=symbol,
        ticker=ticker,
        timeframe=timeframe,
        start=fetch_start.isoformat(),
        end=fetch_end.isoformat(),
    )


    try:
        raw = yf.download(
            tickers=ticker,
            start=fetch_start,
            end=fetch_end,
            interval=interval,
            auto_adjust=True, #adjusts for dividends/splits
            progress=False, #suppress yfinance's progress bar
        )
    
        if raw.empty:
            logger.warning(f"no_data_returned", symbol=symbol, timeframe=timeframe)
            return pd.DataFrame()  
        
        #Flatten multi-index columns  if yfinance returns them
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        

        #normalize column names to lowercase
        raw.columns = [c.lower() for c in raw.columns]

        #Rename yfinance columns to our standard names
        rename_map = {
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume"
        }
        raw = raw.rename(columns=rename_map)
        raw = raw[["open", "high", "low", "close", "volume"]]

        # Reset index to turn the timestamp from the index into a column
        raw = raw.reset_index()
        raw = raw.rename(columns={"index": "timestamp", "Datetime": "timestamp", "Date": "timestamp"})


        #ensure timestamp is timezone-aware and in UTC
        if raw["timestamp"].dt.tz is None:
            raw["timestamp"] = raw["timestamp"].dt.tz_localize("UTC")
        else:
            raw["timestamp"] = raw["timestamp"].dt.tz_convert("UTC")

        #Drop any rows with null OHLC values
        raw = raw.dropna(subset=["open", "high", "low", "close"])

        #Add metadata columns
        raw["symbol"] = symbol
        raw["timeframe"] = timeframe
        raw["source"] = "yfinance"

        logger.info(
            "fetch_complete",
            symbol=symbol,
            timeframe=timeframe,
            rows=len(raw),
        )

        return raw
    
    except Exception as exc:
        logger.error(
            "fetch_failed",
            symbol=symbol,
            timeframe=timeframe,
            error=str(exc),
        )
        return pd.DataFrame()  



# Convenience helpers

def fetch_all_symbols(timeframe: str) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV for all three symbols at once for a given timeframe.
 
    Returns:
        Dict mapping symbol name to its DataFrame.
        e.g. {"XAUUSD": df, "DXY": df, "US10Y": df}
 
    Example:
        data = fetch_all_symbols("5m")
        gold_df = data["XAUUSD"]
    """


    results = {}
    for symbol in SYMBOL_MAP.keys():
        df = fetch_ohlcv(symbol, timeframe)
        
        if not df.empty:
            results[symbol] = df
        else:
            logger.warning("symbol_fetch_empty", symbol=symbol, timeframe=timeframe)
    
    return results


def fetch_todays_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Fetch only today's candles for a symbol.
    Used to compute intraday session levels.
 
    Returns:
        DataFrame of today's candles only.
    """

    now = datetime.now(NY_TZ)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start.astimezone(pytz.utc).replace(tzinfo=None)

    return fetch_ohlcv(symbol, timeframe, start=today_start_utc)









