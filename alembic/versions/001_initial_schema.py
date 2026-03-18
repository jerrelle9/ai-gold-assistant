"""Initial schema — create all tables

Revision ID: 001
Revises:
Create Date: 10/03/2026

Creates all tables for the Gold Trading AI project:
  - market_data
  - technical_indicators
  - news_articles
  - sentiment_scores
  - detected_patterns
  - alerts
  - economic_events
  - daily_briefings
  - trade_journal
  - backtest_runs
  - backtest_trades
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 001
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "market_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(12,5), nullable=False),
        sa.Column("high", sa.Numeric(12,5), nullable=False),
        sa.Column("low", sa.Numeric(12,5), nullable=False),
        sa.Column("close", sa.Numeric(12,5), nullable=False),
        sa.Column("volume", sa.Numeric(20,2), nullable=False),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_market_data")    
    )
    op.create_index("ix_market_data_symbol_tf_ts", "market_data", ["symbol", "timeframe", "timestamp"])


    op.create_table(
        "technical_indicators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atr_14", sa.Numeric(12,5), nullable=True),
        sa.Column("vwap", sa.Numeric(12,5), nullable=True),
        sa.Column("asian_session_high", sa.Numeric(12,5), nullable=True),
        sa.Column("asian_session_low", sa.Numeric(12,5), nullable=True),
        sa.Column("london_session_high", sa.Numeric(12,5), nullable=True),
        sa.Column("london_session_low", sa.Numeric(12,5), nullable=True),
        sa.Column("ny_session_high", sa.Numeric(12,5), nullable=True),
        sa.Column("ny_session_low", sa.Numeric(12,5), nullable=True),
        sa.Column("daily_high", sa.Numeric(12,5), nullable=True),
        sa.Column("daily_low", sa.Numeric(12,5), nullable=True),
        sa.Column("prev_day_high", sa.Numeric(12,5), nullable=True),
        sa.Column("prev_day_close", sa.Numeric(12,5), nullable=True),
        sa.Column("prev_day_low", sa.Numeric(12,5), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "timeframe", "date", name="uq_indicators"),
    )

    op.create_index("ix_indicators_sumbol_date", "technical_indicators", ["symbol", "date"])


    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(100), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("related_symbol", sa.String(20), nullable=True),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("sentiment_score", sa.Numeric(5,4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_news_published_at", "news_articles", ["published_at"])
    op.create_index("ix_news_symbol", "news_articles", ["related_symbol"])

    op.create_table(
        "detected_patterns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pattern_type", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("confidence", sa.Numeric(5,4), nullable=True),
        sa.Column("price_at_detection", sa.Numeric(5,4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patterns_symbol_ts", "dectected_patterns", ["symbol", "detected_at"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pattern_id", sa.Integer(), sa.ForeignKey("detected_patterns.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), default="info"),
        sa.Column("is_read", sa.Boolean(), default=False),
        sa.Column("triggered_At", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


    op.create_table(
        "economic_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country", sa.String(10), nullable=False),
        sa.Column("event_name", sa.String(200), nullable=False),
        sa.Column("impact", sa.String(10), nullable=True),
        sa.Column("forecast", sa.String(50), nullable=True),
        sa.Column("previous", sa.String(50), nullable=True),
        sa.Column("actual", sa.String(50), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_econ_events_event_time", "economic_events", ["event_time"])


    op.create_table(
        "daily_briefings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("briefing_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gold_prev_close", sa.Numeric(12,5), nullable=True),
        sa.Column("dxy_prev_close", sa.Numeric(12,5), nullable=True),
        sa.Column("us10y_prev_close", sa.Numeric(12,5), nullable=True),
        sa.Column("gold_asain_range_pips", sa.Numeric(10,2), nullable=True),
        sa.Column("gold_london_range_pips", sa.Numeric(10,2), nullable=True),
        sa.Column("sentiment_score", sa.Numeric(5,4), nullable=True),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("key_levels", sa.Text(), nullable=True),
        sa.Column("watchlist", sa.Text(), nullable=True),
        sa.Column("risk_notes", sa.Text(), nullable=True),
        sa.Column("generated_by_model", sa.String(50), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("briefing_date", name="uq_briefiing_date"),
    )

    op.create_table(
        "trading_journal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Numeric(12,5), nullable=False),
        sa.Column("exit_price", sa.Numeric(12,5), nullable=True),
        sa.Column("stop_loss", sa.Numeric(12,5), nullable=True),
        sa.Column("take_profit", sa.Numeric(12,5), nullable=True),
        sa.Column("position_size", sa.Numeric(10,4), nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pnl", sa.Numeric(12,2), nullable=True),
        sa.Column("pnl_pips", sa.Numeric(10,2), nullable=True),
        sa.Column("risk_reward_ratio", sa.Numeric(8,4), nullable=True),
        sa.Column("outcome", sa.String(10), nullable=True),
        sa.Column("session", sa.String(20), nullable=True),
        sa.Column("setup_type", sa.String(100), nullable=True),
        sa.Column("screenshot_path", sa.String(500), nullable=True),
        sa.Column("emotions", sa.String(50), nullable=True),
        sa.Column("followed_plan", sa.Boolean(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),


    )
    op.create_index("ix_journal_entry_time", "trading_journal", ["entry_time"])


    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("total_trades", sa.Integer(), default=0),
        sa.Column("winning_trades", sa.Integer(), default=0),
        sa.Column("losing_trades", sa.Integer(), default=0),
        sa.Column("win_rate", sa.Numeric(8,4), nullable=True),
        sa.Column("profit_facor", sa.Numeric(10,4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(10,4), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(10,4), nullable=True),
        sa.Column("avg_rr", sa.Numeric(8,4), nullable=True),
        sa.Column("total_pnl", sa.Numeric(12,2), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )


    op.create_table(

        "backtest_trades",
        sa.Column("id",sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backtest_runs.id"), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Numeric(12,5), nullable=False),
        sa.Column("exit_price", sa.Numeric(12,5), nullable=False),
        sa.Column("stop_loss", sa.Numeric(12,5), nullable=False),
        sa.Column("take_profit", sa.Numeric(12,5), nullable=False),
        sa.Column("pnl", sa.Numeric(12,2), nullable=True),
        sa.Column("pnl_pips", sa.Numeric(10,2), nullable=True),
        sa.Column("outcome", sa.String(10), nullable=True),
        sa.Column("exit_reason", sa.String(50), nullable=True),

        sa.PrimaryKeyConstraint("id")
    )

    op.create_index("ix_bt_trades_run_id", "backtest_trades", ["run_id"])

def downgrade() -> None:
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
    op.drop_table("trade_journal")
    op.drop_table("daily_briefings")
    op.drop_table("economic_events")
    op.drop_table("alerts")
    op.drop_table("detected_patterns")
    op.drop_table("sentiment_scores")
    op.drop_table("news_articles")
    op.drop_table("technical_indicators")
    op.drop_table("market_data")
