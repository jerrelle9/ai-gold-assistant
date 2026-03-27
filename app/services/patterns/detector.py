"""
app/services/patterns/detector.py
===================================
Detects intraday chart patterns used by discretionary gold traders.
 
Patterns detected:
  1. Liquidity Sweep     — price spikes beyond a key level then reverses
  2. Break of Structure  — price closes beyond a prior swing high/low
  3. Fair Value Gap      — three-candle imbalance / price gap
  4. Range Breakout      — price breaks above/below Asian session range
  5. Volume Spike        — abnormally high volume candle
 
Each pattern returns a standardised dict that gets saved to
the detected_patterns table and triggers an alert.
 
All pattern functions take a pandas DataFrame of OHLCV candles
sorted oldest to newest and return a list of detected pattern dicts.
"""


from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np
import pytz

from app.core.logging import get_logger

logger=get_logger(__name__)
NY_TZ=pytz.timezone("America/New_York")

# Entry point


def detect_all_patterns(
    df: pd.DataFrame,
    symbol:str,
    timeframe: str,
    asian_high: Optional[float] = None,
    asian_low: Optional[float] = None,
) -> list[dict]:
    
    """
    Run all pattern detectors on a DataFrame of candles.
    Called by the scheduler every 5 minutes during the NY session.
 
    Args:
        df:           OHLCV DataFrame sorted oldest to newest.
                      Must have: timestamp, open, high, low, close, volume
        symbol:       e.g. "XAUUSD"
        timeframe:    e.g. "5m"
        asian_high:   Asian session high (for range breakout detection)
        asian_low:    Asian session low  (for range breakout detection)
 
    Returns:
        List of pattern dicts. Each dict has:
            symbol, timeframe, detected_at, pattern_type,
            direction, confidence, price_at_detection, notes
    """

    if df.empty or len(df) < 10:
        logger.warning("insufficient_candles_for_detection", rows=len(df))
        return []
    
    patterns=[]

    patterns.extend(detect_liquidity_sweeps(df, symbol, timeframe))
    patterns.extend(detect_break_of_structure(df, symbol, timeframe))
    patterns.extend(detect_fair_value_gaps(df, symbol, timeframe))
    patterns.extend(detect_volume_spikes(df, symbol, timeframe))

    if asian_high and asian_low:
        patterns.extend(
            detect_range_breakouts(df, symbol, timeframe, asian_high, asian_low)
        )
    

    logger.info(
        "pattern_detection_complete",
        symbol=symbol,
        timeframe=timeframe,
        patterns_found=len(patterns),
    )

    return patterns

# pattern 1 - Liquidity sweep

def detect_liquidity_sweeps(
    df:pd.DataFrame,
    symbol: str,
    timeframe: str,
    lookback: int=20,
    reversal_threshold: float=0.5,
) -> list[dict]:
    
    """
    Detect liquidity sweeps — price spikes beyond a key level then reverses.
 
    A bullish liquidity sweep (sell-side sweep):
      - Price wicks below a recent swing low
      - Candle closes back above the swing low
      - Suggests stop orders were triggered below the low
 
    A bearish liquidity sweep (buy-side sweep):
      - Price wicks above a recent swing high
      - Candle closes back below the swing high
      - Suggests stop orders were triggered above the high
 
    Why traders care:
      Liquidity sweeps often precede the real move in the opposite direction.
      Smart money grabs liquidity before reversing.
    """
    
    patterns=[]

    if len(df) < lookback+1:
        return patterns
    

    # look at the last 5 candles for fresh sweeps
    for i in range(max(lookback, 5), len(df)):
        candle = df.lock[i]
        lookback_df = df.iloc[i - lookback:i]

        swing_high = lookback_df["high"].max()
        swing_low = lookback_df["low"].min()

        candle_range = candle["high"] - candle["low"]
        if candle_range == 0:
            continue

        # Bullish sweep — wick below swing low, closes above
        if candle["low"] < swing_low and candle["close"] > swing_low:
            wick_size = swing_low - candle["low"]
            reversal_ratio = wick_size / candle_range

            if reversal_ratio >= reversal_threshold:
                confidence = min(reversal_ratio, 1.0)
                patterns.append(_make_pattern(
                    symbol=symbol,
                    timeframe=timeframe,
                    detected_at=candle["timestamp"],
                    pattern_type="liquidity_sweep",
                    direction="bullish",
                    confidence=round(float(confidence), 4),
                    price=float(candle["close"]),
                    notes=(
                        f"Swept swing low at {swing_low:.2f}. "
                        f"Wick: {wick_size:.2f}. Close above low suggests reversal."
                    ),
                ))

        
        # Bearish sweep — wick above swing high, closes below
        if candle["high"] > swing_high and candle["close"] < swing_high:
            wick_size = candle["high"] - swing_high
            reversal_ratio = wick_size / candle_range

            if reversal_ratio >= reversal_threshold:
                confidence = min(reversal_ratio, 1.0)
                patterns.append(_make_pattern(
                    symbol=symbol,
                    timeframe=timeframe,
                    detected_at=candle["timeframe"],
                    pattern_type="liquidity_sweep",
                    direction="bearish",
                    confidence=round(float(confidence), 4),
                    price=float(candle["close"]),
                    notes=(
                        f"Swept swing high at {swing_high:.2f}."
                        f"Wick: {wick_size: .2f}. Close below high suggests reversal."
                    ),
                ))

    return patterns



