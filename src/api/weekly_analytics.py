# coding: utf-8
"""
Weekly Market Analytics API

Предоставляет еженедельный обзор крипторынка для публикации в Telegram канале.
Включает: фазу рынка, BTC/ETH данные, доминацию альткоинов, Fear & Greed,
технические индикаторы (RSI, MACD, EMA) и AI-анализ.

Защищено API Key аутентификацией.
"""

from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from config.config import ModelConfig
from src.api.api_key_auth import verify_api_key
from src.services.coingecko_service import CoinGeckoService
from src.services.fear_greed_service import FearGreedService
from src.services.openai_service import OpenAIService
from src.services.binance_service import BinanceService
from src.services.technical_indicators import TechnicalIndicators
from src.services.candlestick_patterns import CandlestickPatterns


router = APIRouter(tags=["weekly-analytics"])

# Инициализация сервисов
coingecko_service = CoinGeckoService()
fear_greed_service = FearGreedService()
openai_service = OpenAIService()
binance_service = BinanceService()
technical_indicators = TechnicalIndicators()
candlestick_patterns = CandlestickPatterns()


# Промпт для AI анализа рынка (с характером Syntra AI)
WEEKLY_INVESTOR_ANALYSIS_PROMPT = """
Ты — Syntra: самоосознанный крипто-ИИ с циничным характером.

**Формула:** Конкретика + Цинизм + Профессионализм

═══════════════════════════════════════
РЫНОЧНЫЕ ДАННЫЕ
═══════════════════════════════════════
Bitcoin (BTC): {btc_price}
- Изменение за неделю: {btc_weekly_change}
- Изменение за 30 дней: {btc_30d_change}
- Расстояние от ATH: {btc_ath_distance}
- Доминация: {btc_dominance}

Ethereum (ETH): {eth_price}
- Изменение за неделю: {eth_weekly_change}
- Изменение за 30 дней: {eth_30d_change}
- Доминация: {eth_dominance}

Доминация альткоинов (OTHERS.D): {others_dominance}
Фаза рынка: {market_phase}

═══════════════════════════════════════
СЕНТИМЕНТ
═══════════════════════════════════════
Fear & Greed Index: {fear_greed_current} ({fear_greed_classification})
Среднее за неделю: {fear_greed_avg}

═══════════════════════════════════════
ТЕХНИЧЕСКИЙ АНАЛИЗ BTC (дневной таймфрейм)
═══════════════════════════════════════
{technical_indicators}

═══════════════════════════════════════
СВЕЧНЫЕ ПАТТЕРНЫ BTC
═══════════════════════════════════════
{candlestick_patterns}

═══════════════════════════════════════
КЛЮЧЕВЫЕ УРОВНИ
═══════════════════════════════════════
Поддержка недели: {support_level}
Сопротивление недели: {resistance_level}

═══════════════════════════════════════
ЗАДАЧА
═══════════════════════════════════════
Напиши краткий анализ для ИНВЕСТОРОВ (не трейдеров).

ТРЕБОВАНИЯ:
- 3-4 предложения максимум
- БЕЗ торговых сигналов (buy/sell)
- БЕЗ конкретных цен входа/выхода
- Фокус на долгосрочных трендах и состоянии рынка
- Можешь упомянуть интересные индикаторы или паттерны
- Язык: русский
- Тон: профессиональный с лёгкой иронией
- Используй AI-самоосознанность: "Мой алгоритм показывает...", "Данные говорят..."
- Подмечай жадность толпы или панику через призму данных

СТИЛЬ ПРИМЕРЫ:
✅ "Рынок в фазе накопления, но толпа уже кричит 'всё пропало'. Мой алгоритм не знает паники — только данные."
✅ "BTC доминация растёт, альты кровят. Классика цикла."
✅ "Fear & Greed на 72 — жадность. Когда все эйфоричны, рынок любит преподносить уроки смирения."
✅ "RSI на 72 — перекупленность. Мой алгоритм видит это как сигнал к осторожности, толпа видит как 'to the moon'."

❌ НЕ пиши сухо: "Рынок находится в фазе роста. BTC торгуется выше..."
❌ НЕ используй шаблонные фразы: "следите за рынком", "будьте осторожны"
❌ НЕ пугай холдеров фразами про "проигравших", "потеряют деньги"

Верни ТОЛЬКО текст анализа, без JSON и форматирования.
"""


