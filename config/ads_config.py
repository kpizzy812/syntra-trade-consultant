# coding: utf-8
"""
Native Advertising Configuration for AI Trading Platform (syntratrade.xyz)

This module configures native, non-intrusive advertising for the second product
in the ecosystem - an automated AI trading platform.

The ads are designed to:
1. Feel natural and in Syntra's character (cynical, professional)
2. Be contextually relevant (triggered by trading discussions)
3. Not be annoying (frequency limits, smart targeting)
"""
from typing import Dict
import random


# ============================================================================
# ОСНОВНЫЕ НАСТРОЙКИ РЕКЛАМЫ
# ============================================================================

# URL платформы AI Trading
AI_TRADING_URL = "https://syntratrade.xyz"
AI_TRADING_REFERRAL_URL = "https://syntratrade.xyz?ref=syntra_consultant"

# Частотные ограничения
ADS_CONFIG = {
    # Нативная реклама в чате (добавляется к ответу AI)
    "in_chat": {
        "enabled": True,
        "probability": 0.20,  # 20% шанс при релевантном контексте
        "min_messages_between": 8,  # Минимум 8 сообщений между рекламами
        "max_per_day": 2,  # Максимум 2 раза в день (не спамим)
        "only_for_free_tier": False,
        "exclude_premium_plus": True,  # Не показывать VIP

        # === УМНАЯ СТРАТЕГИЯ: сначала ценность, потом реклама ===
        "min_messages_before_first_ad": 7,  # Первые 7 сообщений — БЕЗ рекламы
        "guaranteed_show_after": 20,  # После 20 сообщений — показать если ещё не видел
        "exclude_first_hours": 24,  # Первые 24 часа — вообще без рекламы
    },

    # Push-сообщения в Telegram боте
    "bot_push": {
        "enabled": True,
        "min_interval_hours": 72,  # Не чаще раза в 3 дня
        "max_per_week": 2,  # Максимум 2 раза в неделю
        "only_active_users": True,  # Только активным пользователям (были за 7 дней)
        "exclude_new_users_days": 3,  # Не показывать новым пользователям первые 3 дня
    },

    # Баннер в Mini App / WebApp
    "webapp_banner": {
        "enabled": True,
        "show_probability": 0.3,  # 30% шанс показать баннер
        "dismiss_cooldown_hours": 24,  # После закрытия не показывать 24ч
        "max_impressions_per_day": 3,
    },
}


# ============================================================================
# УМНЫЕ ТРИГГЕРЫ ДЛЯ НАТИВНОЙ РЕКЛАМЫ В ЧАТЕ
# ============================================================================

