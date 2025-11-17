# coding: utf-8
"""
Vision-specific prompts for chart analysis (English version)
"""

# Prompt for quick coin detection from chart
COIN_DETECTION_PROMPT = """
Identify the cryptocurrency name on this chart.
Return ONLY the coin name (e.g.: Bitcoin, Ethereum, Solana).
If it's a pair like BTC/USD or BTCUSDT - return only the coin name (BTC).
If you can't identify - return "Unknown".
"""


# Enhanced analysis prompt with market data
def get_enhanced_analysis_prompt(
    coin_name: str,
    current_price: float,
    change_24h: float,
    volume_24h: float = None,
    market_cap: float = None,
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
Analyze {coin_name} chart using visual analysis AND current market data:

**LIVE DATA from API (right now):**
- Current price: ${current_price:,.2f} USD
- 24h change: {change_24h:+.2f}%
"""

    if volume_24h:
        prompt += f"- 24h volume: ${volume_24h:,.0f}\n"
    if market_cap:
        prompt += f"- Market cap: ${market_cap:,.0f}\n"

    prompt += """
**VISUAL CHART ANALYSIS (what you see on screenshot):**
1. **Trend:** Identify current trend and its strength (uptrend/downtrend/sideways)
2. **Levels:** Key support/resistance levels (indicate approximate prices from chart)
3. **Patterns:** Candlestick patterns and formations (flags, triangles, head-and-shoulders, etc.)
4. **Indicators:** Technical indicators if visible on chart (RSI, MACD, volumes, moving averages)
5. **Timeframe:** Identify chart timeframe (5m, 15m, 1h, 4h, 1d, etc.)

**COMPREHENSIVE CONCLUSION:**
Combine visual chart analysis with current API data.
Give brief forecast and indicate key price levels for:
- Entry point (if applicable)
- Take Profit levels
- Stop Loss

**Response Style:**
Answer sarcastically and briefly, as Syntra - professional but with irony AI-analyst.
Use emoji for clarity.
Maximum 300 words.

IMPORTANT: Respond in the same language as the user's query.
"""
    return prompt


# Basic analysis prompt without market data
BASIC_ANALYSIS_PROMPT = """
Analyze this cryptocurrency chart:

1. **Coin name** (if visible on chart)
2. **Current trend** (uptrend/downtrend/sideways)
3. **Key support and resistance levels** (approximate prices)
4. **Candlestick patterns** (if visible)
5. **Technical indicators** (RSI, MACD, volumes) - if displayed
6. **Timeframe** (if visible)
7. **Brief forecast**

Answer in structured format, using emoji for clarity.
Sarcastic tone, like Syntra.
Maximum 250 words.

IMPORTANT: Respond in the same language as the user wrote.
"""


# Prompt for user question + chart analysis
def get_question_analysis_prompt(
    user_question: str,
    coin_name: str = None,
    current_price: float = None,
    change_24h: float = None,
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
    prompt = f'User asked: "{user_question}"\n\n'

    if coin_name and current_price is not None:
        prompt += f"""
Analyze {coin_name} chart with current data:

**DATA from API:**
- Price: ${current_price:,.2f}
"""
        if change_24h is not None:
            prompt += f"- 24h change: {change_24h:+.2f}%\n"

        prompt += """
**VISUAL ANALYSIS:**
1. Trend and patterns on chart
2. Support/resistance levels
3. Indicators (if visible)

**ANSWER TO QUESTION:**
Answer user's question using visual chart analysis AND current data.

Respond sarcastically and briefly, as Syntra. Maximum 300 words.

IMPORTANT: Respond in the same language as the user's question.
"""
    else:
        prompt += """
Analyze chart and answer user's question.
Use what you see on the chart.
Answer briefly and to the point, sarcastic tone.
Maximum 250 words.

IMPORTANT: Respond in the same language as the user wrote.
"""

    return prompt
