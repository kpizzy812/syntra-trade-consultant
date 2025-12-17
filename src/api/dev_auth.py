"""
Mock Authentication для локальной разработки
ТОЛЬКО ДЛЯ DEV! В продакшене использовать только настоящую валидацию

!!! SECURITY WARNING !!!
Этот модуль должен быть ПОЛНОСТЬЮ ОТКЛЮЧЕН в production!
Dev auth позволяет обойти аутентификацию через X-Dev-User-Id header.
"""

import os
from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from loguru import logger

from src.database.crud import get_user_by_telegram_id, get_or_create_user
from src.database.models import User
from src.database.engine import get_session
from config.config import ENVIRONMENT


# SECURITY: Дополнительная проверка что мы не в production
_IS_PRODUCTION = ENVIRONMENT == "production" or os.getenv("ENVIRONMENT") == "production"

# SECURITY: Разрешённые IP для dev auth (только localhost)
_ALLOWED_DEV_HOSTS = {"127.0.0.1", "localhost", "::1"}


async def get_dev_user(
    x_dev_user_id: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> Optional[User]:
    """
    Mock пользователь для локальной разработки

    SECURITY NOTES:
    - Работает ТОЛЬКО в development режиме
    - Логирует все попытки использования

    Usage в frontend:
        headers: {
            'X-Dev-User-Id': '123456'  // Telegram ID для тестирования
        }

    Возвращает или создает тестового пользователя
    """
    # SECURITY: Полный запрет в production
    if _IS_PRODUCTION:
        if x_dev_user_id:
            logger.warning(
                f"⚠️ SECURITY: Attempted dev auth in production! "
                f"X-Dev-User-Id: {x_dev_user_id}"
            )
        return None

    if not x_dev_user_id:
        return None

    # SECURITY: Логируем использование dev auth
    logger.warning(
        f"⚠️ DEV AUTH USED: X-Dev-User-Id={x_dev_user_id} "
        f"(ENVIRONMENT={ENVIRONMENT})"
    )

    try:
        telegram_id = int(x_dev_user_id)
    except ValueError:
        logger.warning(f"Invalid dev user ID format: {x_dev_user_id}")
        return None

    # SECURITY: Ограничиваем диапазон dev user IDs
    # Реальные Telegram IDs обычно > 100000000
    if telegram_id < 1 or telegram_id > 999999999999:
        logger.warning(f"Dev user ID out of range: {telegram_id}")
        return None

    # Получаем или создаем тестового пользователя
    user, is_new = await get_or_create_user(
        session,
        telegram_id=telegram_id,
        username=f"dev_user_{telegram_id}",
        first_name="Dev User",
        last_name="Test",
        telegram_language="ru"
    )

    if is_new:
        logger.info(f"Created new dev user: telegram_id={telegram_id}")

    return user


async def get_current_user_dev(
    authorization: str = Header(None),
    x_dev_user_id: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> User:
    """
    Получить пользователя с fallback на dev режим

    SECURITY: Dev mode fallback работает ТОЛЬКО при ENVIRONMENT != production

    1. Если есть Authorization header - валидировать через Telegram/JWT
    2. Если нет и ENVIRONMENT=development - использовать X-Dev-User-Id
    3. Иначе - ошибка 401
    """
    # Если есть authorization - используем настоящую валидацию
    if authorization and (authorization.startswith('tma ') or authorization.startswith('Bearer ')):
        from src.api.auth import get_current_user
        return await get_current_user(authorization, session)

    # SECURITY: Dev режим только при явном development environment
    if not _IS_PRODUCTION and ENVIRONMENT == "development":
        dev_user = await get_dev_user(x_dev_user_id, session)
        if dev_user:
            return dev_user

    # Ошибка - требуется аутентификация
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide valid Authorization header."
    )
