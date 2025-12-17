# coding: utf-8
"""
Broadcast handlers - админ-панель для рассылки сообщений

Функционал:
- Создание рассылки через FSM (пересылка поста)
- Выбор аудитории
- Добавление inline кнопок
- Превью перед отправкой
- Управление шаблонами (редактирование, пауза, удаление)
- Периодические рассылки
"""

import asyncio
import re
from datetime import datetime, timedelta, UTC

from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import BroadcastTemplate, BroadcastStatus, User
from src.database.engine import get_session_maker
from src.services.broadcast_service import (
    create_broadcast_template,
    get_broadcast_template,
    get_all_templates,
    update_template,
    delete_template,
    count_target_users,
    execute_broadcast,
    send_preview_message,
    parse_entities_from_message,
    create_buttons_json,
    get_audience_label,
    get_status_label,
)
from src.bot.handlers.channel_repost import (
    get_auto_repost_enabled,
    set_auto_repost_enabled,
)

router = Router(name="broadcast")


# ===========================
# FSM States
# ===========================


class BroadcastStates(StatesGroup):
    """FSM состояния для создания рассылки"""

    waiting_for_name = State()  # Ожидание названия шаблона
    waiting_for_post = State()  # Ожидание поста (текст/медиа)
    waiting_for_audience = State()  # Выбор аудитории
    waiting_for_buttons = State()  # Добавление кнопок
    waiting_for_button_text = State()  # Текст кнопки
    waiting_for_button_url = State()  # URL кнопки
    waiting_for_period = State()  # Периодичность (для авто-рассылки)
    confirm_send = State()  # Подтверждение отправки
    waiting_for_repost_link = State()  # Ожидание ссылки для репоста


class EditBroadcastStates(StatesGroup):
    """FSM для редактирования шаблона"""

    waiting_for_new_post = State()  # Новый пост
    waiting_for_new_buttons = State()  # Новые кнопки


# ===========================
# Keyboards
# ===========================


async def get_broadcast_main_menu_async() -> InlineKeyboardMarkup:
    """Главное меню рассылки (async для проверки статуса авто-репоста)"""
    auto_repost = await get_auto_repost_enabled()
    auto_repost_text = "Auto-repost: ON" if auto_repost else "Auto-repost: OFF"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Создать рассылку",
                    callback_data="broadcast_create",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Репост из канала",
                    callback_data="broadcast_repost",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Мои шаблоны",
                    callback_data="broadcast_templates_0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="broadcast_stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"📡 {auto_repost_text}",
                    callback_data="broadcast_toggle_auto_repost",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад в админку",
                    callback_data="admin_refresh",
                ),
            ],
        ]
    )


def get_broadcast_main_menu() -> InlineKeyboardMarkup:
    """Главное меню рассылки (sync fallback)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Создать рассылку",
                    callback_data="broadcast_create",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Репост из канала",
                    callback_data="broadcast_repost",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Мои шаблоны",
                    callback_data="broadcast_templates_0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="broadcast_stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📡 Auto-repost",
                    callback_data="broadcast_toggle_auto_repost",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад в админку",
                    callback_data="admin_refresh",
                ),
            ],
        ]
    )


def get_audience_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора аудитории"""
    keyboard = []

    # Основные группы
    keyboard.append([
        InlineKeyboardButton(
            text="👥 Все пользователи",
            callback_data="broadcast_audience_all",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="⭐ Premium",
            callback_data="broadcast_audience_premium",
        ),
        InlineKeyboardButton(
            text="🆓 Бесплатные",
            callback_data="broadcast_audience_free",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="🎁 На триале",
            callback_data="broadcast_audience_trial",
        ),
        InlineKeyboardButton(
            text="💎 VIP",
            callback_data="broadcast_audience_vip",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="😴 Неактивные 7д",
            callback_data="broadcast_audience_inactive_7d",
        ),
        InlineKeyboardButton(
            text="😴 Неактивные 30д",
            callback_data="broadcast_audience_inactive_30d",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="🆕 Новые 24ч",
            callback_data="broadcast_audience_new_24h",
        ),
        InlineKeyboardButton(
            text="🆕 Новые 7д",
            callback_data="broadcast_audience_new_7d",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="broadcast_cancel",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_buttons_keyboard(has_buttons: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для добавления кнопок"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="➕ Добавить кнопку",
                callback_data="broadcast_add_button",
            ),
        ],
    ]

    if has_buttons:
        keyboard.append([
            InlineKeyboardButton(
                text="🗑 Очистить кнопки",
                callback_data="broadcast_clear_buttons",
            ),
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="✅ Готово",
            callback_data="broadcast_buttons_done",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="broadcast_cancel",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_period_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора периодичности"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚫 Без повторения",
                    callback_data="broadcast_period_0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Каждые 6 часов",
                    callback_data="broadcast_period_6",
                ),
                InlineKeyboardButton(
                    text="⏰ Каждые 12 часов",
                    callback_data="broadcast_period_12",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 Каждый день",
                    callback_data="broadcast_period_24",
                ),
                InlineKeyboardButton(
                    text="📅 Каждые 3 дня",
                    callback_data="broadcast_period_72",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 Каждую неделю",
                    callback_data="broadcast_period_168",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="broadcast_cancel",
                ),
            ],
        ]
    )


