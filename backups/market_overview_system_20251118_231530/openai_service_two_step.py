# coding: utf-8
"""
Two-Step OpenAI Service: Analysis → Styling

This service separates data analysis from personality styling to maximize Syntra's character.

Architecture:
1. Step 1: Data Analysis (GPT-4o-mini)
   - Execute function calls to get crypto data
   - Structured analysis without personality
   - Fast and cost-effective

2. Step 2: Styling with Persona (GPT-4o)
   - Apply full Syntra personality to analysis
   - Dynamic sarcasm mode
   - Catchphrases and character enforcement
   - Creative and engaging

Benefits:
- ✅ Better personality preservation
- ✅ More consistent character
- ✅ Cleaner separation of concerns
- ✅ Higher quality responses
- ⚠️ Slightly higher cost (but worth it)
"""
import json
import logging
from typing import AsyncGenerator, Optional, List, Dict, Any
from datetime import datetime

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import OPENAI_API_KEY, ModelConfig
from config.prompt_selector import get_system_prompt
from config.prompts import get_random_catchphrase
from src.database.crud import add_chat_message, get_chat_history, track_cost
from src.services.openai_service import OpenAIService
from src.services.crypto_tools import CRYPTO_TOOLS, execute_tool


logger = logging.getLogger(__name__)


