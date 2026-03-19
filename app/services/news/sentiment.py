"""

Sentiment analysis pipeline using HuggingFace transformers.
 
Model used: ProsusAI/finbert
  - Fine-tuned specifically on financial news text
  - Returns: positive (bullish), negative (bearish), neutral
  - Much more accurate than general-purpose models for financial text
 
Why FinBERT over general sentiment models:
  - "The Fed raised rates" → general model: neutral
                           → FinBERT: negative (bearish for gold)
  - "Inflation surged"    → general model: negative
                           → FinBERT: positive (bullish for gold)
 
The model is downloaded automatically on first run (~440MB).
Subsequent runs use the cached version.
 
Label mapping for gold trading context:
  positive → bullish  (good news for gold price)
  negative → bearish  (bad news for gold price)
  neutral  → neutral  (no clear directional bias)

"""


from functools import lru_cache
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)
MODEL_NAME = "ProsusAI/finbert"

LABEL_MAP ={
    "positive": "bullish",
    "negative": "bearish",
    "neutral": "neutral",
}


@lru_cache(maxsize=1)
def _load_pipeline():
    """
    
    Load the FinBERT sentiment pipeline.
    Uses lru_cache so the model is only loaded once — loading takes ~5 seconds
    and uses ~500MB RAM. Subsequent calls return the cached pipeline instantly.
 
    Returns the HuggingFace pipeline object.

    """

    from transformers import pipeline

    logger.info("loading_sentiment_model", model=MODEL_NAME)

    pipe = pipeline(
        task="text-classfication",
        model=MODEL_NAME,
        tokenizer=MODEL_NAME,
        top_k=None,
        truncation=True,
        max_length=512,
    )

    logger.info("sentiment_model_loaded", model=MODEL_NAME)
    return pipe


# Core analysis functions

def analyze_article(title: str, description: str="") -> dict:
    """

    Run sentiment analysis on a single news article.
 
    Combines title and description for better context.
    Title carries more weight so it's repeated.
 
    Args:
        title:       Article headline
        description: Article summary/description (optional)
 
    Returns:
        Dict with keys:
            label:  "bullish" | "bearish" | "neutral"
            score:  float from -1.0 (most bearish) to 1.0 (most bullish)
            raw:    raw model output for debugging
 
    Example:
        result = analyze_article(
            "Fed raises rates by 25bps",
            "Federal Reserve increases benchmark rate amid inflation concerns"
        )
        print(result["label"])   # "bearish"
        print(result["score"])   # -0.82
    
    """

    #Combine title and desciption for richer context
    #Title is more important so we weight it by including it twice

    text = f"{{title}. {title}. {description}. strip()}"

    #truncate to aavoid tokenizer warnings (512 token limit)
    text = text[:1000]

    try:
        pipe = _load_pipeline()
        results = pipe(text)[0] # return slist of {label, score} dicts


        #find the highest scoring label
        best = max(results, key=lambda x: x["score"])
        raw_label = best["label"].lower()
        confidence = best["score"]

        #map finbert label to our gold trading label
        trading_label = LABEL_MAP.get(raw_label, "neutral")

        #convert to signed score: bullish=positive, bearish=negative 
        if trading_label == "bullish":
            signed_score = confidence
        elif trading_label == "bearish":
            signed_score = -confidence
        else:
            signed_score = 0.0


        return{
            "label": trading_label,
            "score": round(signed_score, 4),
            "confidence": round(confidence, 4),
            "raw": results,
        }       
    
    except Exception as exc:
        logger.error("sentiment_analysis_failed", error=str(exc), title=title[:50])
        return{
            "label": "neutral",
            "score": 0.0,
            "confidence": 0.0,
            "raw": [],
        }
    

def analyze_batch(articles: list[dict]) -> list[dict]:
    """
    
    Run sentiment analysis on a list of articles.
    Adds sentiment_label and sentiment_score to each article dict.
 
    Args:
        articles: List of article dicts from fetcher.py
                  Each must have 'title' and optionally 'description'
 
    Returns:
        Same list with sentiment_label and sentiment_score added to each dict.
 
    Example:
        articles = fetch_all_gold_news()
        articles = analyze_batch(articles)
        bullish = [a for a in articles if a["sentiment_label"] == "bullish"]
    
    """

    if not articles:
        return []
    
    logger.info("analyzing_batch", count=len(articles))

    results = []

    for article in articles:
        sentimenet = analyze_article(
            title=article.get("title", ""),
            description=article.get("description", ""),
        )
        article["sentiment_label"] = sentimenet["label"]
        article["sentiment_score"] = sentimenet["score"]
        results.append(article)
    

    labels = [a["sentiment_label"] for a in results]
    bullish = labels.count("bullish")
    bearish = labels.count("bearish")
    neutral = labels.count("neutral")


    logger.info(
        "batch_analysis_complete",
        total=len(results),
        bullish=bullish,
        bearish=bearish,
        neutral=neutral,
    )

    return results


def compute_daily_sentiment_score(articles:list[dict]) -> dict:
    """

    Aggregate individual article sentiment scores into a single daily score.
 
    Method:
        1. Average all sentiment scores (range -1.0 to 1.0)
        2. Classify the average as bullish/bearish/neutral using thresholds
 
    Thresholds:
        score > 0.15  → bullish
        score < -0.15 → bearish
        otherwise     → neutral
 
    Args:
        articles: List of articles with sentiment_score already set
 
    Returns:
        Dict with keys:
            score:         float -1.0 to 1.0
            label:         "bullish" | "bearish" | "neutral"
            article_count: total articles analyzed
            bullish_count: articles classified as bullish
            bearish_count: articles classified as bearish
            neutral_count: articles classified as neutral
 
    Example:
        articles = analyze_batch(fetch_all_gold_news())
        daily = compute_daily_sentiment_score(articles)
        print(f"Today's gold sentiment: {daily['label']} ({daily['score']:.2f})")

    """


    if not articles:
        return{
            "score": 0.0,
            "label": "neutral",
            "article_count": 0,
            "bullish_count": 0,
            "bearish_count": 0,        
            "neutral_count": 0,
        }
    
    scores = [a.get("sentiment_score"), 0.0 for a in articles]
    labels = [a.get("sentiment_label", "neutral") for a in articles]

    avg_score = sum(scores) / len(scores)

    #classify overall sentiment
    if avg_score > 0.15:
        overall_label = "bullish"
    elif avg_score < -0.15:
        overall_label = "bearish"
    else: 
        overall_label = "neutral"

    result = {
        "score": round(avg_score, 4),
        "label": overall_label,
        "article_count": len(articles),
        "bullish_count": labels.count("bullish"),
        "bearish_count": labels.count("bearish"),
        "neutral_count": labels.count("neutral"),
    }

    logger.info(
        "daily_sentiment_computed",
        **result,
    )


    return result


def is_model_available() -> bool:
    """
    
    Check if the transformers library and model are available.
    Used by the health check and startup to give a clear error
    if torch/transformers are not installed.
    
    """

    try: 
        import transformers
        import torch
        return True
    except ImportError:
        return False














