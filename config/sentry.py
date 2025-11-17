# coding: utf-8
"""
Sentry configuration for error monitoring and tracking
"""
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from loguru import logger

from config.config import SENTRY_DSN, ENVIRONMENT


def init_sentry() -> None:
    """
    Initialize Sentry SDK for error monitoring

    Features:
    - Automatic error capture and reporting
    - Performance monitoring (transactions)
    - User context tracking
    - Release tracking
    - Environment separation (dev/prod)
    """
    if not SENTRY_DSN:
        logger.warning("SENTRY_DSN not configured - error monitoring disabled")
        return

    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,

            # Environment
            environment=ENVIRONMENT,

            # Integrations
            integrations=[
                AsyncioIntegration(),  # Async support
                SqlalchemyIntegration(),  # Database queries tracking
                AioHttpIntegration(),  # HTTP requests tracking
            ],

            # Performance Monitoring
            traces_sample_rate=0.1 if ENVIRONMENT == "production" else 1.0,  # 10% in prod, 100% in dev

            # Error Sampling
            sample_rate=1.0,  # Capture 100% of errors

            # Additional options
            attach_stacktrace=True,  # Include stack traces
            send_default_pii=False,  # Don't send personally identifiable info
            max_breadcrumbs=50,  # Number of breadcrumbs to keep

            # Before send hook - filter sensitive data
            before_send=before_send_hook,
        )

        logger.info(f"Sentry initialized successfully (Environment: {ENVIRONMENT})")

    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")


def before_send_hook(event, hint):
    """
    Filter/modify events before sending to Sentry

    Use this to:
    - Remove sensitive data (tokens, passwords, etc.)
    - Filter out specific errors
    - Add custom context
    """
    # Skip certain errors if needed
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']

        # Example: Skip KeyboardInterrupt
        if isinstance(exc_value, KeyboardInterrupt):
            return None

    # Remove sensitive data from event
    if event.get('request'):
        # Remove auth headers
        headers = event['request'].get('headers', {})
        if 'Authorization' in headers:
            headers['Authorization'] = '[Filtered]'
        if 'X-API-Key' in headers:
            headers['X-API-Key'] = '[Filtered]'

    return event


def set_user_context(user_id: int, username: str = None):
    """
    Set user context for Sentry events

    Args:
        user_id: Telegram user ID
        username: Telegram username (optional)
    """
    sentry_sdk.set_user({
        "id": str(user_id),
        "username": username or f"user_{user_id}"
    })


def capture_exception(error: Exception, **extra_context):
    """
    Manually capture an exception with extra context

    Args:
        error: Exception to capture
        extra_context: Additional context data
    """
    with sentry_sdk.push_scope() as scope:
        # Add extra context
        for key, value in extra_context.items():
            scope.set_extra(key, value)

        # Capture exception
        sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", **extra_context):
    """
    Capture a message (not an error) in Sentry

    Args:
        message: Message to capture
        level: Severity level (debug, info, warning, error, fatal)
        extra_context: Additional context data
    """
    with sentry_sdk.push_scope() as scope:
        # Add extra context
        for key, value in extra_context.items():
            scope.set_extra(key, value)

        # Capture message
        sentry_sdk.capture_message(message, level=level)


def add_breadcrumb(message: str, category: str = "default", level: str = "info", **data):
    """
    Add a breadcrumb (for debugging context)

    Args:
        message: Breadcrumb message
        category: Category (e.g., "auth", "query", "navigation")
        level: Severity level
        data: Additional data
    """
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data
    )
