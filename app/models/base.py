"""
SQLAlchemy ORM models for the full Gold Trading AI project.

All tables are defined here so Alembic can auto-generate migrations.
Phase 1 creates the full schema upfront — this is intentional so
future phases only need to add logic, not restructure the database.

Tables:
  - market_data          Raw OHLCV candles (XAUUSD, DXY, US10Y)
  - technical_indicators Computed ATR, VWAP, session levels
  - news_articles        Raw news headlines from NewsAPI
  - sentiment_scores     Daily aggregated sentiment per symbol
  - detected_patterns    Chart patterns flagged by the detector
  - alerts               Triggered trading alerts
  - economic_events      Economic calendar events
  - daily_briefings      AI-generated pre-market reports
  - trade_journal        Trader's recorded trades
  - backtest_runs        Backtesting sessions
  - backtest_trades      Individual simulated trades per backtest
"""


from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,

)

from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class MarketData(TimestampMixin, Base):
    """
    Raw OHLCV candlestick data for certain markets
    Markets: XAUUSD, DXY, US10y
    TimeFrames: 1m, 5m, 15
    """

    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_market_data"),
        Index("ix_market_data_symbol_tf_ts", "symbol", "timeframe", "timestamp"), 
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(28), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(20,2), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=True)


    def __rep__(self) -> str:
        return f"<MarketData {self.symbol} {self.timeframe} {self.timestamp}>"
    


class TechnicalIndicator(TimestampMixin, Base):
    """
    Computed technical indicators for a given symbol, timeframe and date
    
    """

    __tablename__ = "technical_indicators"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "date", name="uq_indicators"),
        Index("ix_indicators_symbol_date", "symbol", "date"),
    )


    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


    #volatility
    atr_14: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)

    #volume-weighted
    vwap: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)

    #session levels
    asian_session_high: Mapped[Decimal] = mapped_column(Numeric(12,5),nullable=False)
    london_session_high: Mapped[Decimal] = mapped_column(Numeric(12,5),nullable=False)
    ny_session_high: Mapped[Decimal] = mapped_column(Numeric(12,5),nullable=False)
    asian_session_low: Mapped[Decimal] = mapped_column(Numeric(12,5),nullable=False)
    london_session_low: Mapped[Decimal] = mapped_column(Numeric(12,5),nullable=False)
    asian_session_low: Mapped[Decimal] = mapped_column(Numeric(12,5),nullable=False)

    daily_high: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    daily_low: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    prev_day_high: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    prev_day_low: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    prev_day_vol: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)


    def __repr__(self) -> str:
        return f"<TechnicalIndicator {self.symbol} {self.date}>"
    

class NewsArticle(TimestampMixin, Base):
    """
    Raw news headlines fetched from NewsAPI or similar
    
    """

    __tablename__ = "news_articles"
    __table_args__ = (
        Index("ix_news_published_at", "published_at"),
        Index("ix_news_symbol", "related_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content:Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    related_symbol: Mapped[str] = mapped_column(String(20), nullable=True)


    sentiment_label: Mapped[str] = mapped_column(String(20), nullable=True)
    sentiment_score: Mapped[Decimal] = mapped_column(Numeric(5,4), nullable=True)

    def __repr__ (self) -> str:
        return"<NewsArticle {self.source_name} : {self.title[:50]}>"
    



class SentimentScore(TimestampMixin, Base):
    """
    Daily Aggregaed sentiment score per symbol
    """

    __tablename__ = "sentiment_scores"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_sentiment_symbol_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False, autoincrement=True)
    symbol:Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5,4), nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    article_count:Mapped[int] = mapped_column(Integer,default=0)
    bullish_count:Mapped[int] = mapped_column(Integer,default=0)
    bearish_count:Mapped[int] = mapped_column(Integer,default=0)
    neutral_count:Mapped[int] = mapped_column(Integer,default=0)

    def __repr__(self) -> str:
        return f"<SentimentScore {self.symbol} {self.date} {self.label}>"


class DetectedPattern(TimestampMixin, Base):

    """
    Chart patterns dected during the NY session
    """

    __tablename__ = "detected_patterns"
    __table_args__ = (
        Index("ix_patterns_symbol_ts", "symbol", "detected_at"),
    )

    id:Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False, autoincrement=True)
    symbol:Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe:Mapped[str] = mapped_column(String(5), nullable=False)
    detected_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pattern_type:Mapped[str] = mapped_column(String(50), nullable=False)

    direction:Mapped[str] = mapped_column(String(10), nullable=True)
    confidence:Mapped[Decimal] = mapped_column(Numeric(5,4), nullable=True)

    price_at_detection:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)
    notes:Mapped[str] = mapped_column(Text, nullable=True)

    alerts:Mapped[list["Alert"]] = relationship("Alert", back_populates="pattern")

    def __repr__(self) -> str:
        return f"<DetectedPattern {self.pattern_type} {self.symbol} {self.detected_at}>"
    