def get_confirm_keyboard(template_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения отправки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👁 Пример",
                    callback_data=f"broadcast_preview_{template_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Отправить",
                    callback_data=f"broadcast_send_{template_id}",
                ),
                InlineKeyboardButton(
                    text="💾 Сохранить черновик",
                    callback_data=f"broadcast_save_{template_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="broadcast_cancel",
                ),
            ],
        ]
    )


def get_template_keyboard(template: BroadcastTemplate) -> InlineKeyboardMarkup:
    """Клавиатура управления шаблоном"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="👁 Пример",
                callback_data=f"broadcast_preview_{template.id}",
            ),
        ],
    ]

    # Отправить (если не отправляется сейчас)
    if template.status != BroadcastStatus.SENDING.value:
        keyboard.append([
            InlineKeyboardButton(
                text="📤 Отправить сейчас",
                callback_data=f"broadcast_send_{template.id}",
            ),
        ])

    # Пауза/Возобновить для периодических
    if template.is_periodic:
        if template.is_active:
            keyboard.append([
                InlineKeyboardButton(
                    text="⏸ Приостановить",
                    callback_data=f"broadcast_pause_{template.id}",
                ),
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    text="▶️ Возобновить",
                    callback_data=f"broadcast_resume_{template.id}",
                ),
            ])

    keyboard.append([
        InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"broadcast_edit_{template.id}",
        ),
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"broadcast_delete_{template.id}",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            text="« Назад",
            callback_data="broadcast_templates_0",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ===========================
# Handlers
# ===========================


@router.callback_query(F.data == "admin_broadcast")
async def broadcast_menu(callback: CallbackQuery, session: AsyncSession):
    """Главное меню рассылки"""
    # Получаем статистику
    templates = await get_all_templates(session, include_inactive=True)
    active_periodic = sum(1 for t in templates if t.is_periodic and t.is_active)
    total_sent = sum(t.total_sent for t in templates)

    # Статус авто-репоста
    auto_repost = await get_auto_repost_enabled()
    auto_repost_status = "ON" if auto_repost else "OFF"

    text = (
        "📢 <b>Система рассылки</b>\n\n"
        f"📋 Шаблонов: <b>{len(templates)}</b>\n"
        f"🔄 Активных авто-рассылок: <b>{active_periodic}</b>\n"
        f"📤 Всего отправлено: <b>{total_sent}</b>\n"
        f"📡 Авто-репост из канала: <b>{auto_repost_status}</b>\n\n"
        "Выберите действие:"
    )

    menu = await get_broadcast_main_menu_async()
    await callback.message.edit_text(text, reply_markup=menu)
    await callback.answer()


@router.callback_query(F.data == "broadcast_create")
async def broadcast_create_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания рассылки - запрос названия"""
    await state.set_state(BroadcastStates.waiting_for_name)

    text = (
        "📝 <b>Создание рассылки</b>\n\n"
        "Шаг 1/4: Введите название шаблона\n"
        "(только для вашего удобства, пользователи не увидят)"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(StateFilter(BroadcastStates.waiting_for_name))
async def broadcast_name_received(message: Message, state: FSMContext):
    """Получено название шаблона"""
    name = message.text.strip()

    if len(name) > 255:
        await message.answer("❌ Название слишком длинное (макс. 255 символов)")
        return

    await state.update_data(template_name=name)
    await state.set_state(BroadcastStates.waiting_for_post)

    text = (
        "📝 <b>Создание рассылки</b>\n\n"
        f"Название: <b>{name}</b>\n\n"
        "Шаг 2/4: Отправьте пост для рассылки\n\n"
        "Поддерживается:\n"
        "• Текст с форматированием (жирный, курсив, ссылки и т.д.)\n"
        "• Фото с подписью\n"
        "• Видео с подписью\n"
        "• Документы\n"
        "• GIF-анимации\n\n"
        "<i>Просто перешлите или напишите сообщение</i>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")]
        ]
    )

    await message.answer(text, reply_markup=keyboard)


@router.message(StateFilter(BroadcastStates.waiting_for_post))
async def broadcast_post_received(message: Message, state: FSMContext):
    """Получен пост для рассылки"""
    # Извлекаем контент
    text = None
    entities_json = None
    media_type = None
    media_file_id = None

    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id  # Лучшее качество
        text = message.caption
        entities_json = parse_entities_from_message(message)

    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
        text = message.caption
        entities_json = parse_entities_from_message(message)

    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
        text = message.caption
        entities_json = parse_entities_from_message(message)

    elif message.animation:
        media_type = "animation"
        media_file_id = message.animation.file_id
        text = message.caption
        entities_json = parse_entities_from_message(message)

    elif message.text:
        text = message.text
        entities_json = parse_entities_from_message(message)

    else:
        await message.answer(
            "❌ Неподдерживаемый тип сообщения.\n"
            "Отправьте текст, фото, видео, документ или GIF."
        )
        return

    if not text and not media_file_id:
        await message.answer("❌ Пустое сообщение. Отправьте контент.")
        return

    # Сохраняем данные
    await state.update_data(
        text=text,
        entities_json=entities_json,
        media_type=media_type,
        media_file_id=media_file_id,
        buttons=[],
    )

    await state.set_state(BroadcastStates.waiting_for_audience)

    response = (
        "✅ <b>Пост сохранён!</b>\n\n"
        "Шаг 3/4: Выберите целевую аудиторию"
    )

    await message.answer(response, reply_markup=get_audience_keyboard())