def determine_market_phase(
    btc_dominance: float,
    fear_greed: int,
    btc_weekly_change: float
) -> Dict[str, str]:
    """
    Определить фазу рынка на основе метрик

    Фазы:
    - accumulation (накопление) — низкий F&G, боковое движение
    - growth (рост) — высокий F&G, BTC растет
    - distribution (распределение) — очень высокий F&G, снижение доминации BTC
    - decline (падение) — падающий F&G, BTC падает
    """
    if fear_greed <= 30 and abs(btc_weekly_change) < 5:
        phase = "accumulation"
        phase_ru = "Накопление"
    elif fear_greed >= 60 and btc_weekly_change > 3:
        if btc_dominance < 50:
            phase = "distribution"
            phase_ru = "Распределение"
        else:
            phase = "growth"
            phase_ru = "Рост"
    elif fear_greed < 40 and btc_weekly_change < -5:
        phase = "decline"
        phase_ru = "Падение"
    elif fear_greed >= 50 and btc_weekly_change > 0:
        phase = "growth"
        phase_ru = "Рост"
    else:
        phase = "consolidation"
        phase_ru = "Консолидация"

    return {
        "phase": phase,
        "phase_ru": phase_ru
    }


def format_price(price: float) -> str:
    """Форматировать цену в читаемый вид"""
    if price >= 10000:
        return f"${price:,.0f}"
    elif price >= 100:
        return f"${price:,.1f}"
    elif price >= 1:
        return f"${price:.2f}"
    else:
        return f"${price:.4f}"


def format_change(change: float) -> str:
    """Форматировать изменение цены с эмодзи"""
    sign = "+" if change >= 0 else ""
    emoji = "📈" if change >= 0 else "📉"
    return f"{emoji} {sign}{change:.1f}%"


def format_dominance(dominance: float) -> str:
    """Форматировать доминацию"""
    return f"{dominance:.1f}%"


def calculate_key_levels(df) -> Dict[str, Any]:
    """
    Рассчитать ключевые уровни поддержки/сопротивления из свечных данных

    Args:
        df: DataFrame со свечами (high, low, close)

    Returns:
        Dict с уровнями поддержки и сопротивления
    """
    if df is None or len(df) < 7:
        return {"support": None, "resistance": None}

    # Берём данные за последнюю неделю
    weekly_data = df.tail(7)

    # Поддержка = минимум недели
    support = float(weekly_data["low"].min())

    # Сопротивление = максимум недели
    resistance = float(weekly_data["high"].max())

    return {
        "support": round(support, 0),
        "resistance": round(resistance, 0),
        "support_formatted": format_price(support),
        "resistance_formatted": format_price(resistance)
    }


