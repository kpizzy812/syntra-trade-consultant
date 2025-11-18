"""
Mock Authentication для локальной разработки
ТОЛЬКО ДЛЯ DEV! В продакшене использовать только настоящую валидацию
"""

from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from src.database.crud import get_user_by_telegram_id, get_or_create_user
from src.database.models import User
from src.database.engine import get_session
from config.config import ENVIRONMENT


async def get_dev_user(
    x_dev_user_id: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> Optional[User]:
    """
    Mock пользователь для локальной разработки

    Usage в frontend:
        headers: {
            'X-Dev-User-Id': '123456'  // Telegram ID для тестирования
        }

    Возвращает или создает тестового пользователя
    """
    # Только в dev режиме!
    if ENVIRONMENT == "production":
        return None

    if not x_dev_user_id:
        return None

    try:
        telegram_id = int(x_dev_user_id)
    except ValueError:
        return None

    # Получаем или создаем тестового пользователя
    user, _ = await get_or_create_user(
        session,
        telegram_id=telegram_id,
        username=f"dev_user_{telegram_id}",
        first_name="Dev User",
        last_name="Test",
        telegram_language="ru"
    )

    return user


async def get_current_user_dev(
    authorization: str = Header(None),
    x_dev_user_id: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
) -> User:
    """
    Получить пользователя с fallback на dev режим

    1. Если есть Authorization header - валидировать через Telegram
    2. Если нет и ENVIRONMENT=development - использовать X-Dev-User-Id
    3. Иначе - ошибка
    """
    # Если есть authorization - используем настоящую валидацию
    if authorization and authorization.startswith('tma '):
        from src.api.auth import get_current_user
        return await get_current_user(authorization, session)

    # В dev режиме - пробуем mock
    if ENVIRONMENT != "production":
        dev_user = await get_dev_user(x_dev_user_id, session)
        if dev_user:
            return dev_user

    # Ошибка
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Authorization header or X-Dev-User-Id (dev only)"
    )