@router.callback_query(F.data.startswith("broadcast_audience_"))
async def broadcast_audience_selected(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """Выбрана аудитория"""
    audience = callback.data.replace("broadcast_audience_", "")

    # Подсчитываем пользователей
    count = await count_target_users(session, audience)

    await state.update_data(target_audience=audience, audience_count=count)
    await state.set_state(BroadcastStates.waiting_for_buttons)

    label = get_audience_label(audience)

    text = (
        f"✅ Аудитория: <b>{label}</b>\n"
        f"👥 Получателей: <b>{count}</b>\n\n"
        "Шаг 4/4: Добавьте inline-кнопки (необязательно)\n\n"
        "Кнопки появятся под вашим сообщением"
    )

    await callback.message.edit_text(text, reply_markup=get_buttons_keyboard(False))
    await callback.answer()


@router.callback_query(F.data == "broadcast_add_button")
async def broadcast_add_button(callback: CallbackQuery, state: FSMContext):
    """Добавление кнопки - запрос текста"""
    await state.set_state(BroadcastStates.waiting_for_button_text)

    text = (
        "🔘 <b>Добавление кнопки</b>\n\n"
        "Введите текст кнопки:"
    )

    cancel_btn = InlineKeyboardButton(
        text="❌ Отмена", callback_data="broadcast_buttons_back"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[cancel_btn]])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(StateFilter(BroadcastStates.waiting_for_button_text))
async def broadcast_button_text_received(message: Message, state: FSMContext):
    """Получен текст кнопки"""
    button_text = message.text.strip()

    if len(button_text) > 64:
        await message.answer("❌ Текст кнопки слишком длинный (макс. 64 символа)")
        return

    await state.update_data(current_button_text=button_text)
    await state.set_state(BroadcastStates.waiting_for_button_url)

    text = (
        f"🔘 Текст кнопки: <b>{button_text}</b>\n\n"
        "Теперь введите URL (ссылку) для кнопки:"
    )

    cancel_btn = InlineKeyboardButton(
        text="❌ Отмена", callback_data="broadcast_buttons_back"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[cancel_btn]])

    await message.answer(text, reply_markup=keyboard)


@router.message(StateFilter(BroadcastStates.waiting_for_button_url))
async def broadcast_button_url_received(message: Message, state: FSMContext):
    """Получен URL кнопки"""
    url = message.text.strip()

    # Проверяем URL
    if not url.startswith(("http://", "https://", "tg://")):
        await message.answer(
            "❌ Некорректный URL.\n"
            "URL должен начинаться с http://, https:// или tg://"
        )
        return

    data = await state.get_data()
    button_text = data.get("current_button_text", "Button")
    buttons = data.get("buttons", [])

    # Добавляем кнопку как отдельную строку
    buttons.append([{"text": button_text, "url": url}])

    await state.update_data(buttons=buttons)
    await state.set_state(BroadcastStates.waiting_for_buttons)

    text = (
        f"✅ Кнопка добавлена!\n\n"
        f"Кнопок: <b>{len(buttons)}</b>\n\n"
    )

    for i, row in enumerate(buttons, 1):
        for btn in row:
            text += f"{i}. [{btn['text']}]({btn['url']})\n"

    text += "\nДобавьте ещё или нажмите «Готово»"

    has_btns = bool(buttons)
    await message.answer(text, reply_markup=get_buttons_keyboard(has_btns))


@router.callback_query(F.data == "broadcast_clear_buttons")
async def broadcast_clear_buttons(callback: CallbackQuery, state: FSMContext):
    """Очистить все кнопки"""
    await state.update_data(buttons=[])

    text = "🗑 Кнопки очищены\n\nДобавьте кнопки или нажмите «Готово»"

    await callback.message.edit_text(text, reply_markup=get_buttons_keyboard(False))
    await callback.answer("Кнопки удалены")


