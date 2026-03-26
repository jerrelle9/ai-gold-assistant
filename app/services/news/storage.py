"""

Saves news articles and sentiment scores to PostgreSQL.
 
Tables written to:
  - news_articles    : individual headlines with sentiment labels
  - sentiment_scores : daily aggregated sentiment per symbol
 
Duplicate handling:
  - news_articles    : skips articles with duplicate URLs
  - sentiment_scores : upserts — updates if date+symbol already exists

"""


from datetime import datetime, date
from decimal import Decimal
from typing import Optional

import pytz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.database import SyncSessionLocal
from app.models.base import NewsArticle, SentimentScore

logger = get_logger(__name__)
UTC_TZ = pytz.utc


# Save articles

def save_articles(articles: list[dict]) -> int:
    """
    
    Insert news articles into the news_articles table.
    Skips duplicates based on URL.
 
    Args:
        articles: List of article dicts from sentiment.analyze_batch()
                  Each must have: title, published_at, related_symbol
                  Should also have: sentiment_label, sentiment_score
 
    Returns:
        Number of new articles inserted.
 
    Example:
        articles = analyze_batch(fetch_all_gold_news())
        inserted = save_articles(articles)
        print(f"Saved {inserted} new articles")
    
    """

    if not articles: 
        return 0
    
    inserted = 0

    with SyncSessionLocal() as session:
        try:
            for article in articles:
                url = article.get("url", "")
                if url:
                    existing = session.execute(
                        select(NewsArticle).where(NewsArticle.url == url)
                    ).scalar_one_or_none()

                    if existing:
                        continue
                
                row = NewsArticle(
                    title=article.get("title", "")[:500],
                    description=article.get("description") or None,
                    content=article.get("content") or None,
                    source_name=article.get("source_name") or None,
                    url=url or None,
                    published_at=article.get("published_at"),
                    related_symbol=article.get("related_symbol"),
                    sentiment_label=article.get("sentiment_label"),
                    sentiment_score=Decimal(str(article["sentiment_score"]))
                    if article.get("sentiment_Score") is not None
                    else None,
                )
                session.add(row)
                inserted += 1

            session.commit()


            logger.info(
                "articles_saved",
                total=len(articles),
                inserted=inserted,
                skipped=len(articles) - inserted,
            )
        except Exception as exc:
            session.rollback()
            logger.error("save_articles_failed", error=str(exc))
            raise
    
    return inserted


# save daily sentiment score
def save_sentiment_score(
    symbol: str,
    sentiment: dict,
    target_date: Optional[date] = None,
) -> None:
    """
    Upsert the daily aggregated sentiment score for a symbol.
    If a score already exists for this date + symbol, it is updated.
 
    Args:
        symbol:      e.g. "XAUUSD"
        sentiment:   Dict from sentiment.compute_daily_sentiment_score()
                     Must have: score, label, article_count,
                                bullish_count, bearish_count, neutral_count
        target_date: Date for this score. Defaults to today (UTC).
 
    Example:
        score = compute_daily_sentiment_score(articles)
        save_sentiment_score("XAUUSD", score)
    """
    
    if target_date is None:
        target_date = datetime.utcnow().date()

    date_dt = UTC_TZ.localize(
         datetime.combine(target_date, datetime.min.time())
    )

    row = {
        "symbol":symbol,
        "date": date_dt,
        "score": Decimal(str(sentiment["score"])),
        "label": sentiment["label"],
        "article_count": sentiment["article_count"],
        "bullish_count": sentiment["bullish_count"],
        "bearish_count": sentiment["bearish_count"],
        "neutral_count": sentiment["neutral_count"],
    }

    with SyncSessionLocal() as session:
        try:
            stmt = (
                pg_insert(SentimentScore)
                .values(**row)
                .on_conflict_do_update(
                    constraint="uq_sentiment_symbol_date",
                    set_={
                        "score": row["score"],
                        "label": row["label"],
                        "article_count": row["article_count"],
                        "bullish_count": sentiment["bullish_count"],
                        "bearish_count": sentiment["bearish_count"],
                        "neutral_count": sentiment["neutral_count"],
                    },
                )
            )
            session.execute(stmt)
            session.commit()

            logger.info(
                "sentiment_score_saved",
                symbol=symbol,
                date=str(target_date),
                label=sentiment["label"],
                score=sentiment["score"],
                articles=sentiment["article_count"],
            )
        
        except Exception as exc:
            session.rollback()
            logger.error("save_sentiment_score_failed", symbol=symbol, error=str(exc))
            raise