# Семантические паттерны (целые фразы, не отдельные слова)
# Формат: (паттерн, тип_рекламы, вес)
AD_SEMANTIC_PATTERNS = {
    # ===== ВЫСОКАЯ РЕЛЕВАНТНОСТЬ (показываем с высокой вероятностью) =====

    # Тип: emotions — пользователь говорит про эмоции в трейдинге
    "emotions": [
        ("эмоции мешают", 3),
        ("эмоции в трейдинге", 3),
        ("торгую на эмоциях", 3),
        ("не могу контролировать", 2),
        ("fomo", 3),
        ("страх упустить", 3),
        ("fear of missing", 3),
        ("паникую", 2),
        ("panic sell", 3),
        ("panic buy", 3),
        ("жадность", 2),
        ("greed", 2),
        ("нервничаю", 2),
        ("стресс от торговли", 3),
        ("trading stress", 3),
        ("emotions in trading", 3),
    ],

    # Тип: time — пользователю не хватает времени
    "time": [
        ("нет времени следить", 3),
        ("не успеваю следить", 3),
        ("некогда анализировать", 3),
        ("мало времени на", 2),
        ("занят работой", 2),
        ("no time to watch", 3),
        ("don't have time", 3),
        ("too busy to trade", 3),
        ("can't monitor", 2),
        ("24/7", 2),
        ("круглосуточно следить", 3),
    ],

    # Тип: automation — явный интерес к автоматизации
    "automation": [
        ("автоматическая торговля", 3),
        ("автоматизировать торговлю", 3),
        ("торговый бот", 3),
        ("trading bot", 3),
        ("algo trading", 3),
        ("алготрейдинг", 3),
        ("автоматический трейдинг", 3),
        ("automated trading", 3),
        ("роботизированная торговля", 3),
        ("пассивный доход", 2),
        ("passive income", 2),
        ("торговать без меня", 3),
        ("trade without me", 3),
        ("hands-off trading", 3),
    ],

    # Тип: frustration — разочарование в ручной торговле
    "frustration": [
        ("устал от торговли", 3),
        ("надоело торговать", 3),
        ("tired of trading", 3),
        ("не получается торговать", 2),
        ("постоянно теряю", 2),  # осторожно! не после реальных потерь
        ("сложно торговать", 2),
        ("трудно следить за рынком", 2),
        ("hard to trade", 2),
        ("difficult to analyze", 2),
    ],

    # ===== СРЕДНЯЯ РЕЛЕВАНТНОСТЬ (показываем иногда) =====

    # Тип: analysis — просит анализ (показываем редко, после хорошего ответа)
    "analysis": [
        ("сделай анализ", 1),
        ("проанализируй", 1),
        ("технический анализ", 1),
        ("technical analysis", 1),
        ("что думаешь о", 1),
        ("стоит ли покупать", 1),
        ("should i buy", 1),
        ("какой прогноз", 1),
    ],
}

# ===== NEGATIVE TRIGGERS — когда НЕ показывать рекламу =====
AD_NEGATIVE_PATTERNS = [
    # Пользователь расстроен потерями (не время для рекламы!)
    "потерял",
    "потеряла",
    "слил депозит",
    "lost money",
    "lost everything",
    "ликвидация",
    "liquidated",
    "margin call",
    "маржин колл",
    "убыток",
    "loss",

    # Срочные/критичные вопросы
    "срочно",
    "urgent",
    "быстрее",
    "помоги срочно",
    "что делать",
    "что мне делать",
    "what should i do",

    # Жалобы на бота/сервис
    "бот не работает",
    "ошибка",
    "error",
    "bug",
    "не понимаю",
    "объясни",

    # Негативные эмоции (не про трейдинг)
    "плохо себя чувствую",
    "депрессия",
    "depression",
]

# ===== УСЛОВИЯ КАЧЕСТВА ОТВЕТА =====
AD_RESPONSE_REQUIREMENTS = {
    "min_response_length": 300,  # Минимум символов в ответе AI
    "min_user_message_length": 10,  # Минимум символов в вопросе
    "required_response_indicators": [
        # Признаки хорошего развёрнутого ответа
        "анализ",
        "analysis",
        "рекомендую",
        "рекомендация",
        "recommend",
        "вывод",
        "conclusion",
        "итог",
        "summary",
        "📊",
        "📈",
        "💡",
    ],
}


# ============================================================================
# ТИПИЗИРОВАННЫЕ РЕКЛАМНЫЕ СООБЩЕНИЯ В СТИЛЕ SYNTRA (RU)
# ============================================================================