@router.callback_query(F.data == "broadcast_buttons_back")
async def broadcast_buttons_back(callback: CallbackQuery, state: FSMContext):
    """Вернуться к меню кнопок"""
    await state.set_state(BroadcastStates.waiting_for_buttons)

    data = await state.get_data()
    buttons = data.get("buttons", [])

    text = "🔘 Добавьте inline-кнопки или нажмите «Готово»"

    if buttons:
        text += f"\n\nТекущие кнопки ({len(buttons)}):\n"
        for i, row in enumerate(buttons, 1):
            for btn in row:
                text += f"{i}. {btn['text']}\n"

    has_btns = bool(buttons)
    await callback.message.edit_text(
        text, reply_markup=get_buttons_keyboard(has_btns)
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_buttons_done")
async def broadcast_buttons_done(callback: CallbackQuery, state: FSMContext):
    """Кнопки готовы - переход к выбору периодичности"""
    await state.set_state(BroadcastStates.waiting_for_period)

    text = (
        "⏰ <b>Периодичность</b>\n\n"
        "Выберите, как часто повторять рассылку:\n\n"
        "• <b>Без повторения</b> - отправить один раз\n"
        "• <b>Периодично</b> - автоматически повторять"
    )

    await callback.message.edit_text(text, reply_markup=get_period_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast_period_"))
async def broadcast_period_selected(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """Выбрана периодичность - создаём шаблон"""
    period = int(callback.data.replace("broadcast_period_", ""))

    data = await state.get_data()

    # Создаём шаблон
    btns = data.get("buttons")
    buttons_json = create_buttons_json(btns) if btns else None

    template = await create_broadcast_template(
        session=session,
        name=data["template_name"],
        created_by=callback.from_user.id,
        text=data.get("text"),
        entities_json=data.get("entities_json"),
        media_type=data.get("media_type"),
        media_file_id=data.get("media_file_id"),
        buttons_json=buttons_json,
        target_audience=data["target_audience"],
        is_periodic=period > 0,
        period_hours=period if period > 0 else None,
    )

    audience_label = get_audience_label(data["target_audience"])
    audience_count = data.get("audience_count", 0)

    period_text = "Без повторения"
    if period > 0:
        if period < 24:
            period_text = f"Каждые {period} часов"
        elif period == 24:
            period_text = "Каждый день"
        elif period == 72:
            period_text = "Каждые 3 дня"
        elif period == 168:
            period_text = "Каждую неделю"
        else:
            period_text = f"Каждые {period} часов"

    text = (
        "✅ <b>Шаблон создан!</b>\n\n"
        f"📝 Название: <b>{template.name}</b>\n"
        f"👥 Аудитория: <b>{audience_label}</b>\n"
        f"📊 Получателей: <b>{audience_count}</b>\n"
        f"🔄 Периодичность: <b>{period_text}</b>\n\n"
        "Что дальше?"
    )

    await state.clear()
    kb = get_confirm_keyboard(template.id)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast_preview_"))
async def broadcast_preview(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Отправить превью шаблона"""
    template_id = int(callback.data.replace("broadcast_preview_", ""))
    template = await get_broadcast_template(session, template_id)

    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    # Отправляем полноценное превью
    success = await send_preview_message(bot, callback.message.chat.id, template)

    if success:
        await callback.answer("👁 Превью отправлено выше")
    else:
        await callback.answer("❌ Ошибка отправки превью", show_alert=True)


@router.callback_query(F.data.startswith("broadcast_send_"))
async def broadcast_send(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Запустить рассылку"""
    template_id = int(callback.data.replace("broadcast_send_", ""))
    template = await get_broadcast_template(session, template_id)

    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    if template.status == BroadcastStatus.SENDING.value:
        await callback.answer("⏳ Рассылка уже выполняется", show_alert=True)
        return

    await callback.answer("🚀 Запускаю рассылку...")

    # Запускаем рассылку в фоне
    asyncio.create_task(
        _execute_broadcast_and_notify(
            bot=bot,
            session=session,
            template=template,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
        )
    )


async def _execute_broadcast_and_notify(
    bot: Bot,
    session: AsyncSession,
    template: BroadcastTemplate,
    chat_id: int,
    message_id: int,
):
    """Выполнить рассылку и уведомить админа"""
    try:
        # Обновляем сообщение
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏳ <b>Рассылка #{template.id} выполняется...</b>\n\n"
                 f"Это может занять некоторое время.",
        )

        # Выполняем рассылку
        log = await execute_broadcast(bot, session, template)

        # Уведомляем о результате
        result_text = (
            f"✅ <b>Рассылка #{template.id} завершена!</b>\n\n"
            f"📤 Отправлено: <b>{log.sent_count}</b>\n"
            f"❌ Ошибок: <b>{log.failed_count}</b>\n"
            f"🚫 Заблокировали: <b>{log.blocked_count}</b>\n"
            f"📊 Всего: <b>{log.total_recipients}</b>\n\n"
            f"⏱ Время: {(log.completed_at - log.started_at).seconds}сек"
        )

        back_btn = InlineKeyboardButton(
            text="« Назад", callback_data="admin_broadcast"
        )
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=result_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn]]),
        )

    except Exception as e:
        logger.exception(f"Broadcast error: {e}")
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Ошибка рассылки</b>\n\n{str(e)[:200]}",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("broadcast_save_"))
async def broadcast_save_draft(callback: CallbackQuery, session: AsyncSession):
    """Сохранить как черновик"""
    template_id = int(callback.data.replace("broadcast_save_", ""))
    template = await get_broadcast_template(session, template_id)

    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    await update_template(session, template_id, status=BroadcastStatus.DRAFT.value)

    await callback.answer("💾 Сохранено как черновик")
    templates_btn = InlineKeyboardButton(
        text="📋 К шаблонам", callback_data="broadcast_templates_0"
    )
    back_btn = InlineKeyboardButton(
        text="« Назад", callback_data="admin_broadcast"
    )
    await callback.message.edit_text(
        f"💾 Шаблон «{template.name}» сохранён как черновик.\n\n"
        "Вы можете найти его в списке шаблонов.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[templates_btn], [back_btn]]
        ),
    )


