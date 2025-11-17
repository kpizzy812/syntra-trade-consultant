# coding: utf-8
"""
Logging configuration with loguru for Syntra Trade Consultant Bot
"""
import sys
from pathlib import Path
from loguru import logger
import sentry_sdk

from config.config import LOG_LEVEL, ENVIRONMENT, SENTRY_DSN


def setup_logging() -> None:
    """
    Setup loguru logging configuration with beautiful formatting
    """
    # Remove default handler
    logger.remove()

    # Create logs directory
    logs_dir = Path(__file__).parent.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)

    # Console output with colors and formatting
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=LOG_LEVEL,
        colorize=True,
    )

    # File output - all logs
    logger.add(
        logs_dir / "bot_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="00:00",  # Rotate at midnight
        retention="7 days",  # Keep logs for 7 days
        compression="zip",  # Compress old logs
        encoding="utf-8",
    )

    # File output - errors only
    logger.add(
        logs_dir / "error_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="00:00",
        retention="30 days",  # Keep error logs longer
        compression="zip",
        encoding="utf-8",
    )

    # Sentry integration - send ERROR and CRITICAL to Sentry
    if SENTRY_DSN:
        logger.add(
            sentry_sink,
            level="ERROR",
            format="{message}",
        )

    # Suppress noisy third-party loggers
    import logging
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)  # Only errors
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    # Startup message
    logger.info(f"Syntra Bot initialized | Environment: {ENVIRONMENT} | Log level: {LOG_LEVEL}")


def sentry_sink(message):
    """
    Custom sink to send ERROR and CRITICAL logs to Sentry
    """
    record = message.record
    level = record["level"].name

    # Send to Sentry based on level
    if level == "ERROR":
        sentry_sdk.capture_message(
            record["message"],
            level="error",
            extras={
                "function": record["function"],
                "file": record["file"].path,
                "line": record["line"],
            }
        )
    elif level == "CRITICAL":
        sentry_sdk.capture_message(
            record["message"],
            level="fatal",
            extras={
                "function": record["function"],
                "file": record["file"].path,
                "line": record["line"],
            }
        )

    # If there's an exception, send it to Sentry
    if record["exception"]:
        sentry_sdk.capture_exception(record["exception"])


def get_logger(name: str):
    """
    Get logger instance (for backwards compatibility)
    Just returns loguru logger bound to the module name
    """
    return logger.bind(name=name)