# Query helpers - used by router and briefing generator
def get_latest_sentiment(symbol: str) -> Optional[dict]:
    """
    Return the most recent sentiment score for a symbol.
    Used by the dashboard and pre-market briefing.
 
    Example:
        sentiment = get_latest_sentiment("XAUUSD")
        print(f"Gold sentiment: {sentiment['label']} ({sentiment['score']})")
    """

    with SyncSessionLocal() as session:
        row = session.execute(
            select(SentimentScore)
            .where(SentimentScore.symbol == symbol)
            .order_by(SentimentScore.date.desc())
            .limt(1)
        ).scalar_one_or_none()
    
    if not row:
        return None


    return{
        "symbol": row.symbol,
        "date": row.date.isoformat(),
        "score": float(row.score),
        "label": row.label,
        "article_count": row.article_count,
        "bullish_count": row.bullish_count,
        "bearish_count": row.bearish_count,
        "neutral_count": row.neutral_count,
    }


def get_recent_articles(
    symbol: Optional[str] = None,
    limit: int = 20,
    label: Optional[str] = None,
) -> list[dict]:
    

    """
    Return recent news articles from the database.
 
    Args:
        symbol: Filter by related_symbol (e.g. "XAUUSD"). None = all symbols.
        limit:  Max articles to return (default 20)
        label:  Filter by sentiment label: "bullish", "bearish", "neutral"
 
    Returns:
        List of article dicts sorted by published_at descending.
 
    Example:
        # Get last 10 bullish gold articles
        articles = get_recent_articles(symbol="XAUUSD", label="bullish", limit=10)
    """
    
    with SyncSessionLocal() as session:
        query = (
            select(NewsArticle)
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
        )

        if symbol:
            query = query.where(NewsArticle.related_symbol == symbol)
        
        if label:
            query = query.where(NewsArticle.sentiment_label == label)

        rows = session.execute(query).scalers().all()

    return[
        {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "source_name": r.source_name,
            "url": r.url,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "related_symbol": r.related_symbol,
            "sentiment_label": r.sentiment_label,
            "sentiment_score": float(r.sentiment_score) if r.sentiment_score else None,
        }
        for r in rows
    ]


def get_sentiment_history(symbol: str, days: int = 30) -> list[dict]:
    """
    Return daily sentiment scores for the last N days.
    Used by the dashboard sentiment chart.
 
    Example:
        history = get_sentiment_history("XAUUSD", days=14)
    """

    from datetime import timedelta

    cutoff = UTC_TZ.localize(
        datetime.combine(
            datetime.utcnow().date() - timedelta(days=days),
            datetime.min.time(),
        )
    )

    with SyncSessionLocal() as session:
        rows = session.execute(
            select(SentimentScore)
            .where(SentimentScore.symbol == symbol)
            .where(SentimentScore.date >= cutoff)
            .order_by(SentimentScore.date.asc())
        ).scalers().all()
    
    return[
        {
            "date": r.daate.isoformat(),
            "score": float(r.score),
            "label": r.label,
            "article_count": r.article_count,
            "bullish_count": r.bullish_count,
            "bearish_count": r.bearish_count,
            "neutral_count": r.neutral_count,
        }
        for r in rows
    ]



