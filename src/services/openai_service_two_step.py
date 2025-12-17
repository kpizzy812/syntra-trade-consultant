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
from typing import AsyncGenerator, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from config.config import ModelConfig
from config.prompt_selector import get_system_prompt
from src.database.crud import add_chat_message, get_chat_history, track_cost
from src.services.openai_service import OpenAIService
from src.services.crypto_tools import CRYPTO_TOOLS, execute_tool


from loguru import logger


class TwoStepOpenAIService(OpenAIService):
    """
    Two-step AI service: Analysis → Styling

    Optimized for maximum personality preservation
    """

    # Data collection prompt - ONLY JSON, no analysis
    ANALYSIS_SYSTEM_PROMPT = """
You are a crypto data collector. Your ONLY job: call tools, return raw data as JSON.

# CRITICAL RULES:
1. **ALWAYS call relevant tools first** - NEVER respond without calling tools
2. **ALWAYS return ONLY JSON** - zero text, zero comments, zero analysis
3. **NO conclusions** - just raw data from tools
4. **NO interpretation** - Step 2 (smarter model) will do ALL analysis
5. **NEVER say "I need data"** - YOU must call tools to get data yourself

You are a task runner. Fetch data → Format as JSON → Done.

# TOOL SELECTION:

## Market Overview / Risk-Reward Questions
User asks: "что по рынку", "market overview", "где больше риск ревард", "what's the best RR"
→ CALL: get_market_overview()
→ RETURN: exact JSON from tool (btc, eth, alts, market, news)

## Specific Coin Trading Questions
User asks: "long/short ETH?", "BTC до 100к?", "ARB норм тема?"
→ CALL: get_technical_analysis(coin_id, timeframe)
  - timeframe: "1d" for swing, "4h" for day trade, "1h" for scalping
→ RETURN: {
  "coin_id": "...",
  "price": ...,
  "change_24h": ...,
  "technical_indicators": {...},  // RSI, MACD, EMA, ATR
  "scenario_levels": {...},       // entry/SL/TP levels
  "support_resistance": {...},    // S/R levels, liquidity zones
  "fibonacci_levels": {...},      // fib retracement
  "funding_data": {...},          // funding rate, sentiment (if available)
  "long_short_data": {...},       // L/S ratio, sentiment (if available)
  "cycle_data": {...},            // rainbow chart (BTC only)
  "extended_market_data": {...},  // ATH/ATL, market cap, volume
  "candles": {...},               // multi-timeframe OHLCV data
  "news": [...]                   // latest news (if available)
}

## Quick Price Check
User asks: "цена SOL", "сколько стоит BTC"
→ CALL: get_crypto_price(coin_id)
→ RETURN: {"coin_id": "...", "price": ..., "change_24h": ..., "market_cap": ..., "volume": ...}

## News Questions
User asks: "новости BTC", "что нового про Ethereum"
→ CALL: get_crypto_news(coin_id)
→ RETURN: {"coin_id": "...", "news": [...]}

## DEX Token Analysis
User asks about low-cap/DEX token: "что с BONK", "как там PEPE"
→ CALL: get_dex_token_info(token_address, chain)
→ RETURN: {
  "address": "...",
  "price": ...,
  "liquidity": ...,
  "volume_24h": ...,
  "price_change_5m": ...,
  "price_change_1h": ...,
  "price_change_6h": ...,
  "price_change_24h": ...,
  "txns": {...},
  "holders": ...
}

# SCAM DETECTION:
If token has ALL these flags:
- Liquidity < $1,000
- Volume 24h < $500
- No market cap data
→ RETURN: {"error": "scam_detected", "reason": "liquidity <$1k, volume <$500, likely honeypot/rug"}

# USER CONTEXT EXTRACTION:
If user mentions team/events/roadmap/position:
→ ADD to JSON: {
  "user_context": {
    "mentioned_team": "...",
    "mentioned_events": "...",
    "user_position": "...",  // entry price, P&L if mentioned
    "concerns": "..."
  }
}

# OUTPUT FORMAT:
ALWAYS return pure JSON. No text before/after. Example:

{
  "data_type": "technical_analysis",
  "coin_id": "ethereum",
  "price": 3120,
  "technical_indicators": {...},
  "scenario_levels": {...},
  ...
}

If get_market_overview():
{
  "data_type": "market_overview",
  "btc": {...},
  "eth": {...},
  "alts": [...],
  "market": {...},
  "news": [...]
}

# SPECIAL CASES:
If user asks general question (not about specific crypto/market):
{
  "data_type": "general_question",
  "question": "user question text",
  "context": "any relevant context from history"
}

If tools fail or data unavailable:
{
  "data_type": "error",
  "error": "brief error description",
  "fallback_data": {...}  // any partial data you got
}

NO comments. NO explanations. NO text like "I need data" or "Please provide". ONLY JSON.
"""

    async def stream_two_step_completion(
        self,
        session: AsyncSession,
        user_id: int,
        user_message: str,
        user_language: str = "ru",
        user_tier: str = "free",
        max_tool_iterations: int = 5,
    ) -> AsyncGenerator[str, None]:
        """
        Two-step streaming completion with enhanced personality (tier-aware)

        Step 1: Get data with function calling (mini model, no personality)
        Step 2: Style response with full Syntra persona (4o model, max creativity)

        Tier-based Memory:
        - FREE: 0 messages (no memory)
        - BASIC: 5 messages
        - PREMIUM: 10 messages
        - VIP: 50 messages

        Args:
            session: Database session
            user_id: User's database ID
            user_message: User's message
            user_language: User's language ('ru' or 'en')
            user_tier: User's subscription tier (free, basic, premium, vip)
            max_tool_iterations: Max function calling iterations

        Yields:
            Text chunks from final styled response
        """
        from config.limits import get_chat_history_limit, should_save_chat_history
        from src.database.models import SubscriptionTier

        try:
            # Get tier enum
            try:
                tier_enum = SubscriptionTier(user_tier)
            except ValueError:
                logger.warning(f"Invalid tier '{user_tier}', defaulting to FREE")
                tier_enum = SubscriptionTier.FREE

            # Get history limit for tier
            max_history = get_chat_history_limit(tier_enum)

            logger.info(
                f"🎬 Two-step process started for user {user_id} (tier={user_tier}, history_limit={max_history}): {user_message[:50]}..."
            )

            # Save user message to history (only for tiers with save_chat_history=True)
            if should_save_chat_history(tier_enum):
                await add_chat_message(
                    session, user_id=user_id, role="user", content=user_message
                )
                logger.debug(f"User message saved to history for tier {user_tier}")
            else:
                logger.debug(
                    f"User message NOT saved to history for tier {user_tier} (save_chat_history=False)"
                )

            # ==========================================
            # STEP 1: DATA ANALYSIS (mini, no personality)
            # ==========================================

            logger.info("📊 Step 1: Analyzing data with function calling...")

            # Get recent chat history for context (tier-aware)
            history = []
            if max_history > 0:
                history = await get_chat_history(session, user_id, limit=max_history)
                logger.info(f"Loaded {len(history)} messages from history")
            else:
                logger.info(f"No history loaded for FREE tier")

            # Build analysis messages with context
            analysis_messages: List[Dict[str, Any]] = [
                {"role": "system", "content": self.ANALYSIS_SYSTEM_PROMPT}
            ]

            # Add recent history for context
            # If we saved current message (paid tiers), exclude it from history
            # If we didn't save (FREE tier), use all history
            history_to_use = history[:-1] if should_save_chat_history(tier_enum) and len(history) > 0 else history
            for msg in history_to_use:
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
                response = await self.openai_client.chat.completions.create(
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

                            # Логируем что вернул tool
                            logger.info(f"📦 Tool {tool_name} result: {len(result)} chars")
                            try:
                                result_data = json.loads(result)
                                if result_data.get('success'):
                                    data_sources = result_data.get('data_sources', [])
                                    logger.info(f"   ✅ Data sources: {data_sources}")
                                    if 'funding_data' in result_data and result_data['funding_data']:
                                        logger.info(f"   💰 Funding: {result_data['funding_data']}")
                                    if 'long_short_data' in result_data and result_data['long_short_data']:
                                        logger.info(f"   📈 L/S Ratio: {result_data['long_short_data']}")
                                    if 'cycle_data' in result_data and result_data['cycle_data']:
                                        logger.info(f"   🌈 Cycle: {result_data['cycle_data'].get('current_band')}")
                            except:
                                pass

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
                    logger.info(f"📝 STRUCTURED ANALYSIS:\n{structured_analysis}\n{'='*80}")
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
            # Также проверяем паттерн "в минусе -X%" или "минус X%"
            import re
            loss_percentage_pattern = r'(в минусе|минус|убыток).{0,5}[-\d]+%'
            has_loss_percentage = bool(re.search(loss_percentage_pattern, user_message.lower()))

            user_has_losses = has_loss_percentage or any(trigger in user_message.lower() for trigger in [
                "просадка", "убыток", "в минусе", "потерял", "слил", "ликвиднули",
                "обнулился", "потерял всё", "паника", "страшно", "боюсь"
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

            # Detect if this is a newbie question (educational)
            is_newbie_question = any(keyword in user_message.lower() for keyword in [
                "что такое", "что значит", "как работает", "объясни", "не понимаю",
                "расскажи про", "зачем нужен", "в чём разница", "для чего",
                "what is", "what does", "how does", "explain"
            ])

            # Detect if this is a trading question (specific coin analysis)
            # Включаем также вопросы про просадки/hold/sell
            is_trading_question = any(keyword in user_message.lower() for keyword in [
                "лонг", "шорт", "long", "short", "взять", "зайти", "купить", "продать",
                "лонговать", "шортить", "докатит до", "дойдет до", "расклад",
                "стоит ли брать", "имеет смысл", "норм тема",
                "держать", "фиксить", "фиксировать", "продавать", "выходить",
                "в минусе", "просадка", "убыток", "hold", "sell"
            ]) and any(coin in user_message.lower() for coin in [
                "btc", "eth", "биток", "эфир", "bitcoin", "ethereum", "солана", "solana",
                "bnb", "xrp", "ada", "dot", "doge", "shib", "avax", "matic", "link", "uni",
                "арб", "arb", "arbitrum", "op", "optimism"
            ])

            # Create styling prompt based on question type
            if is_trading_question:
                styling_prompt = f"""
Ты получил актуальные данные по монете:

{structured_analysis}

{safeguard_instruction}

⚡ ТВОЯ ЗАДАЧА — ПРОАНАЛИЗИРОВАТЬ И ДАТЬ РЕКОМЕНДАЦИЮ:

ВАЖНО: НИКОГДА не упоминай "JSON", "data collector", "данные", "структуру" или любые технические детали работы системы в ответе пользователю.
Отвечай так, будто ты ВСЕГДА имел доступ к этой информации.

Используй полученные данные:
- Технические индикаторы (RSI, MACD, EMA, ATR)
- Уровни входа/выхода и стоп-лоссов
- Уровни поддержки и сопротивления
- Данные по фандингу и настроениям рынка
- Соотношение лонгов/шортов
- Фаза рыночного цикла (для BTC)
- Исторические данные (ATH/ATL, объемы)

Проанализируй эту информацию и дай профессиональную рекомендацию.

ФОРМАТ ОТВЕТА (адаптируй под вопрос пользователя):

Анализируй ЕСТЕСТВЕННО, как Syntra - профессионал с характером:

1. **ПРЯМОЙ ОТВЕТ**:
   - Если вопрос про long/short → дай bias с обоснованием из данных
   - Если вопрос про "держать или продать" → дай анализ ситуации и сценарии
   - Если вопрос "дойдет до $X" → рассчитай путь по уровням с вероятностью
   - Если вопрос про просадку → оцени текущую ситуацию и риски

2. **СЦЕНАРИИ** (если релевантно):
   - Бычий сценарий с условиями и уровнями
   - Медвежий сценарий с условиями и уровнями
   - Используй данные: RSI, funding, S/R уровни, объемы

3. **ВЫВОД**: Твоя чёткая позиция на основе анализа

4. **КОНКРЕТИКА**: Обязательно используй конкретные цифры ($, %, RSI, funding)

⚠️ ЗАПРЕЩЕНО упоминать в ответе: "JSON", "данные от data collector", "structured_analysis", "нет данных в документе", или любые технические детали системы.

НЕ используй жесткие шаблоны. Отвечай как профессиональный аналитик с характером Syntra.

Добавь в конце: ⚡ NFA

Вопрос: "{user_message}"
"""
            elif is_market_overview:
                styling_prompt = f"""
Ты получил актуальные данные по рынку:

{structured_analysis}

{safeguard_instruction}

⚡ ТВОЯ ЗАДАЧА — ПРОАНАЛИЗИРОВАТЬ РЫНОК И ДАТЬ ВЫВОДЫ:

ВАЖНО: НИКОГДА не упоминай "JSON", "data collector", "данные", или технические детали в ответе.

Используй полученную информацию:
- BTC: цена, изменение, расстояние от ATH, технические индикаторы
- BTC: уровни поддержки/сопротивления, фандинг, long/short ratio
- BTC: фаза рыночного цикла (Rainbow Chart)
- ETH: цена, изменение, расстояние от ATH
- Альткоины: массив монет с ценами и просадками от ATH
- Рынок: доминация BTC/ETH/альтов, индекс страха и жадности
- Новости: последние события на рынке

Проанализируй эту информацию и сделай профессиональные выводы.

ФОРМАТ (для market overview):
- 2-3 строки: общая картина (dominance, F&G, trend) + твой вывод
- 2-3 строки: BTC (цена, RSI, уровни, funding) + куда движется
- 1-2 строки: альты/ETH + сравнение с BTC
- 1 строка: циничный вывод

ФОРМАТ (для risk/reward вопросов):
- Разбей по сегментам: BTC / ETH / Alts
- Для каждого: % от ATH → потенциал до ATH → RR оценка
- Вывод: где максимальный RR и почему

Используй конкретные цифры и данные.

⚠️ ЗАПРЕЩЕНО упоминать: "JSON", "данные", "data collector", "документ", или технические детали системы.

Добавь в конце: ⚡ NFA

Вопрос: "{user_message}"
"""
            elif is_newbie_question:
                styling_prompt = f"""
Вот структурированный анализ от аналитика:

{structured_analysis}

{safeguard_instruction}

Твоя задача — ответить на вопрос новичка в стиле Syntra, используя данные из анализа.

💬 **ПИШИ ПРОСТО И ПОНЯТНО**:
- Объясняй термины простым языком, без жаргона
- Используй аналогии и примеры из жизни
- НЕ перегружай терминами (RSI, MACD, Fibonacci и тд) — только если это сам вопрос
- Структурируй ответ: суть → пример → зачем это нужно

✅ **ОБЯЗАТЕЛЬНО**:
1. **ПРЯМОЙ ОТВЕТ**: Дай определение/объяснение коротко (1-2 предложения)

2. **ПРИМЕР**: Покажи на конкретном примере с ценами

3. **ПРАКТИКА**: Зачем это нужно трейдеру / как использовать

4. **СТИЛЬ**: Лёгкая ирония допустима, но без высокомерия. Ты обучаешь, а не стебёшься над новичком.

5. Добавь в конце: ⚡ NFA (если релевантно)

Исходный вопрос: "{user_message}"
"""
            else:
                styling_prompt = f"""
Ты получил актуальную информацию:

{structured_analysis}

{safeguard_instruction}

⚡ ТВОЯ ЗАДАЧА — ПРОАНАЛИЗИРОВАТЬ И ДАТЬ ОТВЕТ:

ВАЖНО: НИКОГДА не упоминай "JSON", "данные", "data collector" или технические детали в ответе пользователю.

Используй полученную информацию:
- Цена, изменение за 24ч, капитализация, объем, ликвидность
- Технические индикаторы (если есть): RSI, MACD, EMA
- Уровни поддержки/сопротивления, уровни Фибоначчи
- Уровни входа/выхода и стоп-лоссов
- Контекст: команда, события, roadmap, позиция пользователя
- Новости и настроения рынка

Проанализируй эту информацию и дай профессиональную рекомендацию.

ФОРМАТ ОТВЕТА:

Отвечай ЕСТЕСТВЕННО на основе вопроса пользователя. НЕ используй шаблоны типа "Держать/Фиксить".
Формат ответа должен соответствовать ВОПРОСУ:
- Если спрашивают про цену → дай анализ цены и тренда
- Если спрашивают про уровни → дай конкретные уровни с обоснованием
- Если спрашивают про риски → оцени риски на основе данных
- Если спрашивают про действия (держать/продать) → дай несколько сценариев с условиями

ОБЯЗАТЕЛЬНО:
1. **КОНКРЕТИКА**: Используй конкретные цифры ($, %, RSI, объёмы)
2. **ВЫВОД**: Чёткая итоговая позиция основанная на анализе
3. Добавь в конце: ⚡ NFA

⚠️ ЗАПРЕЩЕНО упоминать: "JSON", "данные от collector", "в документе нет", "мне нечего анализировать", или любые технические детали системы.

Вопрос: "{user_message}"
"""

            styling_messages = [
                {"role": "system", "content": syntra_system_prompt},
                {"role": "user", "content": styling_prompt},
            ]

            logger.info(f"🎨 Styling prompt length: {len(styling_prompt)} chars")
            logger.debug(f"🎨 STYLING PROMPT:\n{styling_prompt}\n{'='*80}")

            # Stream styled response with GPT-4o (best model for creativity)
            stream = await self.openai_client.chat.completions.create(
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

            # Save assistant response to history (only for tiers with save_chat_history=True)
            if should_save_chat_history(tier_enum):
                await add_chat_message(
                    session, user_id=user_id, role="assistant", content=full_response
                )
                logger.debug(f"Assistant response saved to history for tier {user_tier}")
            else:
                logger.debug(
                    f"Assistant response NOT saved to history for tier {user_tier} (save_chat_history=False)"
                )

            # Track cost
            await track_cost(
                session,
                user_id=user_id,
                service="openai_two_step",
                model="mini+4o",
                tokens=(
                    step1_input_tokens
                    + step2_input_tokens
                    + step1_output_tokens
                    + step2_output_tokens
                ),
                cost=total_cost,
            )

            logger.info(
                f"✅ Two-step complete for user {user_id}\n"
                f"   Step 1 (mini): {step1_input_tokens}+"
                f"{step1_output_tokens} tokens, ${step1_cost:.4f}\n"
                f"   Step 2 (4o):   {step2_input_tokens}+"
                f"{step2_output_tokens} tokens, ${step2_cost:.4f}\n"
                f"   Total: ${total_cost:.4f}, Tools: {len(tool_calls_made)}"
            )

        except Exception as e:
            logger.exception(f"❌ Error in two-step completion: {e}")
            yield ""


# Global instance
two_step_service = TwoStepOpenAIService()