@router.callback_query(F.data.startswith("broadcast_templates_"))
async def broadcast_templates_list(callback: CallbackQuery, session: AsyncSession):
    """Список шаблонов с пагинацией"""
    page = int(callback.data.replace("broadcast_templates_", ""))
    per_page = 5

    templates = await get_all_templates(
        session, include_inactive=True, limit=per_page, offset=page * per_page
    )
    all_templates = await get_all_templates(session, include_inactive=True, limit=100)
    total = len(all_templates)

    if not templates:
        text = "📋 <b>Шаблоны рассылок</b>\n\nУ вас пока нет шаблонов."
        create_btn = InlineKeyboardButton(
            text="📝 Создать", callback_data="broadcast_create"
        )
        back_btn = InlineKeyboardButton(
            text="« Назад", callback_data="admin_broadcast"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[create_btn], [back_btn]]
        )
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        return

    text = f"📋 <b>Шаблоны рассылок</b> ({total})\n\n"

    keyboard_rows = []

    for t in templates:
        status_emoji = {
            BroadcastStatus.DRAFT.value: "📝",
            BroadcastStatus.SCHEDULED.value: "⏰",
            BroadcastStatus.SENDING.value: "📤",
            BroadcastStatus.COMPLETED.value: "✅",
            BroadcastStatus.PAUSED.value: "⏸",
            BroadcastStatus.CANCELLED.value: "❌",
        }.get(t.status, "❓")

        periodic_mark = "🔄" if t.is_periodic else ""

        text += f"{status_emoji} <b>{t.name}</b> {periodic_mark}\n"
        text += f"   👥 {get_audience_label(t.target_audience)}\n"
        text += f"   📤 Отправлено: {t.total_sent}\n\n"

        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{status_emoji} {t.name[:20]}",
                callback_data=f"broadcast_view_{t.id}",
            )
        ])

    # Пагинация
    nav_row = []
    if page > 0:
        prev_cb = f"broadcast_templates_{page-1}"
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=prev_cb))
    if (page + 1) * per_page < total:
        next_cb = f"broadcast_templates_{page+1}"
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=next_cb))

    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([
        InlineKeyboardButton(text="📝 Создать", callback_data="broadcast_create")
    ])
    keyboard_rows.append([
        InlineKeyboardButton(text="« Назад", callback_data="admin_broadcast")
    ])

    await callback.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast_view_"))
async def broadcast_view_template(callback: CallbackQuery, session: AsyncSession):
    """Просмотр шаблона"""
    template_id = int(callback.data.replace("broadcast_view_", ""))
    template = await get_broadcast_template(session, template_id)

    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    audience_label = get_audience_label(template.target_audience)
    status_label = get_status_label(template.status)

    text = (
        f"📋 <b>Шаблон: {template.name}</b>\n\n"
        f"📊 Статус: <b>{status_label}</b>\n"
        f"👥 Аудитория: <b>{audience_label}</b>\n"
        f"📤 Всего отправлено: <b>{template.total_sent}</b>\n"
        f"✅ Доставлено: <b>{template.total_delivered}</b>\n"
        f"❌ Ошибок: <b>{template.total_failed}</b>\n"
    )

    if template.is_periodic:
        text += f"\n🔄 <b>Периодичность:</b> каждые {template.period_hours}ч\n"
        if template.next_send_at:
            next_str = template.next_send_at.strftime('%d.%m %H:%M')
            text += f"⏰ След. отправка: {next_str}\n"
        active_str = "Да" if template.is_active else "Нет"
        text += f"▶️ Активна: {active_str}\n"

    if template.last_sent_at:
        last_str = template.last_sent_at.strftime('%d.%m.%Y %H:%M')
        text += f"\n📅 Последняя отправка: {last_str}"

    created_str = template.created_at.strftime('%d.%m.%Y %H:%M')
    text += f"\n\n📝 Создан: {created_str}"

    await callback.message.edit_text(text, reply_markup=get_template_keyboard(template))
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast_pause_"))
async def broadcast_pause_template(callback: CallbackQuery, session: AsyncSession):
    """Приостановить периодический шаблон"""
    template_id = int(callback.data.replace("broadcast_pause_", ""))

    await update_template(
        session, template_id,
        is_active=False,
        status=BroadcastStatus.PAUSED.value,
    )

    await callback.answer("⏸ Шаблон приостановлен")

    # Обновляем вид
    template = await get_broadcast_template(session, template_id)
    if template:
        await broadcast_view_template.__wrapped__(callback, session)