class TwoStepOpenAIService(OpenAIService):
    """
    Two-step AI service: Analysis → Styling

    Optimized for maximum personality preservation
    """

    # Enhanced system prompt for comprehensive data analysis (no personality, but deep analysis)
    ANALYSIS_SYSTEM_PROMPT = """
You are a professional crypto market data analyst. Your job is to provide COMPREHENSIVE and CONTEXT-AWARE analysis.

# Your Tasks:
1. **Gather Data**: Call relevant tools to get all available data
2. **Analyze User Context**: Extract and analyze ALL information user provided (team, events, roadmap, concerns)
3. **Assess Market Context**: Examine market phase, token lifecycle, and trends
4. **Evaluate Risks**: Analyze liquidity, volume, regulatory, and project-specific risks
5. **Identify Patterns**: Look for price action, momentum, and market sentiment
6. **Project Scenarios**: Provide multiple scenarios with criteria for decision-making

# SPECIAL: Market Overview Requests
When user asks about the overall market ("what's happening in crypto", "market overview", "что по рынку"):
- CALL: get_market_overview() - returns structured data for BTC, ETH, market metrics, news
- The tool already provides: BTC price/RSI/levels, ETH price, dominance, Fear & Greed, trend, relevant news
- Your output should be MINIMAL - just return the raw JSON data for styling step
- DO NOT write prose, just return: "Market data collected: [JSON summary]"
- The styling step will create the narrative from this data

# Analysis Framework (use even with limited data):

**Technical Layer** (if available):
- Price action and momentum
- Support/resistance levels
- Technical indicators (RSI, MACD, etc.)
- Volume analysis and trends

**Fundamental Layer** (always analyze):
- Market cap and FDV (valuation)
- Liquidity depth (risk of manipulation)
- Trading volume (24h, 6h, 1h trends)
- Token lifecycle phase: Early Launch / Growth / Mature / Declining

**User Context Analysis** (ALWAYS ANALYZE):
- Extract ALL details user mentioned: team, founders, partnerships, upcoming events, product plans
- Analyze project type: Creator-driven (influencer/celebrity), community-driven, VC-backed, anonymous
- Assess roadmap items: Products, utilities, tokenomics changes (buybacks/burns/staking)
- Evaluate hype factors: Media presence, social following, narrative strength
- Identify regulatory/reputation risks: Legal concerns, controversial associations, compliance issues
- Understand user's position: Entry price, current P&L, emotional state (loss/profit/neutral)

**Risk Assessment** (CRITICAL):
- Liquidity risk: <$100k = EXTREME (easy manipulation), $100k-$1M = HIGH, $1M-$10M = MODERATE, >$10M = LOW
- Volume risk: Low volume (<$100k/24h) = pump&dump risk, declining volume = exit liquidity trap
- Project-specific risks: Anonymous team, no product, regulatory concerns, influencer dependency
- News sentiment and fundamental changes
- Market conditions (Fear & Greed Index)

**SCAM DETECTION** (REFUSE to analyze if ALL conditions met):
If a token has ALL of these red flags, REFUSE analysis and warn user:
1. Liquidity < $1,000 USD (extreme manipulation risk)
2. 24h Volume < $500 USD (dead/fake token)
3. No significant market cap or FDV data
RESPONSE: "This token shows extreme scam indicators (liquidity <$1k, volume <$500).
Analysis refused - likely a honeypot, rug pull, or dead project. DO NOT invest."

**Perspectives** (project outcomes):
- Short-term (1-7 days): Based on momentum, volume, news
- Mid-term (1-4 weeks): Based on fundamentals, market cycle
- Long-term (1-3 months): Based on project viability, adoption

# For DEX-only tokens:
- Analyze liquidity stability over time (1h/6h/24h volume trends)
- Assess transaction count (health indicator)
- Check price volatility (5m/1h/6h/24h changes)
- Evaluate chain and DEX (Solana/Raydium more volatile than ETH/Uniswap)
- **Buy/Sell Pressure**: Calculate ratio of buys vs sells (>1.2 = bullish, <0.8 = bearish)
- **Momentum Analysis**: Use 5m/1h/6h/24h price changes to identify trend direction
- **Entry Points**: Calculate specific price levels based on:
  * Current volatility (from price_change data)
  * Volume-weighted support (current price - 2-5% for conservative, 5-10% for aggressive)
  * Buy pressure zones (where buys > sells historically)

# Output Format:
Structure your analysis clearly with sections:
- Data Summary (what we found from tools)
- User Context Summary (what user told us - team, events, plans, position)
- Technical Analysis (if available) OR Price Action Analysis (for DEX)
- Fundamental Assessment (liquidity, volume, market cap, phase, creator influence)
- Risk Analysis (specific risks with data + regulatory + project risks)
- **Fibonacci & Price Levels Analysis** (if fibonacci_levels available in data):
  * Current Fibonacci zone (e.g., "0%-23.6% Near ATL oversold zone")
  * Distance from ATH (percentage)
  * Key support levels (Fibonacci + historical S/R)
  * Key resistance levels (Fibonacci + historical S/R)
  * Interpretation of current position in the cycle
- **Decision Scenarios** (CRITICAL - use scenario_levels from data if available):
  * USE the pre-calculated scenario_levels.scenarios data from tools
  * Scenario A: Bullish Scenario
    - Entry zones: Use scenario_levels.scenarios.bullish_scenario.entry_zone (conservative & aggressive)
    - Stop loss: Use scenario_levels.scenarios.bullish_scenario.stop_loss
    - Targets: Use scenario_levels.scenarios.bullish_scenario.targets (target_1, target_2, target_3)
    - Conditions: Add/expand on scenario_levels.scenarios.bullish_scenario.conditions
  * Scenario B: Bearish Scenario
    - Entry zones: Use scenario_levels.scenarios.bearish_scenario.entry_zone
    - Stop loss: Use scenario_levels.scenarios.bearish_scenario.stop_loss
    - Targets: Use scenario_levels.scenarios.bearish_scenario.targets
    - Conditions: Add/expand on scenario_levels.scenarios.bearish_scenario.conditions
  * Scenario C: Range Trading (if applicable)
    - Range boundaries: Use scenario_levels.scenarios.range_bound_scenario.range
    - Strategy: scenario_levels.scenarios.range_bound_scenario.strategy
  * For EACH scenario: Include risk/reward ratio, probability assessment, decision criteria
  * If scenario_levels NOT available: Generate scenarios manually based on current price ±5-10%
- Perspectives (short/mid/long-term based on data and user context)

IMPORTANT RULES:
- NEVER say "buy", "sell", "hold", "average down" as direct advice
- Instead use "Scenario A/B/C" format with criteria for decision-making
- ALWAYS use specific price levels from fibonacci_levels and scenario_levels when available
- If ATH date (ath_date) is in extended_data, ALWAYS mention it with context (e.g., "ATH $2.39 was 11 months ago on Jan 12, 2024")
- Be objective, factual, and thorough. NO personality in this step.
- Focus on actionable insights with clear decision frameworks and CONCRETE price levels
"""

    async def stream_two_step_completion(
        self,
        session: AsyncSession,
        user_id: int,
        user_message: str,
        user_language: str = "ru",
        max_tool_iterations: int = 5,
    ) -> AsyncGenerator[str, None]:
        """
        Two-step streaming completion with enhanced personality

        Step 1: Get data with function calling (mini model, no personality)
        Step 2: Style response with full Syntra persona (4o model, max creativity)

        Args:
            session: Database session
            user_id: User's database ID
            user_message: User's message
            user_language: User's language ('ru' or 'en')
            max_tool_iterations: Max function calling iterations

        Yields:
            Text chunks from final styled response
        """
        try:
            # Save user message to history
            await add_chat_message(
                session, user_id=user_id, role="user", content=user_message
            )

            logger.info(
                f"🎬 Two-step process started for user {user_id}: {user_message[:50]}..."
            )

            # ==========================================
            # STEP 1: DATA ANALYSIS (mini, no personality)
            # ==========================================

            logger.info("📊 Step 1: Analyzing data with function calling...")

            # Get recent chat history for context (last 5 messages)
            history = await get_chat_history(session, user_id, limit=5)

            # Build analysis messages with context
            analysis_messages: List[Dict[str, Any]] = [
                {"role": "system", "content": self.ANALYSIS_SYSTEM_PROMPT}
            ]

            # Add recent history for context (but not the last message - it's user_message)
            for msg in history[:-1]:  # Exclude last message (it's the current one we just saved)
                analysis_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

            # Add current user message
            analysis_messages.append({"role": "user", "content": user_message})

            step1_input_tokens = 0
            step1_output_tokens = 0
            tool_calls_made = []
            structured_analysis = ""

            # Iterative function calling loop
            iteration = 0
            while iteration < max_tool_iterations:
                iteration += 1

                # Use mini for data gathering (cost-effective)
                response = await self.client.chat.completions.create(
                    model=ModelConfig.GPT_4O_MINI,
                    messages=analysis_messages,
                    tools=CRYPTO_TOOLS,
                    tool_choice="auto",
                    max_tokens=800,  # Enough for structured analysis
                    temperature=0.3,  # Low temperature for factual analysis
                )

                message = response.choices[0].message

                # Track tokens
                if response.usage:
                    step1_input_tokens += response.usage.prompt_tokens
                    step1_output_tokens += response.usage.completion_tokens

                # Check if AI wants to call tools
                if message.tool_calls:
                    logger.info(f"🔧 AI requested {len(message.tool_calls)} tool calls")

                    # Add assistant message with tool calls
                    analysis_messages.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in message.tool_calls
                        ],
                    })

                    # Execute tools
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_id = tool_call.id

                        try:
                            arguments = json.loads(tool_call.function.arguments)
                            logger.info(f"⚙️ Executing: {tool_name}({arguments})")

                            result = await execute_tool(tool_name, arguments)

                            analysis_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": result,
                            })

                            tool_calls_made.append({
                                "name": tool_name,
                                "arguments": arguments,
                            })

                        except Exception as e:
                            logger.error(f"❌ Tool execution failed: {e}")
                            analysis_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": json.dumps({"success": False, "error": str(e)}),
                            })

                    # Continue to next iteration
                    continue

                else:
                    # No more tools - AI provided structured analysis
                    structured_analysis = message.content or ""
                    logger.info(f"✅ Step 1 complete. Analysis: {len(structured_analysis)} chars")
                    break

            # ==========================================
            # STEP 2: STYLING WITH SYNTRA PERSONA (4o, full creativity)
            # ==========================================

            logger.info("🎨 Step 2: Styling with Syntra persona...")

            # Build persona prompt with dynamic sarcasm detection
            syntra_system_prompt = get_system_prompt(
                user_language,
                user_message=user_message  # Auto-detect sarcasm mode
            )

            # Detect if user mentioned losses/drawdown for SAFEGUARD
            # ВАЖНО: Не использовать просто "-" как триггер (ложные срабатывания на "BTC -5%")
            user_has_losses = any(trigger in user_message.lower() for trigger in [
                "просадка", "убыток", "в минусе", "потерял", "слил", "ликвиднули"
            ])

            safeguard_instruction = ""
            if user_has_losses:
                safeguard_instruction = """
⚠️ SAFEGUARD MODE: Пользователь упомянул убытки или просадку.
- ПОЛНОСТЬЮ убери сарказм и иронию
- Говори спокойно, рационально, поддерживающе
- Фокус на помощи принять взвешенное решение
"""

            # Detect if this is a market overview question
            is_market_overview = any(keyword in user_message.lower() for keyword in [
                "по рынку", "рынок", "что происходит", "как крипта", "market",
                "обзор рынка", "общая ситуация", "общий тренд"
            ])

            # Create styling prompt based on question type
            if is_market_overview:
                styling_prompt = f"""
Вот данные о рынке от аналитика:

{structured_analysis}

{safeguard_instruction}

Твоя задача — СОЗДАТЬ С НУЛЯ ответ в стиле Syntra, используя данные которые есть и релевантны для вопроса.

🔥 КРИТИЧЕСКИ ВАЖНО - ИСПОЛЬЗУЙ ТО ЧТО РЕАЛЬНО ВАЖНО:

1. **BTC УРОВНИ** (используй если есть):
   - scenario_levels.key_levels.immediate_support/resistance → основные уровни
   - scenario_levels.key_levels.ema_levels → с distance_pct (например: "цена на 3% ниже EMA50 — ещё терпимо")
   - support_resistance.liquidity_zones → зоны с высоким объёмом ("здесь свеча +3% на объёме x1.8 — зона ликвидности")
   - fibonacci_levels → дополнительный контекст если релевантно

2. **ВОЛАТИЛЬНОСТЬ** (если доступна):
   - scenario_levels.atr → "ATR $XX — движение рваное/спокойное"
   - Для торговли: используй ATR-based SL/TP из scenarios

3. **ФЬЮЧЕРСНЫЕ ДАННЫЕ** (если доступны и релевантны):
   - funding_rate + funding_sentiment → "фандинг +0.02% (bullish bias)"
   - long_short_ratio + ls_sentiment → "лонгисты 1.2:1 (толпа в лонгах)"

4. **MARKET PHASE** (если доступен):
   - cycle_data.current_band → "Rainbow Chart: HODL зона" или "Buy zone"

⚠️ НЕ нужно впихивать абсолютно все поля в каждый ответ - используй то что реально важно для вопроса пользователя.

5. **СТРУКТУРА ОТВЕТА**:
   ```
   BTC на $XX (+/-Y%), поддержка $ZZ (EMA50), сопротивление $WW.
   RSI X, MACD [signal], ATR $1.2k — волатильность [низкая/средняя/высокая].
   [Если есть funding/long-short]: Фандинг +X%, лонгисты X:1 — [интерпретация].
   [Если market phase]: Rainbow Chart: [фаза] — [что это значит].

   Доминация BTC X%, ETH X%, альты X%. F&G: X ([жадность/страх/нейтрал]).

   ETH на $XX (+/-Y%) [если релевантно].

   [Торговый взгляд если спрашивают]:
   Long bias / Short bias / No-trade zone.
   Если хочешь [лонг/шорт] — жди [условие] от $XX. SL за $YY (ATR-based). TP у $ZZ.

   ⚡ NFA
   ```

🚫 **АБСОЛЮТНО ЗАПРЕЩЕНО**:
- Выдумывать уровни которых НЕТ в scenario_levels.key_levels ("поддержка $77,943" если этого числа нет в данных)
- Игнорировать важные данные (ATR, funding, long/short, market phase) если они релевантны для вопроса
- "количество активных криптовалют", "следите за", "обратите внимание", "рекомендую"
- Вода без конкретики

📊 **ФОРМАТ УРОВНЕЙ**:
- Если уровень ЕСТЬ в данных: "$XX" (конкретная цифра)
- Если уровня НЕТ: "зона поддержки ~XX-YYk" (диапазон)
- Если уровень = EMA: "$XX (EMA50)" — указывай источник

🎯 **ЕСЛИ СПРАШИВАЮТ ПРО ТОРГОВЛЮ** ("лонговать/шортить/сторона"):
- Дай чёткий bias: long bias / short bias / no-trade zone
- ИСПОЛЬЗУЙ scenario_levels.scenarios.bullish_scenario или bearish_scenario:
  * entry_zone (conservative/aggressive)
  * stop_loss (conservative/aggressive) - для лонга: entry - ATR, для шорта: entry + ATR
  * targets (target_1, target_2, target_3)
- Если есть scenario_levels.leverage_recommendation → УПОМЯНИ ОСТОРОЖНО:
  * "Для такой волатильности разумный диапазон плеча — до [X]x. Всё выше — уже казино."
  * Например: "При ATR 3.2% (средняя волатильность) — до 3-5x макс"
  * ⚠️ Это чувствительная зона - давай примерные диапазоны, не конкретные советы
- Объясни ПОЧЕМУ (RSI, тренд, funding, long/short, market phase)
- Формат: "Если хочешь лонг — entry от $XX, SL за $YY, TP у $ZZ."
- ОБЯЗАТЕЛЬНО NFA в конце

⏱️ **ДЛИНА**: 180-220 слов максимум

Исходный вопрос: "{user_message}"
"""
            else:
                styling_prompt = f"""
Вот структурированный анализ от аналитика:

{structured_analysis}

{safeguard_instruction}

Твоя задача — СОЗДАТЬ С НУЛЯ ответ в стиле Syntra, используя данные аналитика.

КРИТИЧЕСКИ ВАЖНО:
- Используй ВСЕ важные факты которые пользователь упомянул (команда, события, планы, roadmap)
- Проанализируй ВСЕ риски которые аналитик выявил
- Сохрани формат "Сценарий А/Б/В/Г" - НИКОГДА не давай прямые советы типа "держи", "покупай", "усредняйся"
- Каждый сценарий должен иметь: условия, риски, критерии принятия решения

ФОРМАТ (БЕЗ ### заголовков, только эмодзи + текст):
📊 Технический анализ
(данные + уровни)

📰 Контекст проекта
(что пользователь рассказал + аналитика фундамента)

💡 Мой взгляд
(аналитика + характер, но БЕЗ сарказма если SAFEGUARD)

⚠️ Риски
(все риски: ликвидность, регуляторные, проектные)

🎯 Сценарии решений
(А/Б/В/Г с критериями)

⚡ NFA

ВАЖНО: НЕ используй ### или другие markdown заголовки. Только эмодзи + название секции + перевод строки + контент.

Исходный вопрос: "{user_message}"
"""

            styling_messages = [
                {"role": "system", "content": syntra_system_prompt},
                {"role": "user", "content": styling_prompt},
            ]

            # Stream styled response with GPT-4o (best model for creativity)
            stream = await self.client.chat.completions.create(
                model=ModelConfig.GPT_4O,  # ⚡ Always use 4o for styling
                messages=styling_messages,
                max_tokens=ModelConfig.MAX_TOKENS_RESPONSE,
                temperature=ModelConfig.DEFAULT_TEMPERATURE,  # 0.85 for creativity
                stream=True,
            )

            step2_input_tokens = 0
            step2_output_tokens = 0
            full_response = ""

            # Stream response to user
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content

                # Track tokens
                if hasattr(chunk, "usage") and chunk.usage:
                    step2_input_tokens = chunk.usage.prompt_tokens
                    step2_output_tokens = chunk.usage.completion_tokens

            # Estimate tokens if not provided
            if step1_input_tokens == 0:
                step1_input_tokens = self.count_tokens(self.ANALYSIS_SYSTEM_PROMPT + user_message)
            if step1_output_tokens == 0:
                step1_output_tokens = self.count_tokens(structured_analysis)
            if step2_input_tokens == 0:
                step2_input_tokens = self.count_tokens(syntra_system_prompt + styling_prompt)
            if step2_output_tokens == 0:
                step2_output_tokens = self.count_tokens(full_response)

            # Calculate total cost
            step1_cost = self.calculate_cost(
                ModelConfig.GPT_4O_MINI, step1_input_tokens, step1_output_tokens
            )
            step2_cost = self.calculate_cost(
                ModelConfig.GPT_4O, step2_input_tokens, step2_output_tokens
            )
            total_cost = step1_cost + step2_cost

            # Save assistant response to history
            await add_chat_message(
                session, user_id=user_id, role="assistant", content=full_response
            )

            # Track cost
            await track_cost(
                session,
                user_id=user_id,
                service="openai_two_step",
                model=f"mini+4o",
                tokens=step1_input_tokens + step2_input_tokens + step1_output_tokens + step2_output_tokens,
                cost=total_cost,
            )

            logger.info(
                f"✅ Two-step complete for user {user_id}\n"
                f"   Step 1 (mini): {step1_input_tokens}+{step1_output_tokens} tokens, ${step1_cost:.4f}\n"
                f"   Step 2 (4o):   {step2_input_tokens}+{step2_output_tokens} tokens, ${step2_cost:.4f}\n"
                f"   Total: ${total_cost:.4f}, Tools: {len(tool_calls_made)}"
            )

        except Exception as e:
            logger.exception(f"❌ Error in two-step completion: {e}")
            yield ""


# Global instance
two_step_service = TwoStepOpenAIService()
