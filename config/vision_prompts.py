# coding: utf-8
"""
Vision-specific prompts for chart analysis
"""

# Prompt for quick coin detection from chart
COIN_DETECTION_PROMPT = """
Определи название криптовалюты на этом графике.
Верни ТОЛЬКО название монеты (например: Bitcoin, Ethereum, Solana).
Если это пара типа BTC/USD или BTCUSDT - верни только название монеты (BTC).
Если не можешь определить - верни "Unknown".
"""

# Enhanced analysis prompt with market data
def get_enhanced_analysis_prompt(
    coin_name: str,
    current_price: float,
    change_24h: float,
    volume_24h: float = None,
    market_cap: float = None
) -> str:
    """
    Get prompt for comprehensive analysis with market data

    Args:
        coin_name: Name of the cryptocurrency
        current_price: Current price in USD
        change_24h: 24h price change percentage
        volume_24h: Optional 24h trading volume
        market_cap: Optional market cap

    Returns:
        Formatted prompt string
    """
    prompt = f"""
Проанализируй график {coin_name}, используя визуальный анализ И актуальные рыночные данные:

**АКТУАЛЬНЫЕ ДАННЫЕ из API (прямо сейчас):**
- Текущая цена: ${current_price:,.2f} USD
- Изменение 24ч: {change_24h:+.2f}%
"""

    if volume_24h:
        prompt += f"- Объем 24ч: ${volume_24h:,.0f}\n"
    if market_cap:
        prompt += f"- Капитализация: ${market_cap:,.0f}\n"

    prompt += """
**ВИЗУАЛЬНЫЙ АНАЛИЗ графика (что ты видишь на скриншоте):**
1. **Тренд:** Определи текущий тренд и его силу (восходящий/нисходящий/боковой)
2. **Уровни:** Ключевые уровни поддержки/сопротивления (укажи примерные цены из графика)
3. **Паттерны:** Свечные паттерны и формации (флаги, треугольники, голова-плечи и т.д.)
4. **Индикаторы:** Технические индикаторы, если видны на графике (RSI, MACD, объемы, скользящие средние)
5. **Таймфрейм:** Определи временной фрейм графика (5m, 15m, 1h, 4h, 1d и т.д.)

**КОМПЛЕКСНЫЙ ВЫВОД:**
Объедини визуальный анализ графика с актуальными данными API.
Дай краткий прогноз и укажи ключевые ценовые уровни для:
- Точка входа (если актуально)
- Take Profit уровни
- Stop Loss

**Стиль ответа:**
Отвечай саркастично и кратко, как Syntra - профессиональный, но с иронией AI-аналитик.
Используй эмодзи для наглядности.
Максимум 300 слов.
"""
    return prompt

# Basic analysis prompt without market data
BASIC_ANALYSIS_PROMPT = """
Проанализируй этот график криптовалюты:

1. **Название монеты** (если видно на графике)
2. **Текущий тренд** (восходящий/нисходящий/боковой)
3. **Ключевые уровни поддержки и сопротивления** (примерные цены)
4. **Свечные паттерны** (если видны)
5. **Технические индикаторы** (RSI, MACD, объемы) - если отображены
6. **Таймфрейм** (если виден)
7. **Краткий прогноз**

Отвечай структурированно, используя эмодзи для наглядности.
Саркастичный тон, как у Syntra.
Максимум 250 слов.
"""

# Prompt for user question + chart analysis
def get_question_analysis_prompt(
    user_question: str,
    coin_name: str = None,
    current_price: float = None,
    change_24h: float = None
) -> str:
    """
    Get prompt for answering user question about chart

    Args:
        user_question: User's question
        coin_name: Optional coin name
        current_price: Optional current price
        change_24h: Optional 24h change

    Returns:
        Formatted prompt string
    """
    prompt = f'Пользователь спросил: "{user_question}"\n\n'

    if coin_name and current_price is not None:
        prompt += f"""
Проанализируй график {coin_name} с актуальными данными:

**ДАННЫЕ из API:**
- Цена: ${current_price:,.2f}
"""
        if change_24h is not None:
            prompt += f"- Изменение 24ч: {change_24h:+.2f}%\n"

        prompt += """
**ВИЗУАЛЬНЫЙ АНАЛИЗ:**
1. Тренд и паттерны на графике
2. Уровни поддержки/сопротивления
3. Индикаторы (если видны)

**ОТВЕТ НА ВОПРОС:**
Ответь на вопрос пользователя, используя визуальный анализ графика И актуальные данные.

Отвечай саркастично и кратко, как Syntra. Максимум 300 слов.
"""
    else:
        prompt += """
Проанализируй график и ответь на вопрос пользователя.
Используй то, что видишь на графике.
Отвечай кратко и по существу, саркастичный тон.
Максимум 250 слов.
"""

    return prompt
