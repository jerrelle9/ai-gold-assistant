"""

APScheduler background job scheduler.
 
Runs scheduled jobs in a background thread pool so they don't
block FastAPI's async event loop.
 
Jobs defined here:
  - fetch_market_data_job   : runs every 5 minutes during NY session
  - compute_indicators_job  : runs every 15 minutes during NY session
  - pre_market_fetch_job    : runs at 3:50 AM EST to pre-load data
 
Schedule overview:
  3:50 AM EST   → pre_market_fetch_job    (loads overnight data before session)
  4:00 AM EST   → NY session opens
  Every 5 min   → fetch_market_data_job   (during session only)
  Every 15 min  → compute_indicators_job  (during session only)
  5:00 PM EST   → NY session closes
 
All times use New York timezone to handle EST/EDT automatically.

"""


from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from app.core.logging import get_logger

logger = get_logger(__name__)
NY_TZ = pytz.timezone('America/New_York')

# Symbols and timeframes to fetch on each cycle
SYMBOLS = ["XAUUSD", "DXY", "US10y"]
TIMEFRAMES = ["1m", "5m", "15m"]



# Job functions
# These are plain functions (not async) because APScheduler runs them
# in a thread pool, not in the async event loop.


def fetch_market_data_job() -> None:
    """
    Fetch the latest candles for all symbols and timeframes
    and save them to the database.
 
    Runs every 5 minutes during the NY session (4 AM – 5 PM EST).
    The 1m timeframe gives the freshest data for pattern detection.

    """

    logger.info("job_started", job="fetch_market_data")

    from app.services.market_data.fetcher import fetch_ohlcv
    from app.services.market_data.storage import save_candles

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            try:
                df = fetch_ohlcv(symbol, timeframe)
                if not df.empty:
                    inserted = save_candles(df)
                    logger.info(
                        "job_symbol_completed",
                        job="fetch_market_data",
                        symbol=symbol,
                        timeframe=timeframe,
                        inserted=inserted,
                    )
            except Exception as exc:
                logger.error(
                    "job_symbol_failed",
                    job="fetch_market_data",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(exc),
                )

    logger.info("job_completed", job="fetch_market_data")


def compute_indicators_job() -> None:
    """
    Recompute all technical indicators using the latest candle data.
 
    Runs every 15 minutes during the NY session.
    Updates ATR, VWAP, session highs/lows in the database
    so the dashboard always shows fresh levels.
    """

    logger.info("job_started", job="compute_indicators")

    from app.services.market_data.indicators import compute_and_save_indicators

    for symbol in SYMBOLS:
        for timeframe in ["5m", "15m"]:  # Indicators on 5m and 15m only
            try:
                result = compute_and_save_indicators(symbol, timeframe)
                if result:
                    logger.info(
                        "job_symbol_completed",
                        job="compute_indicators",
                        symbol=symbol,
                        timeframe=timeframe,
                        atr=result.get("atr_14"),
                        vwap=result.get("vwap"),
                    )

            except Exception as exc:
                logger.error(
                    "job_symbol_failed",
                    job="compute_indicators",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(exc),
                )

    logger.info("job_completed", job="compute_indicators")


def pre_market_fetch_job() -> None:
    """
    Pre-market data load at 3:50 AM EST.
 
    Fetches the full overnight session (Asian + London) before the
    NY session opens at 4:00 AM. This ensures:
      - Asian session high/low are ready when the briefing generates at 4 AM
      - London session levels are available for context
      - No gap in data when the session opens
    """

    logger.info("job_started", job="pre_market_fetch")

    from app.services.market_data.fetcher import fetch_ohlcv
    from app.services.market_data.storage import save_candles

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            try:
                df = fetch_ohlcv(symbol, timeframe)  # Fetch more for pre-market
                if not df.empty:
                    inserted = save_candles(df)
                    logger.info(
                        "pre_market_symbol_loaded",
                        symbol=symbol,
                        timeframe=timeframe,
                        candles=len(df),
                        inserted=inserted,
                    )

            except Exception as exc:
                logger.error(
                    "pre_market_fetch_failed",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(exc),
                )

    #after loading data, compute indicators
    compute_indicators_job()
    logger.info("job_completed", job="pre_market_fetch")


#Scheduler setup
def create_scheduler() -> BackgroundScheduler:
    """
    Build and configure the APScheduler instance.
    Called once in main.py on application startup.
 
    
    Returns a configured but not-yet-started BackgroundScheduler.
    Call scheduler.start() to begin executing jobs.
 
    Jobs registered:
      - pre_market_fetch   : 3:50 AM EST daily
      - fetch_market_data  : every 5 min, Mon–Fri, 4 AM–5 PM EST
      - compute_indicators : every 15 min, Mon–Fri, 4 AM–5 PM EST
    """

    scheduler = BackgroundScheduler(timezone=NY_TZ)

    # Job 1: Pre-market data load — 3:50 AM EST, Monday to Friday 
    scheduler.add_job(
        func=pre_market_fetch_job,
        trigger=CronTrigger(
            hour=3,
            minute=50,
            day_of_week="mon-fri",
            timezone=NY_TZ,
        ),
        id="pre_market_fetch",
        name="Pre-market data load",
        replace_existing=True,
        misfire_grace_time= 300, # Allow up to 5 min late start
    )


    # Job 2: Fetch market data every 5 minutes during NY session
    # 4:00 AM – 5:00 PM EST, Monday to Friday

    scheduler.add_job(
        func=fetch_market_data_job,
        trigger=CronTrigger(
            hour="4-17", 
            minute="*/5",
            day_of_week="mon-fri",
            timezone=NY_TZ,
        ),
        id="fetch_market_data",
        name="Fetch Market Data (5 min)",
        misfire_grace_time= 120,
        replace_existing=True,
    )

    # Job 3: Recompute indicators every 15 minutes during NY session
    scheduler.add_job(
        func=compute_indicators_job,
        trigger=CronTrigger(
            hour="4-17", 
            minute="*/15",
            day_of_week="mon-fri",
            timezone=NY_TZ,
        ),
        id="compute_indicators",
        name="Compute Technical Indicators",
        misfire_grace_time= 180,
        replace_existing=True,
    )

    logger.info(
        "scheduler_configured",
        jobs=[job.id for job in scheduler.get_jobs()],
    )

    return scheduler



# Module-level scheduler instance
# Started in main.py lifespan, stopped on shutdown
scheduler = create_scheduler()




