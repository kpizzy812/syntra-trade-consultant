# coding: utf-8
"""
Broadcast Service - система рассылки сообщений

Поддерживает:
- Текст с entities (форматирование из Telegram)
- Медиа (фото, видео, документы, анимации)
- Inline кнопки (URL)
- Выбор аудитории по подпискам
- Периодические рассылки
"""

import asyncio
import json
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Tuple

from aiogram import Bot
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    MessageEntity,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from loguru import logger
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import (
    User,
    Subscription,
    BroadcastTemplate,
    BroadcastLog,
    BroadcastStatus,
    BroadcastTargetAudience,
    SubscriptionTier,
)


# ===========================
# CRUD OPERATIONS
# ===========================


async def create_broadcast_template(
    session: AsyncSession,
    name: str,
    created_by: int,
    text: Optional[str] = None,
    entities_json: Optional[str] = None,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
    buttons_json: Optional[str] = None,
    target_audience: str = BroadcastTargetAudience.ALL.value,
    is_periodic: bool = False,
    period_hours: Optional[int] = None,
) -> BroadcastTemplate:
    """Создать новый шаблон рассылки"""
    template = BroadcastTemplate(
        name=name,
        text=text,
        entities_json=entities_json,
        media_type=media_type,
        media_file_id=media_file_id,
        buttons_json=buttons_json,
        target_audience=target_audience,
        is_periodic=is_periodic,
        period_hours=period_hours,
        created_by=created_by,
        status=BroadcastStatus.DRAFT.value,
    )

    if is_periodic and period_hours:
        template.next_send_at = datetime.now(UTC) + timedelta(hours=period_hours)

    session.add(template)
    await session.commit()
    await session.refresh(template)

    logger.info(f"Created broadcast template: {template.id} - {name}")
    return template