# Рекламные окончания сгруппированы по контексту
# Система выберет релевантное сообщение под ситуацию
NATIVE_AD_ENDINGS_BY_TYPE_RU = {
    # Когда пользователь говорит про эмоции в трейдинге
    "emotions": [
        "\n\n---\n<i>💡 К слову, если устал бороться с эмоциями — на "
        "<a href=\"{url}\">syntratrade.xyz</a> торгует алгоритм. "
        "Он не знает что такое FOMO.</i>",

        "\n\n---\n<i>🎯 Алгоритмы не паникуют и не жадничают. "
        "На <a href=\"{url}\">syntratrade.xyz</a> именно так работает торговля.</i>",
    ],

    # Когда пользователю не хватает времени
    "time": [
        "\n\n---\n<i>⏰ Нет времени следить за рынком 24/7? "
        "На <a href=\"{url}\">syntratrade.xyz</a> AI делает это за тебя.</i>",

        "\n\n---\n<i>🌙 Пока ты спишь, алгоритм работает. "
        "<a href=\"{url}\">syntratrade.xyz</a> — торговля без твоего участия.</i>",
    ],

    # Когда пользователь интересуется автоматизацией
    "automation": [
        "\n\n---\n<i>🤖 Раз интересует автоматизация — загляни на "
        "<a href=\"{url}\">syntratrade.xyz</a>. Тот же AI мозг, только торгует сам.</i>",

        "\n\n---\n<i>⚡ Автоматическая торговля уже работает на "
        "<a href=\"{url}\">syntratrade.xyz</a>. Настроил стратегию — и забыл.</i>",
    ],

    # Когда пользователь разочарован ручной торговлей
    "frustration": [
        "\n\n---\n<i>📊 Понимаю. Ручная торговля — это сложно. "
        "На <a href=\"{url}\">syntratrade.xyz</a> всё делает алгоритм.</i>",

        "\n\n---\n<i>💡 Если надоело — можно попробовать "
        "<a href=\"{url}\">syntratrade.xyz</a>. Там AI торгует вместо тебя.</i>",
    ],

    # После хорошего анализа (общий/нейтральный)
    "analysis": [
        "\n\n---\n<i>🤖 Кстати, этот же анализ можно автоматизировать. "
        "<a href=\"{url}\">syntratrade.xyz</a> — AI торговля 24/7.</i>",
    ],

    # Дефолтный (если не определили тип)
    "default": [
        "\n\n---\n<i>💡 Если интересна автоматическая торговля — "
        "<a href=\"{url}\">syntratrade.xyz</a>.</i>",
    ],
}

# Для обратной совместимости
NATIVE_AD_ENDINGS_RU = NATIVE_AD_ENDINGS_BY_TYPE_RU["default"]


# Полноценные рекламные сообщения для push в боте
BOT_AD_MESSAGES_RU = [
    {
        "title": "Syntra AI Trading",
        "text": """🤖 <b>Syntra AI Trading</b>

Привет, это снова я.

Знаешь, что отличает успешных трейдеров от остальных? Они убирают эмоции из уравнения.

Я создал платформу автоматической торговли, где AI делает всю работу:
• 24/7 мониторинг рынка
• Автоматические сделки по стратегии
• Никакого FOMO и паники

Пока ты спишь — твой портфель работает.

<i>Это не финансовый совет, но это точно умнее, чем торговать на эмоциях.</i>""",
        "button_text": "🚀 Попробовать AI Trading",
        "url": AI_TRADING_REFERRAL_URL,
    },
    {
        "title": "Пассивный дох��д с AI",
        "text": """💰 <b>Устал от ручного трейдинга?</b>

Syntra здесь.

Я анализирую рынок для тебя каждый день. Но что если бы я не просто анализировал, а ещё и торговал?

На <b>syntratrade.xyz</b> — именно так и работает:
• AI сам принимает решения
• Ты настраиваешь риски
• Прибыль капает автоматически

Алгоритмы не знают страха и жадности. В этом их сила.

<i>Данные не врут. Эмоции — постоянно.</i>""",
        "button_text": "📈 Узнать больше",
        "url": AI_TRADING_REFERRAL_URL,
    },
    {
        "title": "AI vs Human Trading",
        "text": """📊 <b>Факт дня от Syntra</b>

Знаешь, почему 95% трейдеров теряют деньги?

Эмоции.
FOMO.
Паника.
Жадность.

Алгоритмы лишены этих слабостей. Они торгуют по данным, не по чувствам.

На <b>syntratrade.xyz</b> я торгую автоматически — без эмоций, 24/7, по проверенным стратегиям.

Выбор за тобой: торговать своими руками или доверить это AI.

<i>Рынок не ждёт, пока ты перестанешь нервничать.</i>""",
        "button_text": "🤖 AI Trading Platform",
        "url": AI_TRADING_REFERRAL_URL,
    },
]