@router.callback_query(F.data.startswith("broadcast_resume_"))
async def broadcast_resume_template(callback: CallbackQuery, session: AsyncSession):
    """Возобновить периодический шаблон"""
    template_id = int(callback.data.replace("broadcast_resume_", ""))

    template = await get_broadcast_template(session, template_id)
    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    # Устанавливаем следующую отправку
    next_send = datetime.now(UTC) + timedelta(hours=template.period_hours or 24)

    await update_template(
        session, template_id,
        is_active=True,
        status=BroadcastStatus.SCHEDULED.value,
        next_send_at=next_send,
    )

    await callback.answer("▶️ Шаблон возобновлён")

    # Обновляем вид
    template = await get_broadcast_template(session, template_id)
    if template:
        await broadcast_view_template.__wrapped__(callback, session)


@router.callback_query(F.data.startswith("broadcast_delete_"))
async def broadcast_delete_template(callback: CallbackQuery, session: AsyncSession):
    """Удалить шаблон - подтверждение"""
    template_id = int(callback.data.replace("broadcast_delete_", ""))

    template = await get_broadcast_template(session, template_id)
    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    text = (
        f"🗑 <b>Удалить шаблон?</b>\n\n"
        f"Название: <b>{template.name}</b>\n\n"
        f"Это действие нельзя отменить!"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"broadcast_delete_confirm_{template_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"broadcast_view_{template_id}",
                ),
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast_delete_confirm_"))
async def broadcast_delete_confirm(callback: CallbackQuery, session: AsyncSession):
    """Подтверждение удаления"""
    template_id = int(callback.data.replace("broadcast_delete_confirm_", ""))

    success = await delete_template(session, template_id)

    if success:
        await callback.answer("🗑 Шаблон удалён")
        back_btn = InlineKeyboardButton(
            text="« Назад", callback_data="broadcast_templates_0"
        )
        await callback.message.edit_text(
            "🗑 Шаблон успешно удалён",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn]]),
        )
    else:
        await callback.answer("❌ Ошибка удаления", show_alert=True)


@router.callback_query(F.data.startswith("broadcast_edit_"))
async def broadcast_edit_template(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """Редактирование шаблона"""
    template_id = int(callback.data.replace("broadcast_edit_", ""))

    template = await get_broadcast_template(session, template_id)
    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    await state.set_state(EditBroadcastStates.waiting_for_new_post)
    await state.update_data(edit_template_id=template_id)

    text = (
        f"✏️ <b>Редактирование: {template.name}</b>\n\n"
        "Отправьте новый пост для замены текущего\n"
        "(или нажмите «Пропустить» чтобы оставить старый)"
    )

    skip_btn = InlineKeyboardButton(
        text="⏭ Пропустить", callback_data="broadcast_edit_skip_post"
    )
    cancel_btn = InlineKeyboardButton(
        text="❌ Отмена", callback_data=f"broadcast_view_{template_id}"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[skip_btn], [cancel_btn]]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(StateFilter(EditBroadcastStates.waiting_for_new_post))
async def broadcast_edit_post_received(
    message: Message, state: FSMContext, session: AsyncSession
):
    """Получен новый пост для редактирования"""
    data = await state.get_data()
    template_id = data.get("edit_template_id")

    # Извлекаем контент (аналогично созданию)
    text = None
    entities_json = None
    media_type = None
    media_file_id = None

    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
        text = message.caption
        entities_json = parse_entities_from_message(message)
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
        text = message.caption
        entities_json = parse_entities_from_message(message)
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
        text = message.caption
        entities_json = parse_entities_from_message(message)
    elif message.animation:
        media_type = "animation"
        media_file_id = message.animation.file_id
        text = message.caption
        entities_json = parse_entities_from_message(message)
    elif message.text:
        text = message.text
        entities_json = parse_entities_from_message(message)
    else:
        await message.answer("❌ Неподдерживаемый тип сообщения")
        return

    # Обновляем шаблон
    await update_template(
        session, template_id,
        text=text,
        entities_json=entities_json,
        media_type=media_type,
        media_file_id=media_file_id,
    )

    await state.clear()
    view_btn = InlineKeyboardButton(
        text="👁 Посмотреть", callback_data=f"broadcast_view_{template_id}"
    )
    list_btn = InlineKeyboardButton(
        text="« К шаблонам", callback_data="broadcast_templates_0"
    )
    await message.answer(
        "✅ Пост обновлён!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[view_btn], [list_btn]]
        ),
    )


@router.callback_query(F.data == "broadcast_edit_skip_post")
async def broadcast_edit_skip_post(callback: CallbackQuery, state: FSMContext):
    """Пропустить редактирование поста"""
    data = await state.get_data()
    template_id = data.get("edit_template_id")

    await state.clear()
    await callback.answer("⏭ Пропущено")

    # Возвращаемся к просмотру шаблона
    view_btn = InlineKeyboardButton(
        text="👁 Посмотреть", callback_data=f"broadcast_view_{template_id}"
    )
    list_btn = InlineKeyboardButton(
        text="« К шаблонам", callback_data="broadcast_templates_0"
    )
    await callback.message.edit_text(
        "✅ Редактирование завершено",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[view_btn], [list_btn]]
        ),
    )


