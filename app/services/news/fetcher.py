"""

Fetches financial news headlines from NewsAPI.
 
Searches for articles related to:
  - Gold (XAUUSD)
  - Federal Reserve / interest rates
  - Inflation / CPI
  - US Dollar (DXY)
  - Geopolitics affecting gold
 
Free tier limits:
  - 100 requests per day
  - Articles from last 30 days
  - No full article content (headlines + description only)
 
Get a free API key at: https://newsapi.org/register
Then set NEWS_API_KEY in your .env file.
 
Docs: https://newsapi.org/docs/endpoints/everything

"""


from datetime import datetime, timedelta
from typing import Optional

import requests
import pytz

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
BASE_URL = "https://newsapi.org/v2/everything"
NY_TZ = pytz.timezone("America/New_York")

# Search queries — each targets a different driver of gold price
GOLD_QUERIES = [
    {
        "q": "gold price XAU inflation",
        "related_symbol": "XAUUSD",
        "description": "Gold price and inflation news",
    },
    {
        "q": "Federal Reserve interest rates FOMC",
        "related_symbol": "XAUUSD",
        "description": "Fed policy news affecting gold",
    },
    {
        "q": "US dollar DXY forex",
        "related_symbol": "DXY",
        "description": "Dollar strength news",  
    },
    {
        "q": "geopolitical risk war sanctions commodities",
        "related_symbol": "XAUUSD",
        "description": "Geopolitcal risk news",
    },
    {
        "q": tre
    }


]