async def get_broadcast_template(
    session: AsyncSession, template_id: int
) -> Optional[BroadcastTemplate]:
    """Получить шаблон по ID"""
    stmt = select(BroadcastTemplate).where(BroadcastTemplate.id == template_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_templates(
    session: AsyncSession,
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> List[BroadcastTemplate]:
    """Получить все шаблоны"""
    stmt = select(BroadcastTemplate).order_by(BroadcastTemplate.created_at.desc())

    if not include_inactive:
        stmt = stmt.where(BroadcastTemplate.is_active.is_(True))

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_periodic_templates_due(session: AsyncSession) -> List[BroadcastTemplate]:
    """Получить периодические шаблоны, готовые к отправке"""
    now = datetime.now(UTC)
    stmt = select(BroadcastTemplate).where(
        and_(
            BroadcastTemplate.is_periodic.is_(True),
            BroadcastTemplate.is_active.is_(True),
            BroadcastTemplate.status != BroadcastStatus.SENDING.value,
            BroadcastTemplate.next_send_at <= now,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_template(
    session: AsyncSession,
    template_id: int,
    **kwargs,
) -> Optional[BroadcastTemplate]:
    """Обновить шаблон"""
    template = await get_broadcast_template(session, template_id)
    if not template:
        return None

    for key, value in kwargs.items():
        if hasattr(template, key):
            setattr(template, key, value)

    await session.commit()
    await session.refresh(template)
    return template


async def delete_template(session: AsyncSession, template_id: int) -> bool:
    """Удалить шаблон"""
    template = await get_broadcast_template(session, template_id)
    if not template:
        return False

    await session.delete(template)
    await session.commit()
    logger.info(f"Deleted broadcast template: {template_id}")
    return True


async def create_broadcast_log(
    session: AsyncSession,
    template_id: int,
    total_recipients: int,
) -> BroadcastLog:
    """Создать лог рассылки"""
    log = BroadcastLog(
        template_id=template_id,
        total_recipients=total_recipients,
        status=BroadcastStatus.SENDING.value,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def update_broadcast_log(
    session: AsyncSession,
    log_id: int,
    **kwargs,
) -> Optional[BroadcastLog]:
    """Обновить лог рассылки"""
    stmt = select(BroadcastLog).where(BroadcastLog.id == log_id)
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        return None

    for key, value in kwargs.items():
        if hasattr(log, key):
            setattr(log, key, value)

    await session.commit()
    await session.refresh(log)
    return log


# ===========================
# AUDIENCE SELECTION
# ===========================


async def get_target_users(
    session: AsyncSession,
    target_audience: str,
) -> List[User]:
    """
    Получить пользователей по целевой аудитории

    Возвращает только пользователей с telegram_id (не забаненных)
    """
    base_query = select(User).where(
        and_(
            User.telegram_id.isnot(None),
            User.is_banned.is_(False),
        )
    ).options(selectinload(User.subscription))

    now = datetime.now(UTC)

    if target_audience == BroadcastTargetAudience.ALL.value:
        stmt = base_query

    elif target_audience == BroadcastTargetAudience.PREMIUM.value:
        # Пользователи с активной подпиской (не FREE)
        stmt = base_query.join(Subscription).where(
            and_(
                Subscription.is_active.is_(True),
                Subscription.tier != SubscriptionTier.FREE.value,
            )
        )

    elif target_audience == BroadcastTargetAudience.FREE.value:
        # Пользователи без подписки или с FREE
        stmt = base_query.outerjoin(Subscription).where(
            or_(
                Subscription.id.is_(None),
                Subscription.tier == SubscriptionTier.FREE.value,
                Subscription.is_active.is_(False),
            )
        )

    elif target_audience == BroadcastTargetAudience.BASIC.value:
        stmt = base_query.join(Subscription).where(
            and_(
                Subscription.is_active.is_(True),
                Subscription.tier == SubscriptionTier.BASIC.value,
            )
        )

    elif target_audience == BroadcastTargetAudience.VIP.value:
        stmt = base_query.join(Subscription).where(
            and_(
                Subscription.is_active.is_(True),
                Subscription.tier == SubscriptionTier.VIP.value,
            )
        )

    elif target_audience == BroadcastTargetAudience.TRIAL.value:
        stmt = base_query.join(Subscription).where(
            and_(
                Subscription.is_trial.is_(True),
                Subscription.is_active.is_(True),
            )
        )

    elif target_audience == BroadcastTargetAudience.INACTIVE_7D.value:
        threshold = now - timedelta(days=7)
        stmt = base_query.where(User.last_activity < threshold)

    elif target_audience == BroadcastTargetAudience.INACTIVE_30D.value:
        threshold = now - timedelta(days=30)
        stmt = base_query.where(User.last_activity < threshold)

    elif target_audience == BroadcastTargetAudience.NEW_24H.value:
        threshold = now - timedelta(hours=24)
        stmt = base_query.where(User.created_at >= threshold)

    elif target_audience == BroadcastTargetAudience.NEW_7D.value:
        threshold = now - timedelta(days=7)
        stmt = base_query.where(User.created_at >= threshold)

    else:
        # По умолчанию - все
        stmt = base_query

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_target_users(
    session: AsyncSession,
    target_audience: str,
) -> int:
    """Подсчитать количество пользователей в целевой аудитории"""
    users = await get_target_users(session, target_audience)
    return len(users)


# ===========================
# MESSAGE FORMATTING
# ===========================


def parse_entities_from_message(message: Message) -> Optional[str]:
    """
    Извлечь entities из сообщения и сохранить как JSON

    Поддерживает ВСЕ типы Telegram entities:
    bold, italic, underline, strikethrough, spoiler, code, pre,
    text_link, text_mention, custom_emoji, blockquote, expandable_blockquote
    """
    entities = message.entities or message.caption_entities
    if not entities:
        return None

    entities_list = []
    for entity in entities:
        entity_dict = {
            "type": entity.type,
            "offset": entity.offset,
            "length": entity.length,
        }

        if entity.url:
            entity_dict["url"] = entity.url
        if entity.user:
            entity_dict["user_id"] = entity.user.id
        if entity.language:
            entity_dict["language"] = entity.language
        if entity.custom_emoji_id:
            entity_dict["custom_emoji_id"] = entity.custom_emoji_id

        entities_list.append(entity_dict)

    return json.dumps(entities_list, ensure_ascii=False)


def restore_entities_from_json(entities_json: str) -> List[MessageEntity]:
    """Восстановить entities из JSON"""
    if not entities_json:
        return []

    try:
        entities_list = json.loads(entities_json)
        result = []

        for e in entities_list:
            result.append(MessageEntity(
                type=e["type"],
                offset=e["offset"],
                length=e["length"],
                url=e.get("url"),
                language=e.get("language"),
                custom_emoji_id=e.get("custom_emoji_id"),
            ))

        return result
    except (json.JSONDecodeError, KeyError) as ex:
        logger.error(f"Failed to restore entities: {ex}")
        return []


def parse_buttons_json(buttons_json: str) -> Optional[InlineKeyboardMarkup]:
    """
    Восстановить клавиатуру из JSON

    Формат: [[{"text": "Button 1", "url": "https://..."}], [...]]
    """
    if not buttons_json:
        return None

    try:
        buttons_data = json.loads(buttons_json)
        keyboard = []

        for row in buttons_data:
            keyboard_row = []
            for btn in row:
                keyboard_row.append(
                    InlineKeyboardButton(text=btn["text"], url=btn["url"])
                )
            keyboard.append(keyboard_row)

        return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
    except (json.JSONDecodeError, KeyError) as ex:
        logger.error(f"Failed to parse buttons: {ex}")
        return None


def create_buttons_json(buttons: List[List[Dict[str, str]]]) -> str:
    """
    Создать JSON для кнопок

    Args:
        buttons: [[{"text": "...", "url": "..."}], ...]
    """
    return json.dumps(buttons, ensure_ascii=False)


# ===========================
# BROADCAST SENDING
# ===========================


async def send_broadcast_message(
    bot: Bot,
    user_id: int,
    text: Optional[str],
    entities: Optional[List[MessageEntity]],
    media_type: Optional[str],
    media_file_id: Optional[str],
    reply_markup: Optional[InlineKeyboardMarkup],
) -> Tuple[bool, Optional[str]]:
    """
    Отправить сообщение пользователю

    Returns:
        (success, error_message)
    """
    try:
        if media_type and media_file_id:
            # Отправка с медиа
            if media_type == "photo":
                await bot.send_photo(
                    chat_id=user_id,
                    photo=media_file_id,
                    caption=text,
                    caption_entities=entities,
                    reply_markup=reply_markup,
                )
            elif media_type == "video":
                await bot.send_video(
                    chat_id=user_id,
                    video=media_file_id,
                    caption=text,
                    caption_entities=entities,
                    reply_markup=reply_markup,
                )
            elif media_type == "document":
                await bot.send_document(
                    chat_id=user_id,
                    document=media_file_id,
                    caption=text,
                    caption_entities=entities,
                    reply_markup=reply_markup,
                )
            elif media_type == "animation":
                await bot.send_animation(
                    chat_id=user_id,
                    animation=media_file_id,
                    caption=text,
                    caption_entities=entities,
                    reply_markup=reply_markup,
                )
            else:
                # Неизвестный тип - отправляем как документ
                await bot.send_document(
                    chat_id=user_id,
                    document=media_file_id,
                    caption=text,
                    caption_entities=entities,
                    reply_markup=reply_markup,
                )
        else:
            # Только текст
            if text:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    entities=entities,
                    reply_markup=reply_markup,
                )
            else:
                return False, "No content to send"

        return True, None

    except TelegramForbiddenError:
        return False, "blocked"
    except TelegramBadRequest as e:
        return False, str(e)
    except Exception as e:
        logger.exception(f"Error sending broadcast to {user_id}: {e}")
        return False, str(e)


async def execute_broadcast(
    bot: Bot,
    session: AsyncSession,
    template: BroadcastTemplate,
    delay_between_messages: float = 0.05,
) -> BroadcastLog:
    """
    Выполнить рассылку по шаблону

    Args:
        bot: Bot instance
        session: Database session
        template: Шаблон рассылки
        delay_between_messages: Задержка между сообщениями (сек)

    Returns:
        BroadcastLog с результатами
    """
    # Получаем целевых пользователей
    users = await get_target_users(session, template.target_audience)

    if not users:
        logger.warning(f"No users found for broadcast {template.id}")
        # Создаем пустой лог
        log = await create_broadcast_log(session, template.id, 0)
        log = await update_broadcast_log(
            session, log.id,
            status=BroadcastStatus.COMPLETED.value,
            completed_at=datetime.now(UTC),
        )
        return log

    # Создаем лог
    log = await create_broadcast_log(session, template.id, len(users))

    # Обновляем статус шаблона
    await update_template(session, template.id, status=BroadcastStatus.SENDING.value)

    # Восстанавливаем форматирование
    entities = (
        restore_entities_from_json(template.entities_json)
        if template.entities_json else None
    )
    reply_markup = (
        parse_buttons_json(template.buttons_json)
        if template.buttons_json else None
    )

    sent_count = 0
    failed_count = 0
    blocked_count = 0
    errors = []

    logger.info(f"Starting broadcast {template.id} to {len(users)} users")

    for user in users:
        success, error = await send_broadcast_message(
            bot=bot,
            user_id=user.telegram_id,
            text=template.text,
            entities=entities,
            media_type=template.media_type,
            media_file_id=template.media_file_id,
            reply_markup=reply_markup,
        )

        if success:
            sent_count += 1
        else:
            failed_count += 1
            if error == "blocked":
                blocked_count += 1
            else:
                errors.append({"user_id": user.telegram_id, "error": error})

        # Задержка для избежания rate limit
        await asyncio.sleep(delay_between_messages)

    # Обновляем лог
    errors_data = json.dumps(errors[:100], ensure_ascii=False) if errors else None
    log = await update_broadcast_log(
        session, log.id,
        sent_count=sent_count,
        failed_count=failed_count,
        blocked_count=blocked_count,
        errors_json=errors_data,
        status=BroadcastStatus.COMPLETED.value,
        completed_at=datetime.now(UTC),
    )

    # Обновляем статистику шаблона
    await update_template(
        session, template.id,
        status=BroadcastStatus.COMPLETED.value,
        last_sent_at=datetime.now(UTC),
        total_sent=template.total_sent + sent_count,
        total_delivered=template.total_delivered + sent_count,
        total_failed=template.total_failed + failed_count,
    )

    # Для периодических шаблонов - планируем следующую отправку
    if template.is_periodic and template.period_hours:
        next_send = datetime.now(UTC) + timedelta(hours=template.period_hours)
        await update_template(
            session, template.id,
            next_send_at=next_send,
            status=BroadcastStatus.SCHEDULED.value,
        )

    logger.info(
        f"Broadcast {template.id} completed: "
        f"sent={sent_count}, failed={failed_count}, blocked={blocked_count}"
    )

    return log


async def send_preview_message(
    bot: Bot,
    chat_id: int,
    template: BroadcastTemplate,
) -> bool:
    """
    Отправить превью сообщения (для кнопки "Пример")

    Returns:
        True если успешно
    """
    entities = (
        restore_entities_from_json(template.entities_json)
        if template.entities_json else None
    )
    reply_markup = (
        parse_buttons_json(template.buttons_json)
        if template.buttons_json else None
    )

    success, error = await send_broadcast_message(
        bot=bot,
        user_id=chat_id,
        text=template.text,
        entities=entities,
        media_type=template.media_type,
        media_file_id=template.media_file_id,
        reply_markup=reply_markup,
    )

    if not success:
        logger.error(f"Failed to send preview: {error}")

    return success


# ===========================
# AUDIENCE LABELS
# ===========================


AUDIENCE_LABELS = {
    BroadcastTargetAudience.ALL.value: "Все пользователи",
    BroadcastTargetAudience.PREMIUM.value: "Premium подписчики",
    BroadcastTargetAudience.FREE.value: "Бесплатные пользователи",
    BroadcastTargetAudience.BASIC.value: "Basic подписчики",
    BroadcastTargetAudience.VIP.value: "VIP подписчики",
    BroadcastTargetAudience.TRIAL.value: "На пробном периоде",
    BroadcastTargetAudience.INACTIVE_7D.value: "Неактивные 7+ дней",
    BroadcastTargetAudience.INACTIVE_30D.value: "Неактивные 30+ дней",
    BroadcastTargetAudience.NEW_24H.value: "Новые за 24 часа",
    BroadcastTargetAudience.NEW_7D.value: "Новые за 7 дней",
}


def get_audience_label(audience: str) -> str:
    """Получить человекочитаемое название аудитории"""
    return AUDIENCE_LABELS.get(audience, audience)


STATUS_LABELS = {
    BroadcastStatus.DRAFT.value: "Черновик",
    BroadcastStatus.SCHEDULED.value: "Запланирована",
    BroadcastStatus.SENDING.value: "Отправляется...",
    BroadcastStatus.COMPLETED.value: "Завершена",
    BroadcastStatus.PAUSED.value: "Приостановлена",
    BroadcastStatus.CANCELLED.value: "Отменена",
}


def get_status_label(status: str) -> str:
    """Получить человекочитаемое название статуса"""
    return STATUS_LABELS.get(status, status)
