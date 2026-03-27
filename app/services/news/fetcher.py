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
        "q": "treasury yield bonds US10Y",
        "related_symbol": "US10Y",
        "description": "Treasury yield news",
    },
]


# Core fetch function
def fetch_news(
    query: str,
    related_symbol: str,
    # from_date: Optional[datetime] = None,
    page_size: int = 20,
)-> list[dict]:
    """
    Fetch news articles from NewsAPI for a given query.
 
    Args:
        query:          Search query string
        related_symbol: Symbol this news relates to (XAUUSD, DXY, US10Y)
        from_date:      Fetch articles published after this date.
                        Defaults to 24 hours ago.
        page_size:      Number of articles to fetch (max 100 on free tier)
 
    Returns:
        List of article dicts with keys:
            title, description, content, source_name,
            url, published_at, related_symbol
 
    Example:
        articles = fetch_news("gold price inflation", "XAUUSD")
        print(f"Fetched {len(articles)} articles")
    """

    if not settings.NEWS_API_KEY:
        logger.error(
            "news_api_key_missing",
            hint = "Set NEWS_API_KEY in your .env file - get one free at newsapi.org"
        )
        return[]
    
    # if from_date is None:
    #     from_date = datetime.utcnow() - timedelta(hours=24)

    
    params = {
        "q": query,
        # "from": from_date.strftime("%Y-%m-%dT%H:%M:%S"),
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": min(page_size, 100),
        "apiKey": settings.NEWS_API_KEY,
    }


    logger.info(
        "fetching_news",
        query=query,
        symbol=related_symbol,
        # from_date=from_date.isoformat(),
    )

    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            logger.error(
                "newsapi_error",
                status=data.get("status"),
                code=data.get("code"),
                message=data.get("message"),
            )
            return []
        

        articles = data.get("articles", [])
        parsed = []

        for article in articles:
             # Skip articles with no title or removed content
            if not article.get("title"):
                continue

            if article.get("title") == "[Removed]":
                continue

            # Parse published_at timestamp
            published_at = _parse_timestamp(article.get("publishedAt"))
            if not published_at:
                continue
            
            parsed.append({
                "title": article.get("title", "")[:500],
                "description": article.get("description") or "",
                "content": article.get("content") or "",
                "source_name": article.get("source", {}).get("name", ""),
                "published_at": published_at,
                "related_symbol": related_symbol,
                "url": article.get("url", "")
            })
        
        logger.info(
            "news_fetch_complete",
            query=query,
            symbol=related_symbol,
            total=len(articles),
            parsed=len(parsed),
        )

        return parsed
    
    except requests.exceptions.Timeout:
        logger.error("newsapi_timeout", query=query)
        return []
    
    except requests.exceptions.RequestException as exc:
        logger.error("newsapi_request_failed", query=query, error=str(exc))
        return []
    

def fetch_all_gold_news(hours_back: int = 24) -> list[dict]:
    """
    Fetch news for all gold-related queries.
    Called by the scheduler once per day at 3:50 AM EST.
 
    Args:
        hours_back: How many hours back to search for news.
                    Default 24 fetches last day's news.
 
    Returns:
        Combined list of all articles across all queries.
        Duplicates by URL are removed.
 
    Example:
        articles = fetch_all_gold_news(hours_back=24)
        print(f"Total articles: {len(articles)}")
    """
     
    # from_date = datetime.utcnow() - timedelta(hours=hours_back)
    all_articles = []
    seen_urls = set()

    for query_config in GOLD_QUERIES:
        articles = fetch_news(
            query=query_config["q"],
            related_symbol=query_config["related_symbol"],
            # from_date=from_date,
            page_size=20,
        )

        for article in articles:
            url = article.get("url", ""),
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_articles.append(article)
        
    
    logger.info(
        "all_news_fetch_complete",
        total_articles=len(all_articles),
        unqiue_urls=len(seen_urls),
    )

    return all_articles


# Helpers

def _parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """
    Parse NewsAPI's ISO timestamp string into a UTC datetime.
 
    NewsAPI returns timestamps like: "2024-01-15T14:30:00Z"
    """

    if not ts_str:
        return None
    
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=pytz.utc) if dt.tzinfo is None else dt
    except (ValueError, AttributeError):
        logger.warning("timestamp_parse_failed", timestamp=ts_str)
        return None