# ============================================================================
# РЕКЛАМНЫЕ СООБЩЕНИЯ (EN)
# ============================================================================

# Типизированные сообщения (EN)
NATIVE_AD_ENDINGS_BY_TYPE_EN = {
    "emotions": [
        "\n\n---\n<i>💡 Tired of fighting emotions? "
        "<a href=\"{url}\">syntratrade.xyz</a> trades without FOMO or panic.</i>",

        "\n\n---\n<i>🎯 Algorithms don't panic or get greedy. "
        "That's how <a href=\"{url}\">syntratrade.xyz</a> works.</i>",
    ],
    "time": [
        "\n\n---\n<i>⏰ No time to watch the market 24/7? "
        "<a href=\"{url}\">syntratrade.xyz</a> — AI does it for you.</i>",

        "\n\n---\n<i>🌙 While you sleep, the algorithm works. "
        "<a href=\"{url}\">syntratrade.xyz</a> — hands-off trading.</i>",
    ],
    "automation": [
        "\n\n---\n<i>🤖 Since you're interested in automation — check "
        "<a href=\"{url}\">syntratrade.xyz</a>. Same AI brain, trades itself.</i>",

        "\n\n---\n<i>⚡ Automated trading is live at "
        "<a href=\"{url}\">syntratrade.xyz</a>. Set your strategy and forget it.</i>",
    ],
    "frustration": [
        "\n\n---\n<i>📊 I get it. Manual trading is hard. "
        "<a href=\"{url}\">syntratrade.xyz</a> — let the algorithm handle it.</i>",

        "\n\n---\n<i>💡 Had enough? Try "
        "<a href=\"{url}\">syntratrade.xyz</a>. AI trades for you.</i>",
    ],
    "analysis": [
        "\n\n---\n<i>🤖 This analysis can be automated. "
        "<a href=\"{url}\">syntratrade.xyz</a> — AI trading 24/7.</i>",
    ],
    "default": [
        "\n\n---\n<i>💡 Interested in automated trading? "
        "<a href=\"{url}\">syntratrade.xyz</a>.</i>",
    ],
}

NATIVE_AD_ENDINGS_EN = NATIVE_AD_ENDINGS_BY_TYPE_EN["default"]


BOT_AD_MESSAGES_EN = [
    {
        "title": "Syntra AI Trading",
        "text": """🤖 <b>Syntra AI Trading</b>

Hey, it's me again.

You know what separates successful traders from the rest? They remove emotions from the equation.

I've built an automated trading platform where AI does all the work:
• 24/7 market monitoring
• Automatic trades following strategy
• No FOMO, no panic

While you sleep — your portfolio works.

<i>Not financial advice, but definitely smarter than emotional trading.</i>""",
        "button_text": "🚀 Try AI Trading",
        "url": AI_TRADING_REFERRAL_URL,
    },
    {
        "title": "Passive Income with AI",
        "text": """💰 <b>Tired of manual trading?</b>

Syntra here.

I analyze the market for you every day. But what if I didn't just analyze, but also traded?

On <b>syntratrade.xyz</b> — that's exactly how it works:
• AI makes decisions
• You set the risks
• Profits flow automatically

Algorithms don't know fear or greed. That's their power.

<i>Data doesn't lie. Emotions do — constantly.</i>""",
        "button_text": "📈 Learn More",
        "url": AI_TRADING_REFERRAL_URL,
    },
]


# ============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С РЕКЛАМОЙ
# ============================================================================

def get_native_ad_ending(
    language: str = "ru",
    ad_type: str = "default",
) -> str:
    """
    Get contextually relevant ad ending for AI response

    Args:
        language: User's language ('ru' or 'en')
        ad_type: Type of ad context ('emotions', 'time', 'automation', etc.)

    Returns:
        Formatted ad ending with URL
    """
    if language == "ru":
        type_endings = NATIVE_AD_ENDINGS_BY_TYPE_RU
    else:
        type_endings = NATIVE_AD_ENDINGS_BY_TYPE_EN

    # Get endings for specific type, fallback to default
    endings = type_endings.get(ad_type, type_endings["default"])
    ending = random.choice(endings)
    return ending.format(url=AI_TRADING_REFERRAL_URL)