# Pattern 2 — Break of Structure (BOS)

def detect_break_of_structure(
    df: pd.DataFrame,
    symbol:str,
    timeframe: str,
    lookback: int=10,
)-> list[dict]:
    
    """
    Detect Break of Structure (BOS) — price closes beyond a prior swing.
 
    Bullish BOS:
      - Price closes above the most recent swing high
      - Signals continuation of uptrend or start of new uptrend
 
    Bearish BOS:
      - Price closes below the most recent swing low
      - Signals continuation of downtrend or start of new downtrend
 
    Why traders care:
      BOS confirms trend direction and provides entries on retracements.
      Used by Smart Money Concepts (SMC) traders as primary bias signal.
    """

    patterns=[]

    if len(df) < lookback+2: 
        return patterns
    
    for i in range(lookback + 1, len(df)):
        candle=df.iloc[i]
        prev_candle = df.iloc[i-1]
        lookback_df = df.iloc[i - lookback -1:i-1]

        swing_high = lookback_df["high"].max()
        swing_low = lookback_df["low"].min()

        # Bullish BOs - close above swing high
        if(prev_candle["close"] <= swing_high and candle["close"]>swing_high):
            breakout_pips=candle["close"]-swing_high
            confidence = min(breakout_pips / (swing_high * 0.001), 1.0)

            patterns.append(_make_pattern(
                symbol=symbol,
                timeframe=timeframe,
                detected_at=candle["timestamp"],
                pattern_type="break_of_structure",
                direction="bullish",
                confidence=round(float(confidence), 4),
                price=float(candle["close"]),
                notes=(
                    f"Bullish BOS: closed above swing high at {swing_high: .2f}."
                    f"Breakout: {breakout_pips: .2f} above level."
                ),
            ))

        # Bearish BOS - close below swing low
        if(prev_candle["close"] >= swing_low and candle["close"]< swing_low):
            breakout_pips = swing_low - candle["close"]
            confidence = min(breakout_pips/(swing_low * 0.001), 1.0)

            patterns.append(_make_pattern(
                symbol=symbol,
                timeframe=timeframe,
                detected_at=candle["timestamp"],
                pattern_type="break_of_structure",
                direction="bearish",
                confidence=round(float(confidence), 4),
                price=float(candle["close"]),
                notes=(
                    f"Bearish BOs: closed below swing low at {swing_low: .2f}. "
                    f"Breakdown: {breakout_pips: .2f} below level."
                ),
            ))
    
    return patterns

# Patterns 3 FVGs
def detect_fair_value_gaps(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    min_gap_pips: float = 2.0
) -> list[dict]:
    """
    Detect Fair Value Gaps (FVG) — three-candle price imbalance.
 
    Bullish FVG:
      Candle[i-2].high < Candle[i].low
      (Gap between candle 1's high and candle 3's low — price moved up fast)
 
    Bearish FVG:
      Candle[i-2].low > Candle[i].high
      (Gap between candle 1's low and candle 3's high — price moved down fast)
 
    Why traders care:
      FVGs represent price imbalances. Price often returns to fill them.
      Traders use unfilled FVGs as entry zones on pullbacks.
    """

    patterns = []

    if len(df) < 3:
        return patterns
    
    for i in range(2, len(df)):
        c1 = df.iloc[i-2]
        c2 = df.iloc[i-1]
        c3 = df.iloc[i]


    for 