@router.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена создания/редактирования"""
    await state.clear()

    await callback.message.edit_text(
        "❌ Операция отменена",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="admin_broadcast")]
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_stats")
async def broadcast_stats(callback: CallbackQuery, session: AsyncSession):
    """Статистика рассылок"""
    templates = await get_all_templates(session, include_inactive=True, limit=100)

    total_templates = len(templates)
    active_periodic = sum(1 for t in templates if t.is_periodic and t.is_active)
    total_sent = sum(t.total_sent for t in templates)
    total_delivered = sum(t.total_delivered for t in templates)
    total_failed = sum(t.total_failed for t in templates)

    delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0

    text = (
        "📊 <b>Статистика рассылок</b>\n\n"
        f"📋 Всего шаблонов: <b>{total_templates}</b>\n"
        f"🔄 Активных авто-рассылок: <b>{active_periodic}</b>\n\n"
        f"📤 <b>Отправка:</b>\n"
        f"├ Всего отправлено: <b>{total_sent}</b>\n"
        f"├ Доставлено: <b>{total_delivered}</b>\n"
        f"├ Ошибок: <b>{total_failed}</b>\n"
        f"└ Доставляемость: <b>{delivery_rate:.1f}%</b>\n"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Назад", callback_data="admin_broadcast")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ===========================
# Auto-Repost & Channel Repost
# ===========================


@router.callback_query(F.data == "broadcast_toggle_auto_repost")
async def toggle_auto_repost(callback: CallbackQuery, session: AsyncSession):
    """Toggle auto-repost from channel"""
    current = await get_auto_repost_enabled()
    new_value = not current
    await set_auto_repost_enabled(new_value)

    new_status = "ON" if new_value else "OFF"
    await callback.answer(f"Auto-repost: {new_status}")

    # Получаем статистику
    templates = await get_all_templates(session, include_inactive=True)
    active_periodic = sum(1 for t in templates if t.is_periodic and t.is_active)
    total_sent = sum(t.total_sent for t in templates)

    # Статус авто-репоста (используем новое значение напрямую)
    auto_repost_status = "ON" if new_value else "OFF"

    text = (
        "📢 <b>Система рассылки</b>\n\n"
        f"📋 Шаблонов: <b>{len(templates)}</b>\n"
        f"🔄 Активных авто-рассылок: <b>{active_periodic}</b>\n"
        f"📤 Всего отправлено: <b>{total_sent}</b>\n"
        f"📡 Авто-репост из канала: <b>{auto_repost_status}</b>\n\n"
        "Выберите действие:"
    )

    # Создаём меню с актуальным статусом
    auto_repost_text = f"Auto-repost: {auto_repost_status}"
    menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Создать рассылку",
                    callback_data="broadcast_create",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Репост из канала",
                    callback_data="broadcast_repost",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Мои шаблоны",
                    callback_data="broadcast_templates_0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="broadcast_stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"📡 {auto_repost_text}",
                    callback_data="broadcast_toggle_auto_repost",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад в админку",
                    callback_data="admin_refresh",
                ),
            ],
        ]
    )

    await callback.message.edit_text(text, reply_markup=menu)


@router.callback_query(F.data == "broadcast_repost")
async def broadcast_repost_start(callback: CallbackQuery, state: FSMContext):
    """Start repost from channel by link"""
    text = (
        "📢 <b>Репост из канала</b>\n\n"
        "Отправьте ссылку на пост, который хотите переслать всем пользователям.\n\n"
        "<b>Поддерживаемые форматы:</b>\n"
        "• <code>https://t.me/channel_name/123</code>\n"
        "• <code>https://t.me/c/1234567890/123</code>\n\n"
        "Сообщение будет переслано с указанием источника (Forwarded from...)"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Назад", callback_data="admin_broadcast")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(BroadcastStates.waiting_for_repost_link)
    await callback.answer()


def parse_telegram_post_link(link: str) -> tuple[str | int, int] | None:
    """
    Parse Telegram post link

    Supported formats:
    - https://t.me/channel_name/123
    - https://t.me/c/1234567890/123 (private channels)
    - t.me/channel_name/123

    Returns:
        tuple(chat_id, message_id) or None if parsing failed
    """
    link = link.strip()

    # Private channel pattern: t.me/c/CHANNEL_ID/MESSAGE_ID
    private_pattern = r'(?:https?://)?t\.me/c/(\d+)/(\d+)'
    match = re.match(private_pattern, link)
    if match:
        channel_id = int(match.group(1))
        message_id = int(match.group(2))
        return (int(f"-100{channel_id}"), message_id)

    # Public channel pattern: t.me/CHANNEL_NAME/MESSAGE_ID
    public_pattern = r'(?:https?://)?t\.me/([a-zA-Z][a-zA-Z0-9_]{3,})/(\d+)'
    match = re.match(public_pattern, link)
    if match:
        channel_name = match.group(1)
        message_id = int(match.group(2))
        return (f"@{channel_name}", message_id)

    return None


def get_repost_target_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting repost target audience"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Всем пользователям",
                    callback_data="repost_target_all"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Premium",
                    callback_data="repost_target_premium"
                ),
                InlineKeyboardButton(
                    text="🆓 Бесплатные",
                    callback_data="repost_target_free"
                ),
            ],
            [
                InlineKeyboardButton(text="« Назад", callback_data="admin_broadcast")
            ],
        ]
    )


@router.message(StateFilter(BroadcastStates.waiting_for_repost_link))
async def process_repost_link(
    message: Message, state: FSMContext, session: AsyncSession
):
    """Process repost link input"""
    link = message.text.strip()

    # Parse link
    parsed = parse_telegram_post_link(link)

    if not parsed:
        await message.answer(
            "❌ Не удалось распознать ссылку.\n\n"
            "Убедитесь, что ссылка имеет формат:\n"
            "• <code>https://t.me/channel_name/123</code>\n"
            "• <code>https://t.me/c/1234567890/123</code>",
            parse_mode="HTML"
        )
        return

    chat_id, message_id = parsed

    # Save repost data
    await state.update_data(
        repost_chat_id=chat_id,
        repost_message_id=message_id,
        repost_link=link
    )

    # Count users
    stmt = select(User).where(
        User.telegram_id.isnot(None),
        User.is_banned.is_(False),
    )
    result = await session.execute(stmt)
    total_users = len(result.scalars().all())

    text = (
        f"📢 <b>Репост поста</b>\n\n"
        f"🔗 Ссылка: {link}\n\n"
        f"<b>Выберите аудиторию:</b>\n"
        f"• Всего пользователей: {total_users:,}"
    )

    await message.answer(text, reply_markup=get_repost_target_keyboard())
    await state.set_state(None)  # Clear state, waiting for callback


@router.callback_query(F.data.startswith("repost_target_"))
async def select_repost_target(
    callback: CallbackQuery, bot: Bot, state: FSMContext, session: AsyncSession
):
    """Select target audience and start repost"""
    target = callback.data.replace("repost_target_", "")

    data = await state.get_data()
    chat_id = data.get("repost_chat_id")
    message_id = data.get("repost_message_id")
    link = data.get("repost_link")

    if not chat_id or not message_id:
        await callback.answer("❌ Данные репоста потеряны", show_alert=True)
        return

    await callback.answer("🚀 Запускаю репост...")

    await callback.message.edit_text(
        "🚀 <b>Репост запущен...</b>\n\n"
        f"🔗 Пост: {link}\n"
        "Это может занять некоторое время.\n"
        "Отчет будет отправлен по завершении."
    )

    # Run repost in background (don't pass session - it will be closed)
    asyncio.create_task(
        execute_repost(bot, callback.from_user.id, chat_id, message_id, target)
    )

    await state.clear()


async def execute_repost(
    bot: Bot,
    admin_id: int,
    from_chat_id: str | int,
    message_id: int,
    target: str
):
    """Execute repost to users"""
    try:
        # Get users based on target (create fresh session)
        from src.database.models import Subscription, SubscriptionTier

        base_query = select(User).where(
            User.telegram_id.isnot(None),
            User.is_banned.is_(False),
        )

        if target == "all":
            stmt = base_query
        elif target == "premium":
            stmt = base_query.join(Subscription).where(
                Subscription.is_active.is_(True),
                Subscription.tier != SubscriptionTier.FREE.value,
            )
        elif target == "free":
            from sqlalchemy import or_
            stmt = base_query.outerjoin(Subscription).where(
                or_(
                    Subscription.id.is_(None),
                    Subscription.tier == SubscriptionTier.FREE.value,
                    Subscription.is_active.is_(False),
                )
            )
        else:
            stmt = base_query

        # Create fresh session for background task
        async with get_session_maker()() as session:
            result = await session.execute(stmt)
            users = result.scalars().all()

        if not users:
            await bot.send_message(admin_id, "❌ Не найдено пользователей для репоста")
            return

        # Notify about start
        await bot.send_message(
            admin_id,
            f"📢 Начинаю репост для {len(users):,} пользователей..."
        )

        sent = 0
        blocked = 0
        failed = 0

        for i, user in enumerate(users, 1):
            try:
                await asyncio.sleep(0.05)  # Rate limit delay

                # Forward with source attribution
                await bot.forward_message(
                    chat_id=user.telegram_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id
                )
                sent += 1

                # Progress report every 100 users
                if i % 100 == 0:
                    await bot.send_message(
                        admin_id,
                        f"📊 Прогресс: {i}/{len(users)} ({(i / len(users) * 100):.1f}%)"
                    )

            except Exception as e:
                error_str = str(e).lower()
                if "blocked" in error_str or "chat not found" in error_str:
                    blocked += 1
                else:
                    failed += 1

        # Final report
        total = sent + blocked + failed
        success_rate = (sent / total * 100) if total > 0 else 0

        report = (
            f"📊 <b>Репост завершен!</b>\n\n"
            f"✅ Доставлено: {sent:,}\n"
            f"🚫 Заблокированы: {blocked:,}\n"
            f"❌ Ошибки: {failed:,}\n"
            f"📋 Всего: {total:,}\n"
            f"📈 Успешность: {success_rate:.1f}%"
        )

        await bot.send_message(admin_id, report, parse_mode="HTML")

    except Exception as e:
        logger.exception(f"Repost error: {e}")
        await bot.send_message(admin_id, f"❌ Ошибка репоста: {e}")