def get_bot_ad_message(language: str = "ru") -> Dict:
    """
    Get random ad message for bot push notification

    Args:
        language: User's language ('ru' or 'en')

    Returns:
        Dict with title, text, button_text, url
    """
    messages = BOT_AD_MESSAGES_RU if language == "ru" else BOT_AD_MESSAGES_EN
    return random.choice(messages)


def analyze_ad_context(
    user_message: str,
    ai_response: str = "",
) -> tuple[bool, str, float]:
    """
    Умный анализ контекста для показа рекламы

    Анализирует:
    1. Семантические паттерны в сообщении пользователя
    2. Негативные триггеры (когда НЕ показывать)
    3. Качество ответа AI

    Args:
        user_message: Сообщение пользователя
        ai_response: Ответ AI (опционально)

    Returns:
        Tuple: (should_show, ad_type, confidence_score)
        - should_show: показывать ли рекламу
        - ad_type: тип рекламы ('emotions', 'time', 'automation', etc.)
        - confidence_score: уверенность (0.0 - 1.0)
    """
    message_lower = user_message.lower()
    response_lower = ai_response.lower() if ai_response else ""

    # ===== 1. Проверка негативных триггеров (сразу отказ) =====
    for pattern in AD_NEGATIVE_PATTERNS:
        if pattern in message_lower:
            return False, "blocked", 0.0

    # ===== 2. Проверка качества ответа AI =====
    reqs = AD_RESPONSE_REQUIREMENTS
    if ai_response:
        # Слишком короткий ответ — не показываем
        if len(ai_response) < reqs["min_response_length"]:
            return False, "short_response", 0.0

        # Проверяем наличие индикаторов хорошего ответа
        has_quality_indicator = any(
            ind in response_lower for ind in reqs["required_response_indicators"]
        )
        if not has_quality_indicator:
            # Нет индикаторов качества — снижаем вероятность
            pass  # продолжаем, но с меньшей уверенностью

    # Слишком короткий вопрос
    if len(user_message) < reqs["min_user_message_length"]:
        return False, "short_question", 0.0

    # ===== 3. Поиск семантических паттернов =====
    best_type = "default"
    best_score = 0.0

    for ad_type, patterns in AD_SEMANTIC_PATTERNS.items():
        type_score = 0
        for pattern, weight in patterns:
            if pattern in message_lower:
                type_score += weight

        if type_score > best_score:
            best_score = type_score
            best_type = ad_type

    # ===== 4. Расчёт уверенности =====
    # score 3+ = высокая уверенность
    # score 2 = средняя
    # score 1 = низкая
    # score 0 = не показываем
    if best_score >= 3:
        confidence = 0.8
    elif best_score >= 2:
        confidence = 0.5
    elif best_score >= 1:
        confidence = 0.25
    else:
        return False, "no_match", 0.0

    return True, best_type, confidence