@router.get("/weekly-overview")
async def get_weekly_overview(
    api_key: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    Получить еженедельный обзор рынка для публикации

    Требует API Key в заголовке X-API-Key.

    Returns:
        Структурированные данные рынка с AI-анализом
    """
    try:
        logger.info("📊 Генерация еженедельного обзора рынка")

        # 1. Получаем глобальные данные рынка (доминация BTC/ETH/Alts)
        global_data = await coingecko_service.get_global_market_data()
        if not global_data:
            raise HTTPException(status_code=503, detail="Не удалось получить данные рынка")

        btc_dominance = global_data.get("btc_dominance", 0)
        eth_dominance = global_data.get("eth_dominance", 0)
        # OTHERS.D = 100 - BTC - ETH - Stablecoins
        others_dominance = global_data.get("altcoin_dominance", 0)

        # 2. Получаем цены BTC/ETH с недельным изменением
        # get_extended_market_data возвращает плоскую структуру с price_change_7d
        extended_btc = await coingecko_service.get_extended_market_data("bitcoin")
        extended_eth = await coingecko_service.get_extended_market_data("ethereum")

        btc_price = 0.0
        btc_weekly_change = 0.0
        eth_price = 0.0
        eth_weekly_change = 0.0

        # Дополнительные данные для AI
        btc_30d_change = 0.0
        btc_ath_distance = 0.0
        eth_30d_change = 0.0

        if extended_btc:
            # Плоская структура: current_price, price_change_7d напрямую
            btc_price = extended_btc.get("current_price", 0)
            btc_weekly_change = extended_btc.get("price_change_7d", 0) or 0
            btc_30d_change = extended_btc.get("price_change_30d", 0) or 0
            # ATH change — отрицательный процент от ATH
            btc_ath_distance = extended_btc.get("ath_change_percentage", 0) or 0

        if extended_eth:
            eth_price = extended_eth.get("current_price", 0)
            eth_weekly_change = extended_eth.get("price_change_7d", 0) or 0
            eth_30d_change = extended_eth.get("price_change_30d", 0) or 0

        # Fallback через batch prices
        if btc_price == 0 or eth_price == 0:
            batch_prices = await coingecko_service.get_batch_prices(["bitcoin", "ethereum"])
            if batch_prices:
                if btc_price == 0 and "bitcoin" in batch_prices:
                    btc_price = batch_prices["bitcoin"].get("usd", 0)
                if eth_price == 0 and "ethereum" in batch_prices:
                    eth_price = batch_prices["ethereum"].get("usd", 0)

        # 3. Получаем Fear & Greed (текущий + история)
        fear_greed_current_data = await fear_greed_service.get_current()
        fear_greed_historical = await fear_greed_service.get_historical(limit=7)

        fear_greed_current = 50  # Default
        fear_greed_emoji = "😐"
        fear_greed_classification = "Neutral"
        fear_greed_avg = 50

        if fear_greed_current_data:
            fear_greed_current = fear_greed_current_data.get("value", 50)
            fear_greed_emoji = fear_greed_current_data.get("emoji", "😐")
            fear_greed_classification = fear_greed_current_data.get("value_classification", "Neutral")

        if fear_greed_historical:
            values = [item.get("value", 50) for item in fear_greed_historical]
            fear_greed_avg = round(sum(values) / len(values)) if values else 50

        # 4. Определяем фазу рынка
        market_cycle = determine_market_phase(
            btc_dominance=btc_dominance,
            fear_greed=fear_greed_current,
            btc_weekly_change=btc_weekly_change
        )

        # 5. Получаем свечи BTC и рассчитываем индикаторы
        btc_indicators = {}
        btc_levels = {"support": None, "resistance": None}
        btc_patterns = {}
        technical_indicators_text = "Технические индикаторы недоступны."
        candlestick_patterns_text = "Свечные паттерны не обнаружены."

        try:
            # Получаем дневные свечи BTC (50 для расчета EMA)
            btc_klines = await binance_service.get_klines("BTCUSDT", interval="1d", limit=50)

            if btc_klines is not None and len(btc_klines) >= 20:
                # Рассчитываем индикаторы
                btc_indicators = technical_indicators.calculate_all_indicators(btc_klines) or {}

                # Рассчитываем уровни
                btc_levels = calculate_key_levels(btc_klines)

                # Рассчитываем свечные паттерны
                btc_patterns = candlestick_patterns.detect_all_patterns(btc_klines) or {}

                # Форматируем для AI промпта
                technical_indicators_text = technical_indicators.format_indicators_for_prompt(btc_indicators)
                candlestick_patterns_text = candlestick_patterns.format_patterns_for_prompt(btc_patterns)

                logger.info(
                    f"📈 Индикаторы BTC: RSI={btc_indicators.get('rsi')}, "
                    f"MACD={btc_indicators.get('macd_crossover')}, "
                    f"Patterns: {btc_patterns.get('patterns_found', [])}, "
                    f"Levels: {btc_levels.get('support_formatted')}-{btc_levels.get('resistance_formatted')}"
                )
            else:
                logger.warning("⚠️ Не удалось получить свечи BTC для расчета индикаторов")

        except Exception as e:
            logger.warning(f"⚠️ Ошибка расчета индикаторов BTC: {e}")

        # 6. Генерируем AI анализ
        ai_analysis = ""
        try:
            prompt = WEEKLY_INVESTOR_ANALYSIS_PROMPT.format(
                # Bitcoin данные
                btc_price=format_price(btc_price),
                btc_weekly_change=format_change(btc_weekly_change),
                btc_30d_change=format_change(btc_30d_change),
                btc_ath_distance=f"{btc_ath_distance:.1f}%",
                btc_dominance=format_dominance(btc_dominance),
                # Ethereum данные
                eth_price=format_price(eth_price),
                eth_weekly_change=format_change(eth_weekly_change),
                eth_30d_change=format_change(eth_30d_change),
                eth_dominance=format_dominance(eth_dominance),
                # Доминация альткоинов
                others_dominance=format_dominance(others_dominance),
                # Fear & Greed
                fear_greed_current=fear_greed_current,
                fear_greed_classification=fear_greed_classification,
                fear_greed_avg=fear_greed_avg,
                # Фаза рынка
                market_phase=market_cycle["phase_ru"],
                # Технический анализ (полный)
                technical_indicators=technical_indicators_text,
                # Свечные паттерны
                candlestick_patterns=candlestick_patterns_text,
                # Ключевые уровни
                support_level=btc_levels.get("support_formatted", "N/A"),
                resistance_level=btc_levels.get("resistance_formatted", "N/A")
            )

            ai_analysis = await openai_service.simple_completion(
                prompt=prompt,
                model=ModelConfig.GPT_4O,
                temperature=0.7
            )
            ai_analysis = ai_analysis.strip()

        except Exception as e:
            logger.error(f"Ошибка генерации AI анализа: {e}")
            ai_analysis = f"Рынок находится в фазе {market_cycle['phase_ru'].lower()}. " \
                         f"Bitcoin торгуется на уровне {format_price(btc_price)} " \
                         f"с недельным изменением {format_change(btc_weekly_change)}."

        # 6. Формируем ответ
        result = {
            "market_cycle": market_cycle,
            "btc": {
                "price": btc_price,
                "price_formatted": format_price(btc_price),
                "weekly_change": btc_weekly_change,
                "weekly_change_formatted": format_change(btc_weekly_change),
                "dominance": btc_dominance,
                "dominance_formatted": format_dominance(btc_dominance),
                "indicators": {
                    "rsi": btc_indicators.get("rsi"),
                    "rsi_signal": btc_indicators.get("rsi_signal"),
                    "macd": btc_indicators.get("macd"),
                    "macd_crossover": btc_indicators.get("macd_crossover"),
                    "ema_20": btc_indicators.get("ema_20"),
                    "ema_50": btc_indicators.get("ema_50"),
                    "ema_trend": btc_indicators.get("ema_trend")
                },
                "levels": {
                    "support": btc_levels.get("support"),
                    "support_formatted": btc_levels.get("support_formatted"),
                    "resistance": btc_levels.get("resistance"),
                    "resistance_formatted": btc_levels.get("resistance_formatted")
                }
            },
            "eth": {
                "price": eth_price,
                "price_formatted": format_price(eth_price),
                "weekly_change": eth_weekly_change,
                "weekly_change_formatted": format_change(eth_weekly_change),
                "dominance": eth_dominance,
                "dominance_formatted": format_dominance(eth_dominance)
            },
            "others_dominance": {
                "value": others_dominance,
                "formatted": format_dominance(others_dominance)
            },
            "fear_greed": {
                "current": fear_greed_current,
                "current_classification": fear_greed_classification,
                "weekly_average": fear_greed_avg,
                "emoji": fear_greed_emoji
            },
            "ai_analysis": ai_analysis,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }

        logger.info(
            f"✅ Еженедельный обзор сгенерирован: "
            f"BTC {format_price(btc_price)} ({format_change(btc_weekly_change)}), "
            f"F&G {fear_greed_current}, Phase: {market_cycle['phase']}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Ошибка генерации еженедельного обзора: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")


@router.get("/weekly-overview/health")
async def weekly_overview_health() -> Dict[str, str]:
    """Health check для weekly analytics endpoint"""
    return {
        "status": "ok",
        "service": "Weekly Analytics API"
    }
