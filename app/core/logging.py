"""
Structured JSON logging using structlog.
 
Produces human-friendly coloured output in development
and machine-readable JSON in production.
"""


import logging
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    """
    Configure structlog and stdlib logging.
    Call once at application startup inside main.py.
    """


    # set stdlib root logger level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )

    #processors shared across all environments
    shared_processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level_number,
        structlog.processors.StackInfoRenderer(), 
    ]

    if settings.is_development:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Return a structlog logger bound to the given name.
 
    Usage:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("event_name", key="value")
    """

    return structlog.get_logger(name)

    