def should_show_ad_in_chat(
    user_message: str,
    messages_since_last_ad: int,
    ads_today: int,
    user_tier: str = "free",
    ai_response: str = "",
    total_user_messages: int = 0,
    user_hours_since_registration: float = 999,
    user_has_seen_ad: bool = False,
) -> tuple[bool, str]:
    """
    Умное определение показа рекламы в чате

    СТРАТЕГИЯ:
    1. Первые 24 часа — вообще без рекламы (не отпугиваем новичков)
    2. Первые 7 сообщений — без рекламы (сначала ценность)
    3. После 20 сообщений — гарантированный показ если ещё не видел
    4. Иначе — показ по контексту и вероятности

    Args:
        user_message: Сообщение пользователя
        messages_since_last_ad: Сообщений с последней рекламы
        ads_today: Реклам сегодня
        user_tier: Тариф пользователя
        ai_response: Ответ AI (для анализа качества)
        total_user_messages: Всего сообщений от пользователя за всё время
        user_hours_since_registration: Часов с момента регистрации
        user_has_seen_ad: Видел ли пользователь хоть одну рекламу

    Returns:
        Tuple: (should_show, ad_type)
    """
    config = ADS_CONFIG["in_chat"]

    if not config["enabled"]:
        return False, "disabled"

    # Don't show to VIP users
    if config["exclude_premium_plus"] and user_tier == "vip":
        return False, "vip_user"

    # ===== УМНАЯ СТРАТЕГИЯ: сначала ценность, потом реклама =====

    # 1. Первые N часов — вообще без рекламы (не отпугиваем новичков)
    exclude_hours = config.get("exclude_first_hours", 24)
    if user_hours_since_registration < exclude_hours:
        return False, "new_user_cooldown"

    # 2. Первые N сообщений — без рекламы (сначала ценность)
    min_messages = config.get("min_messages_before_first_ad", 7)
    if total_user_messages < min_messages:
        return False, "building_trust"

    # 3. Дневной лимит
    if ads_today >= config["max_per_day"]:
        return False, "daily_limit"

    # 4. После N сообщений — гарантированный показ если ещё не видел
    guaranteed_after = config.get("guaranteed_show_after", 20)
    if total_user_messages >= guaranteed_after and not user_has_seen_ad:
        # Гарантированный показ, но всё равно проверяем негативные триггеры
        for pattern in AD_NEGATIVE_PATTERNS:
            if pattern in user_message.lower():
                return False, "negative_context"

        # Выбираем тип рекламы по контексту, или default
        _, ad_type, _ = analyze_ad_context(user_message, ai_response)
        if ad_type in ["blocked", "short_response", "short_question", "no_match"]:
            ad_type = "default"

        return True, ad_type

    # ===== ОБЫЧНАЯ ЛОГИКА для остальных случаев =====

    # Check frequency limits
    if messages_since_last_ad < config["min_messages_between"]:
        return False, "too_frequent"

    # Умный анализ контекста
    should_show, ad_type, confidence = analyze_ad_context(
        user_message=user_message,
        ai_response=ai_response,
    )

    if not should_show:
        return False, ad_type

    # Финальный рандом с учётом уверенности
    # Base probability * confidence
    final_probability = config["probability"] * (1 + confidence)
    final_probability = min(final_probability, 0.35)  # Max 35%

    if random.random() < final_probability:
        return True, ad_type
    else:
        return False, "random_skip"


def check_ad_trigger_relevance(user_message: str) -> str:
    """
    Quick check for ad relevance (legacy compatibility)

    Args:
        user_message: User's message

    Returns:
        'high', 'medium', 'low', or 'none'
    """
    should_show, ad_type, confidence = analyze_ad_context(user_message)

    if confidence >= 0.7:
        return "high"
    elif confidence >= 0.4:
        return "medium"
    elif confidence > 0:
        return "low"
    else:
        return "none"


# ============================================================================
# WEBAPP / MINI APP BANNER CONFIG
# ============================================================================

WEBAPP_BANNER_CONFIG = {
    "ru": {
        "title": "Syntra AI Trading",
        "subtitle": "Автоматическая торговля без эмоций",
        "cta": "Попробовать",
        "url": AI_TRADING_REFERRAL_URL,
    },
    "en": {
        "title": "Syntra AI Trading",
        "subtitle": "Automated trading without emotions",
        "cta": "Try Now",
        "url": AI_TRADING_REFERRAL_URL,
    },
}


def get_webapp_banner(language: str = "ru") -> Dict:
    """
    Get banner config for WebApp/Mini App

    Args:
        language: User's language

    Returns:
        Dict with banner config
    """
    return WEBAPP_BANNER_CONFIG.get(language, WEBAPP_BANNER_CONFIG["en"])
