"""
FastAPI Server для Telegram Mini App
Запускает API endpoints для фронтенда
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.config import validate_config
from config.logging import setup_logging
from src.database.engine import init_db, dispose_engine
from src.api.router import router as api_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager для startup/shutdown events
    """
    # Startup
    logger.info("Starting Syntra API Server...")

    # Initialize database
    await init_db()
    logger.info("Database initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down Syntra API Server...")
    await dispose_engine()
    logger.info("Database connections closed")


# Создаем FastAPI приложение
app = FastAPI(
    title="Syntra Trade Consultant API",
    description="API для Telegram Mini App",
    version="1.0.0",
    lifespan=lifespan,
)


# Настраиваем CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "http://127.0.0.1:3000",  # Alternative localhost
        "https://*.vercel.app",  # Vercel deployments
        "https://*.ngrok-free.app",  # ngrok для тестирования
        "https://*.ngrok.io",  # старый формат ngrok
        # TODO: Добавить production URL когда будет деплой
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Подключаем API router (уже включает все sub-роутеры)
app.include_router(api_router)


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


# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler
    """
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if app.debug else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Setup logging
    setup_logging()

    # Validate configuration
    if not validate_config():
        logger.error("Configuration validation failed. Please check your .env file.")
        exit(1)

    logger.info("Configuration validated successfully")

    # Run server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8003,  # Порт 8003 для Mini App (8000=syntra, 8002=leadmagnet)
        reload=True,  # Hot reload для разработки
        log_level="info",
    )