class Alert(TimestampMixin,Base):
    """
    Alerts triggered when patterns are detected
    """


    __tablename__ = "alerts"

    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=True)
    pattern_id:Mapped[int] = mapped_column(
        Integer, ForeignKey("detected_patterns.id"), nullable=False,
    )
    symbol:Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    alert_type:Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    is_read:Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pattern: Mapped["DetectedPattern"] = relationship("DetectedPattern", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<Alert {self.alert_type} {self.symbol} {self.triggered_at}>"
    

class EconomicEvent(TimestampMixin, Base):
    """
    Scheduled economic events ( CPI, FOMC, NFP)
    """

    __tablename__ = "economic_events"
    __table_args__ = (
        Index("ix_econ_events_event_time", "event_time"),
    )

    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    country: Mapped[str] = mapped_column(String(10), nullable=False)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    impact: Mapped[str] = mapped_column(String(10), nullable=False)
    forecast: Mapped[str] = mapped_column(String(50), nullable=False)
    previous: Mapped[str] = mapped_column(String(50), nullable=False)
    actual: Mapped[str] = mapped_column(String(50), nullable=False)

    def __repr__ (self) -> str:
        return f"<EconomicEvent {self.event_name} {self.event_time}>"
    

class DailyBriefing(TimestampMixin, Base):
    """
    AI-generated pre-market briefing report
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    briefing_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    gold_prev_close: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)
    dxy_prev_close: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)
    us10y_prev_close: Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)
    gold_asian_range_pips: Mapped[Decimal] = mapped_column(Numeric(10,2), nullable=True)
    gold_london_range_pips: Mapped[Decimal] = mapped_column(Numeric(10,2), nullable=True)

    sentiment_score: Mapped[Decimal] = mapped_column(Numeric(5,4), nullable=True)
    senttiment_label : Mapped[str] = mapped_column(String(20), nullable=True)

    summary:Mapped[str] = mapped_column(Text, nullable=True)
    key_levels:Mapped[str] = mapped_column(Text, nullable=True)
    watchlist:Mapped[str] = mapped_column(Text, nullable=True)
    risk_notes:Mapped[str] = mapped_column(Text, nullable=True)

    generated_by_model: Mapped[str] = mapped_column(String(50), nullable=True)

    def __repr__ (self) -> str:
        return f"<DailyBriefing {self.briefing_date}>"
    

class TradeJournalEntry(TimestampMixin, Base):
    """
    Trader's manually recorded trade entries
    """

    __tablename__ = "trade_journal"
    __table_args__ = (
        Index("ix_journal_entry_time", "entry_time"),
    )


    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    symbol:Mapped[str] = mapped_column(String(20), default="XAUUSD")

    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    exit_price:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)
    stop_loss:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)
    take_profit:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)
    position_size:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=True)


    entry_time:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    pnl:Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=True)
    pnl_pips:Mapped[Decimal] = mapped_column(Numeric(10,2), nullable=True)
    risk_reward_ratio: Mapped[Decimal] = mapped_column(Numeric(8,4), nullable=True)
    outcome:Mapped[str] = mapped_column(String(10), nullable=True)

    session: Mapped[str] = mapped_column(String(20), nullable=True)
    setup_type : Mapped[str] = mapped_column(String(100), nullable=True)

    notes:Mapped[str] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str] = mapped_column(String(500), nullable=True)
    emotions: Mapped[str] = mapped_column(String(50), nullable=True)
    followed_plan: Mapped[bool] = mapped_column(Boolean, nullable=True)

    ai_feedback: Mapped[str] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<TradeJournalEntry {self.direction}  {self.symbol}  {self.entry_time}"
    

class BacktestRun(TimestampMixin, Base):
    """
    A single backtesting run/session.
    """

    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description:Mapped[str] = mapped_column(Text, nullable=True)

    start_date:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol:Mapped[str] = mapped_column(String(20), default="XAUUSD")
    timeframe:Mapped[str] = mapped_column(String(5), nullable=False)

    parameters:Mapped[str] = mapped_column(Text, nullable=True)

    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate:Mapped[Decimal] = mapped_column(Numeric(8,4), nullable=True)
    profit_factor:Mapped[Decimal] = mapped_column(Numeric(10,4), nullable=True)
    sharpe_ratio:Mapped[Decimal] = mapped_column(Numeric(10,4), nullable=True)
    max_drawdown:Mapped[Decimal] = mapped_column(Numeric(10,4), nullable=True)
    total_pnl:Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=True)
    avg_rr:Mapped[Decimal] = mapped_column(Numeric(8,4), nullable=True)

    trades:Mapped[list["BacktestTrade"]] = relationship("BacktestTrade", back_populates="run")

    def __repr__(self) -> str:
        return f"<BacktestRun {self.strategy_name} {self.start_date}-{self.end_date}"


class BacktestTrade(Base):
    """
    Individual simulated trade generated by a backtest run
    """

    __tablename__ = "backtest_trades"
    __table_args__ = (
        Index("ix_bt_trades_run_id", "run_id"),
    )

    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    run_id:Mapped[int] = mapped_column(Integer, ForeignKey("backtest_runs.id"), nullable=False)

    entry_time:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction:Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    exit_price:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    stop_loss:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    take_profit:Mapped[Decimal] = mapped_column(Numeric(12,5), nullable=False)
    pnl:Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=True)
    pnl_pips:Mapped[Decimal] = mapped_column(Numeric(10,2), nullable=True)
    outcome:Mapped[str] = mapped_column(String(10), nullable=True)
    exit_reason:Mapped[str] = mapped_column(String(50), nullable=True)

    run:Mapped["BacktestRun"] = relationship("BacktestRun", back_populates="trades")

    def __repr__(self) -> str:
        return f"<BacktestTrade {self.direction}  {self.entry_time}  {self.outcome}" 