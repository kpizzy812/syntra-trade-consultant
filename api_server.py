"""
FastAPI Server для Telegram Mini App
Запускает API endpoints для фронтенда
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config.config import validate_config, WEBAPP_URL
from config.logging import setup_logging
from src.database.engine import dispose_engine
from src.api.router import router as api_router
from src.api.security import SecurityMiddleware
from src.services.forward_test.scheduler import ForwardTestScheduler

# Setup logging at module level (must run before app creation)
# This ensures logging works when uvicorn imports the module
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager для startup/shutdown events
    """
    import asyncio

    # Startup
    logger.info("Starting Syntra API Server...")

    # NOTE: Database tables managed by Alembic migrations
    # Run: alembic upgrade head

    # NOTE: Security cleanup отключён - очистка происходит автоматически
    # при каждом запросе в SecurityStorage.add_request() и is_banned()

    # Start Forward Test Scheduler (paper trading monitoring)
    forward_test_scheduler = ForwardTestScheduler()
    forward_test_scheduler.start()
    logger.info("Forward Test Scheduler started (generation/monitor/aggregation)")

    yield

    # Shutdown
    logger.info("Shutting down Syntra API Server...")

    # Stop Forward Test Scheduler
    forward_test_scheduler.stop()
    logger.info("Forward Test Scheduler stopped")

    await dispose_engine()
    logger.info("Database connections closed")


# Инициализируем rate limiter
# SECURITY: Защита от DDoS и брутфорса
# 300 запросов в минуту на IP адрес (можно настроить в .env)
# Примечание: это по IP, а не по юзеру, так что за роутером
# может быть много юзеров
rate_limit = os.getenv("API_RATE_LIMIT", "300/minute")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[rate_limit],  # Глобальный лимит на все endpoints
    storage_uri="memory://",  # Используем in-memory storage (для production лучше Redis)
)

# Создаем FastAPI приложение
app = FastAPI(
    title="Syntra Trade Consultant API",
    description="API для Telegram Mini App",
    version="1.0.0",
    lifespan=lifespan,
)

# Добавляем limiter state в app
app.state.limiter = limiter

# Регистрируем обработчик ошибок rate limit
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Настраиваем CORS для фронтенда
# SECURITY: Используем только точные домены, без wildcards
allowed_origins = [
    "http://localhost:3000",  # Local development
    "http://127.0.0.1:3000",  # Alternative localhost
    "https://ai.syntratrade.xyz",  # Production domain
]

# Добавляем WEBAPP_URL из конфига если он отличается
if WEBAPP_URL and WEBAPP_URL not in allowed_origins:
    allowed_origins.append(WEBAPP_URL)

# В development режиме можно добавить ngrok (но только если явно указан в .env)
if os.getenv("ENVIRONMENT") == "development":
    ngrok_url = os.getenv("NGROK_URL")
    if ngrok_url and ngrok_url not in allowed_origins:
        allowed_origins.append(ngrok_url)
        logger.warning(f"⚠️ Development mode: Added ngrok URL to CORS: {ngrok_url}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔒 SECURITY: Add comprehensive security middleware
# Includes: rate limiting, IP banning, pattern detection, input validation
app.add_middleware(SecurityMiddleware)


# 🔒 SECURITY: Security Headers Middleware
# Защита от XSS, clickjacking, MIME sniffing и других атак
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Добавляет security headers ко всем ответам

    Headers:
    - Content-Security-Policy: Защита от XSS атак
    - X-Content-Type-Options: Защита от MIME sniffing
    - X-Frame-Options: Защита от clickjacking
    - X-XSS-Protection: Дополнительная защита от XSS (legacy browsers)
    - Referrer-Policy: Контроль referrer информации
    - Permissions-Policy: Контроль browser features
    """
    response = await call_next(request)

    # Content Security Policy (CSP)
    # ВАЖНО: Настроено для Next.js + PostHog + Telegram Mini App
    is_production = os.getenv("ENVIRONMENT") == "production"

    csp_directives = [
        "default-src 'self'",
        # Scripts: Next.js требует 'unsafe-eval' в dev, 'unsafe-inline' для inline scripts
        "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://telegram.org https://cdn.jsdelivr.net https://us.i.posthog.com https://us-assets.i.posthog.com https://*.posthog.com",
        # Styles: Разрешаем inline styles для Next.js + Tailwind
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        # Fonts: Google Fonts + локальные
        "font-src 'self' https://fonts.gstatic.com data:",
        # Images: Разрешаем data: для base64, blob: для динамических, CDN для иконок
        "img-src 'self' data: blob: https: http:",
        # Connect: API запросы (PostHog, backend API, Telegram) - разрешаем все для dev
        "connect-src 'self' https: http: ws: wss: data: blob:",
        # Frame: Разрешаем telegram.org для Telegram Mini App
        "frame-src 'self' https://telegram.org https://web.telegram.org",
        # Object/Embed: Блокируем Flash и другие плагины
        "object-src 'none'",
        "base-uri 'self'",
        # Upgrade insecure requests в production
        "upgrade-insecure-requests" if is_production else "",
    ]

    # Убираем пустые директивы
    csp = "; ".join(filter(None, csp_directives))
    response.headers["Content-Security-Policy"] = csp

    # X-Content-Type-Options: Блокируем MIME sniffing
    # Браузер не будет пытаться угадать MIME type
    response.headers["X-Content-Type-Options"] = "nosniff"

    # X-Frame-Options: Защита от clickjacking
    # SAMEORIGIN - разрешаем фреймить только с того же origin
    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    # X-XSS-Protection: Legacy защита от XSS для старых браузеров
    # 1; mode=block - включаем XSS фильтр и блокируем страницу при обнаружении
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Referrer-Policy: Контролируем передачу referrer
    # strict-origin-when-cross-origin - полный referrer для same-origin, только origin для cross-origin
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions-Policy: Отключаем ненужные browser features
    # Экономим ресурсы и повышаем безопасность
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )

    # Strict-Transport-Security (HSTS): Принудительный HTTPS
    # Включаем только в production и только для HTTPS
    if is_production and request.url.scheme == "https":
        # max-age=31536000 (1 год), includeSubDomains, preload
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    return response


# Подключаем API router (уже включает все sub-роутеры)
# Добавляем префикс /api для всех API endpoints
app.include_router(api_router, prefix="/api")


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint
    """
    return {
        "service": "Syntra Trade Consultant API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


# Health check endpoint
@app.get("/health")
async def health():
    """
    Health check endpoint
    """
    return {"status": "healthy"}


# Error handler for HTTPException (must be before generic Exception handler)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle HTTPException properly - return correct status code and detail
    """
    # Log 4xx as warning, 5xx as error
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    elif exc.status_code >= 400:
        logger.warning(f"HTTP {exc.status_code}: {exc.detail}")

    # Return proper response with original status code
    content = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )


# Error handler for unexpected exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unexpected errors
    """
    # Don't catch HTTPException here (handled above)
    if isinstance(exc, HTTPException):
        raise exc

    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if getattr(app, 'debug', False) else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Validate configuration
    if not validate_config():
        logger.error("Configuration validation failed. Please check your .env file.")
        exit(1)

    logger.info("Configuration validated successfully")

    # Run server
    # SECURITY: host="127.0.0.1" - слушаем только localhost
    # Доступ извне только через nginx reverse proxy
    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",  # 🔒 LOCALHOST ONLY - доступ только через nginx
        port=8003,  # Порт 8003 для Mini App (8000=syntra, 8002=leadmagnet)
        reload=True,  # Hot reload для разработки
        log_level="info",
    )
