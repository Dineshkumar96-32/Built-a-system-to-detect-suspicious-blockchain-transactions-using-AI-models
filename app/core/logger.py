"""
app/core/logging.py
Structured JSON logging via structlog.
"""
import logging
import sys
import structlog
from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if settings.DEBUG
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )

    # Silence noisy libs
    for lib in ("uvicorn.access", "web3.RequestManager", "web3.providers"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str = "blockshield"):
    return structlog.get_logger(name)
