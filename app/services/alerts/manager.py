"""
Creates, stores, and retrieves trading alerts.
 
Alerts are triggered when:
  - A chart pattern is detected during the NY session
  - Sentiment changes significantly
  - Price reaches a key level
 
Each alert is saved to the alerts table and can be
read by the dashboard in real time.
"""

from datetime import datetime
from typing import Optional
import pytz

from sqlalchemy import select, update

from app.core.logging import get_logger
from app.database import SyncSessionLocal
from app.models.base import Alert

logger = get_logger(__name__)
NY_TZ = pytz.timezone("America/New_York")

# Create alerts

def create_pattern_alert(
    pattern: dict,
    pattern_id: Optional[int]=None,
)-> Optional[int]:
    """
    Create an alert for a detected chart pattern.
 
    Args:
        pattern:    Pattern dict from detector.py
        pattern_id: Database ID of the saved pattern row
 
    Returns:
        ID of the created alert, or None if failed.
 
    Example:
        alert_id = create_pattern_alert(pattern, pattern_id=42)
    """

    direction_emoji = "🟢" if pattern["direction"] == "bullish" else "🔴"
    pattern_name = pattern["pattern_type"].replace("_", " ").title()

    message=(
        f"{direction_emoji} {pattern_name} detected on "
        f"{pattern['symbol']} {pattern['timeframe']} "
        f"at {pattern['price_at_detection']:.2f}. "
        f"{pattern.get('notes', '')}"
    )

    return _create_alert(
        symbol=pattern["symbol"],
        message=message,
        alert_type=pattern["pattern_type"],
        severity=_get_severity(pattern),
        trigger_at=pattern["detected_at"],
        pattern_id=pattern_id,
    )


def create_sentiment_alert(
    symbol: str,
    label: str,
    score: float,
    article_count: int,
) -> Optional[int]:
   """
    Create an alert when daily sentiment is strongly bullish or bearish.
 
    Args:
        symbol:        e.g. "XAUUSD"
        label:         "bullish" | "bearish" | "neutral"
        score:         Sentiment score -1.0 to 1.0
        article_count: Number of articles analyzed
 
    Returns:
        ID of the created alert, or None if neutral.
    """ 



