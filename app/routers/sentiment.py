"""

FastAPI routes for news and sentiment data.
 
Endpoints:
  GET  /api/v1/sentiment/latest          → Latest sentiment score per symbol
  GET  /api/v1/sentiment/history         → Daily sentiment scores over time
  GET  /api/v1/sentiment/articles        → Recent news articles
  POST /api/v1/sentiment/analyze         → Manually trigger news fetch + analysis
  GET  /api/v1/sentiment/model-status    → Check if FinBERT model is loaded

"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import get_logger

logger=get_logger(__name__)
router=APIRouter(prefix="/sentiment", tags=["Sentiment"])

# Response models
VALID_SYMBOLS=["XAUUSD", "DXY", "US10Y"]
VALID_LABELS = ["bullish", "bearish", "neutral"]


class SentimentResponse(BaseModel):
    symbol: str
    date: str
    score: float
    label: str
    article_count: int
    bullish_count: int
    bearish_count: int
    neutral_count: int

class AnalyzeResponse(BaseModel):
    success: bool
    message: str
    articles_fetched: int
    articles_saved: int 
    sentiment: Optional[dict] = None


@router.get("/model-status", summary="Check if snetiment model is loaded")
async def model_status():
    """
    Checks whether the FinBERT model and required libraries are available.
    Call this first to confirm the sentiment pipeline is ready before
    triggering analysis.
    """

    from app.services.news.sentiment import is_model_available

    available = is_model_available()

    return{
        "succes": True,
        "model": "ProsusAI/finbert",
        "available": available,
        "message":(
            "Model libraries available. Model will load on first analysis request."
            if available
            else "torch and transformers are not installed. Run: pip install torch transformers"
        ),
    }


@router.get("/history", summary="Daily sentiment history")
async def get_sentiment_history(
    symbol: str = Query("XAUUSD", description="Symbol to get history for"),
    days: int = Query(30, ge=1, le=90, description="Number of days of history"),
):
    """
    Returns daily sentiment scores for the last N days.
    Useful for plotting sentiment trends on the dashboard.
    """

    _validate_symbol(symbol)

    from app.services.news.storage import get_sentiment_history
    history = get_sentiment_history(symbol, days=days)

    return{
        "success": True,
        "symbol": symbol,
        "days": days,
        "count": len(history),
        "history": history,
    }


@router.get("/articles", summary="Recent news articles")
async def get_recent_articles(
    symbol:Optional[str] = Query(None, description="Filter by symbol (optional)"),
    label: Optional[str] = Query(None, description="Filter by label: bullish, bearish, neutral"),
    limit: int = Query(20, ge=1, le=100, description="Number of articles to return"),
):
    """
    Returns recent news articles stored in the database.
    Optionally filter by symbol or sentiment label.
    """

    if symbol:
        _validate_symbol(symbol)

    if label and label not in VALID_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid label '{label}'. Must be one of: {VALID_LABELS}"
        )
    
    from app.services.news.storage import get_recent_articles
    articles = get_recent_articles(symbol=symbol, limit=limit, label=label)

    return{
        "success": True,
        "count": len(articles),
        "filters": {"symbol": symbol, "label":label},
        "articles": articles,
    }


@router.post("/analyze", summary="Fetch and analyze news sentiment")
async def trigger_analysis(request: AnalyzeRequest):

    """
    Manually trigger a full news fetch and sentiment analysis cycle.
 
    Steps performed:
      1. Fetch latest headlines from NewsAPI
      2. Run FinBERT sentiment analysis on each article
      3. Save articles with sentiment labels to database
      4. Compute and save daily sentiment score
 
    This runs automatically via scheduler at 3:50 AM EST.
    Use this endpoint to trigger a manual refresh.
 
    Note: First call downloads the FinBERT model (~440MB) if not cached.
    Subsequent calls are instant as the model stays in memory.
    """

    from app.services.news.fetcher import fetch_all_gold_news, fetch_news
    from app.services.news.sentiment import analyze_batch, compute_daily_sentiment_score
    from app.services.news.storage import save_articles, save_sentiment_score

    logger.info(
        "manual_sentiment_analysis_triggered",
        hours_back = request.hours_back,
        symbol=request.symbol,
    )

    try:
        #Step 1 - Fetch news
        if request.symbol:
            _validate_symbol(request.symbol)
            articles = fetch_news(
                query=f"gold {request.symbol} price trading",
                related_symbol=request.symbol,
            )
        else:
            articles=fetch_all_gold_news(hours_back=request.hours_back)
        
        if not articles:
            return AnalyzeResponse(
                success=True,
                message="No new articles found for the specified time period.",
                articles_fetched=0,
                articles_saved=0,
                sentiment=None,
            )
        
        # step 2 -run sentiment analysis
        articles_with_sentiment = analyze_batch(articles)
        
        # step 3 - save articles
        saved = save_articles(articles_with_sentiment)

        # step 4 -compute and save daily score (for XAUUSD only)
        xauusd_articles = [
            a for a in articles_with_sentiment
            if a.get("related_symbol") == "XAUUSD"
        ]

        daily_sentiment = None
        if xauusd_articles:
            daily_sentiment = compute_daily_sentiment_score(xauusd_articles)
            save_sentiment_score("XAUUSD", daily_sentiment)


        return AnalyzeResponse(
            success=True,
            message=f"Analysis complete. {saved} new articles saved.",
            articles_fetched=len(articles),
            articles_saved=saved,
            sentiment=daily_sentiment,
        )

    except Exception as exc:
        logger.error("manual_sentiment_analysis_failed", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(exc)}"
        )   


# Helpers

def _validate_symbol(symbol: str) -> None:
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid symbol '{symbol}'. Must be one of: {VALID_SYMBOLS}"
        ) 






