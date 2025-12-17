# coding: utf-8
"""
OpenAI API Service with streaming support and Vision capabilities
"""
import base64
import json
import logging  # Needed for tenacity before_sleep_log level constants
from typing import AsyncGenerator, Optional, List, Tuple, Dict, Any

import tiktoken
from openai import (
    AsyncOpenAI,
    BadRequestError,
    APIError,
    RateLimitError,
    APIConnectionError,
)
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from config.config import (
    OPENAI_API_KEY,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    ModelConfig,
    Pricing,
)
from config.limits import get_token_limits
from config.prompt_selector import (
    get_system_prompt,
    get_few_shot_examples,
    get_vision_analysis_prompt,
    get_enhanced_vision_prompt,
    get_coin_detection_prompt,
)
from src.database.crud import (
    add_chat_message,
    get_chat_history,
    track_cost,
    add_chat_message_to_chat,
    get_chat_messages,
)
from src.database.models import SubscriptionTier
from src.utils.vision_tokens import calculate_image_tokens
from src.services.crypto_tools import CRYPTO_TOOLS, execute_tool


from loguru import logger


class OpenAIService:
    """
    Service for interacting with OpenAI API

    Features:
    - Streaming responses
    - Automatic model routing (gpt-4o vs gpt-4o-mini)
    - Token counting and cost tracking
    - Chat history management
    - Error handling and retries
    """

    def __init__(self):
        """
        Initialize BOTH OpenAI and DeepSeek clients

        Client selection is now DYNAMIC based on user's subscription tier:
        - FREE/BASIC → DeepSeek (cheapest)
        - PREMIUM/VIP → OpenAI GPT-4o for complex queries

        This replaces the old global AI_PROVIDER setting.
        """
        # Initialize OpenAI client
        logger.info("🔧 Initializing OpenAI client (for GPT-4o, GPT-4o-mini, Vision)")
        self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        # Initialize DeepSeek client (OpenAI-compatible API)
        logger.info("🔧 Initializing DeepSeek client (for deepseek-chat)")
        self.deepseek_client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

        # Vision always uses OpenAI
        self.vision_client = self.openai_client

        # Tokenizer (same for all models)
        self.encoding = tiktoken.encoding_for_model("gpt-4o")

    def _get_client_for_model(self, model: str) -> AsyncOpenAI:
        """
        Get appropriate client for the specified model

        Args:
            model: Model name (e.g., "gpt-4o", "deepseek-chat")

        Returns:
            AsyncOpenAI client (either OpenAI or DeepSeek)
        """
        if "deepseek" in model.lower():
            return self.deepseek_client
        else:
            return self.openai_client

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))

    def select_model(self, user_message: str, history_tokens: int = 0, user_tier: str = "free") -> str:
        """
        Smart model selection based on TIER, message complexity and keywords

        🚨 CRITICAL: FREE and BASIC users ALWAYS get cheap models (no GPT-4o)!
        Only PREMIUM+ can get GPT-4o for complex queries.

        Args:
            user_message: User's message
            history_tokens: Tokens in chat history
            user_tier: User's subscription tier (free, basic, premium, vip)

        Returns:
            Model name based on AI_PROVIDER and tier:
            - OpenAI: "gpt-4o" or "gpt-4o-mini"
            - DeepSeek: "deepseek-chat" (same for both cases, no mini version)
        """
        from config.limits import get_model_config

        # Get model config for user's tier
        try:
            tier_enum = SubscriptionTier(user_tier)
        except ValueError:
            logger.warning(f"Invalid tier '{user_tier}', defaulting to FREE")
            tier_enum = SubscriptionTier.FREE

        model_config = get_model_config(tier_enum)

        # FREE and BASIC: ALWAYS use cheap primary model (gpt-4o-mini or deepseek)
        if user_tier in ["free", "basic"]:
            model = model_config["primary_model"]
            logger.info(
                f"Tier {user_tier.upper()}: Using primary model {model} (no routing)"
            )
            return model

        # PREMIUM and VIP: Smart routing (can use expensive model for complex tasks)
        if not model_config.get("use_advanced_routing", False):
            # If advanced routing disabled, use primary model
            model = model_config["primary_model"]
            logger.info(
                f"Tier {user_tier.upper()}: Using primary model {model} (routing disabled)"
            )
            return model

        # Advanced routing enabled: check complexity
        message_tokens = self.count_tokens(user_message)
        total_tokens = message_tokens + history_tokens

        # Keywords indicating complex analysis requiring main model
        complex_keywords = [
            "анализ",
            "стратегия",
            "прогноз",
            "технический",
            "фундаментальный",
            "analysis",
            "strategy",
            "forecast",
            "technical",
            "fundamental",
            "глубокий",
            "подробный",
            "детальный",
            "deep",
            "detailed",
            "сравни",
            "compare",
            "объясни сложно",
            "explain complex",
        ]

        message_lower = user_message.lower()
        has_complex_keywords = any(
            keyword in message_lower for keyword in complex_keywords
        )

        # Use reasoning model (expensive) if complex OR high token count
        if has_complex_keywords or total_tokens > ModelConfig.MODEL_ROUTING_THRESHOLD:
            model = model_config["reasoning_model"]  # gpt-4o for PREMIUM+
            logger.info(
                f"Tier {user_tier.upper()}: Using reasoning model {model} "
                f"(tokens: {total_tokens}, complex: {has_complex_keywords})"
            )
            return model
        else:
            model = model_config["primary_model"]  # gpt-4o-mini
            logger.info(
                f"Tier {user_tier.upper()}: Using primary model {model} (tokens: {total_tokens})"
            )
            return model

    async def get_context_messages(
        self,
        session: AsyncSession,
        user_id: int,
        current_message: str,
        user_language: str = "ru",
        user_tier: str = "free",
        chat_id: Optional[int] = None,
    ) -> List[ChatCompletionMessageParam]:
        """
        Build context messages from chat history (tier-aware)

        OpenAI Cached Prompts Optimization:
        - System prompt is placed FIRST (required for caching)
        - System prompt is compact (RU: ~1500 chars, EN: ~1100 chars)
        - Few-shot examples are added AFTER system prompt for tone training
        - OpenAI automatically caches system prompt, saving ~50% on input tokens
        - Cache TTL: 5-10 minutes (OpenAI manages automatically)

        Message Structure:
        [system_prompt] + [few_shot_examples] + [history] + [user_message]

        Tier-based History:
        - FREE: 0 messages (no memory)
        - BASIC: 5 messages
        - PREMIUM: 10 messages
        - VIP: 50 messages

        Args:
            session: Database session
            user_id: User's database ID (NOT Telegram ID)
            current_message: Current user message
            user_language: User's language ('ru' or 'en')
            user_tier: User's subscription tier (free, basic, premium, vip)
            chat_id: Optional chat ID for multiple chats support

        Returns:
            List of messages for OpenAI API
        """
        from config.limits import get_chat_history_limit

        # Get tier enum
        try:
            tier_enum = SubscriptionTier(user_tier)
        except ValueError:
            logger.warning(f"Invalid tier '{user_tier}', defaulting to FREE")
            tier_enum = SubscriptionTier.FREE

        # Get history limit for tier (0 for FREE = no memory)
        max_history = get_chat_history_limit(tier_enum)

        logger.info(
            f"User {user_id} tier={user_tier}: chat_history_limit={max_history} messages, chat_id={chat_id}"
        )

        # System prompt MUST be first for automatic caching
        # Auto-detect sarcasm mode from current message
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": get_system_prompt(
                    user_language, user_message=current_message, tier=tier_enum
                ),
            }
        ]

        # Add few-shot examples for tone training (AFTER system, BEFORE history)
        few_shot = get_few_shot_examples(
            user_language, user_message=current_message, tier=tier_enum
        )
        messages.extend(few_shot)

        # Get recent chat history (only if tier allows it)
        if max_history > 0:
            # If chat_id provided, use new chat system
            if chat_id:
                history = await get_chat_messages(session, chat_id, limit=max_history)
                logger.debug(f"Loaded {len(history)} messages from chat {chat_id}")
            else:
                # Fallback to old system for backward compatibility
                history = await get_chat_history(session, user_id, limit=max_history)
                logger.debug(f"Loaded {len(history)} messages from old chat_history")

            # Add history messages (oldest first)
            for msg in reversed(history):
                messages.append({"role": msg.role, "content": msg.content})
        else:
            logger.info(f"User {user_id} on FREE tier - no chat history loaded")

        # Add current message
        messages.append({"role": "user", "content": current_message})

        return messages

    async def stream_completion(
        self,
        session: AsyncSession,
        user_id: int,
        user_message: str,
        user_language: str = "ru",
        user_tier: str = "free",
        model: Optional[str] = None,
        use_tools: bool = True,
        chat_id: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from OpenAI with Function Calling support

        Args:
            session: Database session
            user_id: User's database ID (NOT Telegram ID)
            user_message: User's message
            user_language: User's language ('ru' or 'en')
            user_tier: User's subscription tier (free, basic, premium, vip)
            model: Model to use (auto-selected if None)
            use_tools: Enable Function Calling (crypto tools)
            chat_id: Optional chat ID for multiple chats support

        Yields:
            Text chunks from OpenAI
        """
        try:
            # Build context messages (tier-aware)
            messages = await self.get_context_messages(
                session, user_id, user_message, user_language, user_tier, chat_id
            )

            # Calculate history tokens
            history_text = "\n".join([m["content"] for m in messages[:-1]])
            history_tokens = self.count_tokens(history_text)

            # Select model if not provided (tier-aware routing)
            if model is None:
                model = self.select_model(user_message, history_tokens, user_tier)

            # Get token limits for user's tier
            try:
                tier_enum = SubscriptionTier(user_tier)
            except ValueError:
                logger.warning(f"Invalid tier '{user_tier}', defaulting to FREE")
                tier_enum = SubscriptionTier.FREE

            token_limits = get_token_limits(tier_enum)
            max_output = token_limits["max_output_tokens"]

            logger.info(
                f"User {user_id} tier={user_tier}: max_output_tokens={max_output}"
            )

            # Save user message to history (only for tiers with save_chat_history=True)
            from config.limits import should_save_chat_history

            if should_save_chat_history(tier_enum):
                if chat_id:
                    # Use new chat system
                    await add_chat_message_to_chat(
                        session, chat_id=chat_id, role="user", content=user_message
                    )
                    logger.debug(f"User message saved to chat {chat_id} for tier {user_tier}")
                else:
                    # Fallback to old system for backward compatibility
                    await add_chat_message(
                        session, user_id=user_id, role="user", content=user_message
                    )
                    logger.debug(f"User message saved to old history for tier {user_tier}")
            else:
                logger.debug(
                    f"User message NOT saved to history for tier {user_tier} (save_chat_history=False)"
                )

            # Create streaming completion with tools
            logger.info(
                f"Starting OpenAI stream for user {user_id} with model {model}, tools: {use_tools}"
            )

            # Build API call parameters
            # Reasoning models (o3, o4, gpt-5.x) require max_completion_tokens instead of max_tokens
            is_reasoning_model = any(
                x in model.lower() for x in ["o3-", "o4-", "gpt-5", "o1-"]
            )

            api_params = {
                "model": model,
                "messages": messages,
                "stream": True,
            }

            if is_reasoning_model:
                api_params["max_completion_tokens"] = max_output
                # Reasoning models don't support temperature
            else:
                api_params["max_tokens"] = max_output
                api_params["temperature"] = ModelConfig.DEFAULT_TEMPERATURE

            # Add tools if enabled
            if use_tools:
                api_params["tools"] = CRYPTO_TOOLS
                api_params["tool_choice"] = "auto"  # Let AI decide when to use tools

            # Select appropriate client based on model
            client = self._get_client_for_model(model)
            stream = await client.chat.completions.create(**api_params)

            full_response = ""
            input_tokens = 0
            output_tokens = 0
            tool_calls = []  # Accumulate tool calls
            current_tool_call = None

            # Stream response chunks
            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                delta = choice.delta

                # Handle tool calls
                if delta.tool_calls:
                    for tool_call_chunk in delta.tool_calls:
                        # Initialize new tool call
                        if tool_call_chunk.index is not None:
                            # Ensure we have enough space in tool_calls list
                            while len(tool_calls) <= tool_call_chunk.index:
                                tool_calls.append(
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                )
                            current_tool_call = tool_calls[tool_call_chunk.index]

                        # Accumulate tool call data
                        if tool_call_chunk.id:
                            current_tool_call["id"] = tool_call_chunk.id
                        if tool_call_chunk.function:
                            if tool_call_chunk.function.name:
                                current_tool_call["function"][
                                    "name"
                                ] += tool_call_chunk.function.name
                            if tool_call_chunk.function.arguments:
                                current_tool_call["function"][
                                    "arguments"
                                ] += tool_call_chunk.function.arguments

                # Handle regular content
                elif delta.content:
                    content = delta.content
                    full_response += content
                    yield content

                # Track token usage if available
                if hasattr(chunk, "usage") and chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens

            # If AI called tools, execute them and continue
            if tool_calls:
                logger.info(
                    f"AI called {len(tool_calls)} tools: {[tc['function']['name'] for tc in tool_calls]}"
                )

                # Add assistant message with tool calls to conversation
                messages.append(
                    {"role": "assistant", "tool_calls": tool_calls, "content": None}
                )

                # Execute each tool and add results to messages
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args_json = tool_call["function"]["arguments"]

                    try:
                        # Parse arguments
                        tool_args = json.loads(tool_args_json)

                        # Execute tool (with tier gating!)
                        logger.info(
                            f"Executing tool: {tool_name} with args: {tool_args}, tier: {user_tier}"
                        )
                        tool_result = await execute_tool(tool_name, tool_args, user_tier)

                        # Add tool result to messages
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_name,
                                "content": tool_result,
                            }
                        )

                        logger.info(f"Tool {tool_name} executed successfully")

                    except json.JSONDecodeError as e:
                        logger.error(
                            f"Failed to parse tool arguments for {tool_name}: {e}"
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_name,
                                "content": json.dumps(
                                    {"success": False, "error": "Invalid arguments"}
                                ),
                            }
                        )

                # Make second API call with tool results
                logger.info("Making second API call with tool results...")

                api_params["messages"] = messages
                # Don't include tools in second call to avoid infinite loop
                api_params.pop("tools", None)
                api_params.pop("tool_choice", None)

                # Use same client for second call
                second_stream = await client.chat.completions.create(**api_params)

                # Stream final response
                async for chunk in second_stream:
                    choice = chunk.choices[0] if chunk.choices else None
                    if choice and choice.delta.content:
                        content = choice.delta.content
                        full_response += content
                        yield content

                    # Update token usage
                    if hasattr(chunk, "usage") and chunk.usage:
                        input_tokens += chunk.usage.prompt_tokens
                        output_tokens += chunk.usage.completion_tokens

            # If no usage data, estimate tokens
            if input_tokens == 0:
                input_tokens = self.count_tokens(history_text + user_message)
                output_tokens = self.count_tokens(full_response)

            # Calculate cost
            cost = self.calculate_cost(model, input_tokens, output_tokens)

            # Save assistant response to history (only for tiers with save_chat_history=True)
            if should_save_chat_history(tier_enum):
                if chat_id:
                    # Use new chat system
                    await add_chat_message_to_chat(
                        session, chat_id=chat_id, role="assistant", content=full_response,
                        tokens_used=output_tokens, model=model
                    )
                    logger.debug(f"Assistant response saved to chat {chat_id} for tier {user_tier}")
                else:
                    # Fallback to old system for backward compatibility
                    await add_chat_message(
                        session, user_id=user_id, role="assistant", content=full_response
                    )
                    logger.debug(f"Assistant response saved to old history for tier {user_tier}")
            else:
                logger.debug(
                    f"Assistant response NOT saved to history for tier {user_tier} (save_chat_history=False)"
                )

            # Track cost
            await track_cost(
                session,
                user_id=user_id,
                service="openai",
                tokens=input_tokens + output_tokens,
                cost=cost,
                model=model,
            )

            logger.info(
                f"OpenAI stream completed for user {user_id}. "
                f"Tools used: {len(tool_calls)}, "
                f"Tokens: {input_tokens}+{output_tokens}={input_tokens+output_tokens}, "
                f"Cost: ${cost:.4f}"
            )

        except Exception as e:
            logger.exception(f"Error in OpenAI stream: {e}")
            # Let handler deal with error messages in user's language
            yield ""

    def calculate_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """
        Calculate cost for API call (supports both OpenAI and DeepSeek)

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # DeepSeek models
        if model in (ModelConfig.DEEPSEEK_CHAT, ModelConfig.DEEPSEEK_REASONER):
            # Use cache miss pricing (conservative estimate)
            # In reality, DeepSeek caches prompts automatically, reducing cost to $0.028/1M
            input_cost = (input_tokens / 1_000_000) * Pricing.DEEPSEEK_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.DEEPSEEK_OUTPUT

        # OpenAI GPT-5.1 (2025 flagship)
        elif model == ModelConfig.GPT_5_1:
            input_cost = (input_tokens / 1_000_000) * Pricing.GPT_5_1_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.GPT_5_1_OUTPUT

        # OpenAI GPT-5-mini
        elif model == ModelConfig.GPT_5_MINI:
            input_cost = (input_tokens / 1_000_000) * Pricing.GPT_5_MINI_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.GPT_5_MINI_OUTPUT

        # OpenAI GPT-4o
        elif model == ModelConfig.GPT_4O:
            input_cost = (input_tokens / 1_000_000) * Pricing.GPT_4O_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.GPT_4O_OUTPUT

        # OpenAI GPT-4o-mini
        elif model == ModelConfig.GPT_4O_MINI:
            input_cost = (input_tokens / 1_000_000) * Pricing.GPT_4O_MINI_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.GPT_4O_MINI_OUTPUT

        # OpenAI Reasoning models (o4-mini, o3-mini)
        elif model == ModelConfig.O4_MINI:
            input_cost = (input_tokens / 1_000_000) * Pricing.O4_MINI_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.O4_MINI_OUTPUT

        elif model == ModelConfig.O3_MINI:
            input_cost = (input_tokens / 1_000_000) * Pricing.O3_MINI_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.O3_MINI_OUTPUT

        else:
            logger.warning(f"Unknown model for cost calculation: {model}")
            input_cost = 0
            output_cost = 0

        return input_cost + output_cost

    @retry(
        retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def simple_completion(
        self,
        prompt: str,
        model: str = ModelConfig.GPT_4O_MINI,
        temperature: float = ModelConfig.DEFAULT_TEMPERATURE,
    ) -> str:
        """
        Simple non-streaming completion with automatic retries

        Retries up to 3 times with exponential backoff (2-10s) for:
        - APIError (OpenAI server errors)
        - RateLimitError (rate limit exceeded)
        - APIConnectionError (network issues)

        Args:
            prompt: Prompt text
            model: Model to use
            temperature: Temperature setting

        Returns:
            Response text
        """
        try:
            # Select appropriate client based on model
            client = self._get_client_for_model(model)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.exception(f"Error in simple completion: {e}")
            return ""

    async def structured_completion(
        self,
        prompt: str,
        json_schema: Dict,
        model: str = ModelConfig.GPT_4O,
        temperature: float | None = None,  # None = don't send (for reasoning models)
    ) -> Dict:
        """
        🎯 Structured completion с ГАРАНТИРОВАННЫМ валидным JSON

        Использует OpenAI Structured Outputs для гарантии:
        - Валидный JSON (не сломается при парсинге)
        - Все required поля присутствуют
        - Правильные типы данных
        - Enum values соблюдены

        Args:
            prompt: Prompt text
            json_schema: JSON Schema для response format
            model: Model to use (только gpt-4o / gpt-4o-mini поддерживают structured outputs)
            temperature: Temperature setting

        Returns:
            Parsed JSON dict (ГАРАНТИРОВАННО валидный!)

        Example:
            schema = {
                "name": "trading_scenarios",
                "schema": {
                    "type": "object",
                    "properties": {
                        "scenarios": {"type": "array", "items": {...}},
                        "market_summary": {"type": "string"}
                    },
                    "required": ["scenarios", "market_summary"]
                },
                "strict": True
            }
            result = await openai_service.structured_completion(prompt, schema)
        """
        try:
            # Только OpenAI поддерживает structured outputs (не DeepSeek)
            # Build params - temperature optional (reasoning models don't support it)
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": json_schema
                }
            }
            if temperature is not None:
                params["temperature"] = temperature

            response = await self.openai_client.chat.completions.create(**params)

            # Парсим JSON из ответа
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")

            return json.loads(content)

        except Exception as e:
            logger.exception(f"Error in structured completion: {e}")
            raise

    def encode_image(self, image_bytes: bytes) -> str:
        """
        Encode image bytes to base64 string

        Args:
            image_bytes: Image file content

        Returns:
            Base64 encoded string
        """
        return base64.b64encode(image_bytes).decode("utf-8")

    @retry(
        retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def detect_coin_from_image(
        self, image_bytes: bytes, user_language: str = "ru"
    ) -> Optional[str]:
        """
        Detect cryptocurrency name from chart image with automatic retries

        Retries up to 3 times for API errors.

        Args:
            image_bytes: Image file content
            user_language: User's language ('ru' or 'en')

        Returns:
            Detected coin name or None
        """
        try:
            base64_image = self.encode_image(image_bytes)

            response = await self.vision_client.chat.completions.create(
                model=ModelConfig.GPT_4O_MINI,  # Use mini for quick detection
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": get_coin_detection_prompt(user_language),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "low",  # Low detail is enough for coin detection
                                },
                            },
                        ],
                    }
                ],
                max_tokens=50,
                temperature=0.1,  # Low temperature for consistent results
            )

            coin_name = response.choices[0].message.content.strip()

            if coin_name and coin_name.lower() != "unknown":
                logger.info(f"Detected coin from image: {coin_name}")
                return coin_name

            return None

        except Exception as e:
            logger.warning(f"Error detecting coin from image: {e}")
            return None

    async def stream_image_analysis(
        self,
        session: AsyncSession,
        user_id: int,
        image_bytes: bytes,
        user_language: str = "ru",
        user_prompt: Optional[str] = None,
        detail: str = ModelConfig.VISION_DETAIL_LEVEL,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream image analysis using GPT-4o Vision with optional market data integration

        Args:
            session: Database session
            user_id: User's database ID (NOT Telegram ID)
            image_bytes: Image file content
            user_language: User's language ('ru' or 'en')
            user_prompt: Optional custom prompt (uses default chart analysis if None)
            detail: Detail level - "low", "high", or "auto"
            market_data: Optional market data from CoinGecko API

        Yields:
            Text chunks from OpenAI Vision API

        Raises:
            BadRequestError: If image is invalid or too large
        """
        # Build prompt based on available data
        if user_prompt is None:
            if market_data:
                # Enhanced prompt with market data
                user_prompt = get_enhanced_vision_prompt(
                    user_language,
                    coin_name=market_data.get(
                        "name",
                        "криптовалюты" if user_language == "ru" else "cryptocurrency",
                    ),
                    current_price=market_data.get("current_price", 0),
                    change_24h=market_data.get("price_change_percentage_24h", 0),
                    volume_24h=market_data.get("total_volume"),
                    market_cap=market_data.get("market_cap"),
                )
            else:
                # Basic prompt without market data
                user_prompt = get_vision_analysis_prompt(user_language)

        try:
            # Encode image
            base64_image = self.encode_image(image_bytes)

            # Calculate image tokens BEFORE API call
            image_tokens = calculate_image_tokens(image_bytes, detail)
            prompt_tokens_estimate = self.count_tokens(user_prompt)
            total_input_tokens_estimate = image_tokens + prompt_tokens_estimate

            logger.info(
                f"Vision streaming analysis for user {user_id}: "
                f"Image tokens: {image_tokens}, "
                f"Prompt tokens: {prompt_tokens_estimate}, "
                f"Detail: {detail}"
            )

            # Build messages with system prompt for Syntra persona
            # For vision, use soft sarcasm mode by default (focus on analysis)
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": get_system_prompt(user_language, mode="soft")},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": detail,
                            },
                        },
                    ],
                },
            ]

            # Create streaming completion
            stream = await self.vision_client.chat.completions.create(
                model=ModelConfig.GPT_4O,  # Vision requires GPT-4o
                messages=messages,
                max_tokens=ModelConfig.MAX_TOKENS_VISION,
                temperature=ModelConfig.DEFAULT_TEMPERATURE,
                stream=True,
            )

            full_response = ""
            input_tokens = 0
            output_tokens = 0

            # Stream response chunks
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content

                # Track token usage if available
                if hasattr(chunk, "usage") and chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens

            # If no usage data, use estimates
            if input_tokens == 0:
                input_tokens = total_input_tokens_estimate
                output_tokens = self.count_tokens(full_response)

            # Calculate cost
            cost = self.calculate_vision_cost(input_tokens, output_tokens)

            # Track in database
            await track_cost(
                session,
                user_id=user_id,
                service="openai_vision",
                tokens=input_tokens + output_tokens,
                cost=cost,
                model=ModelConfig.GPT_4O,
            )

            logger.info(
                f"Vision streaming completed for user {user_id}. "
                f"Tokens: {input_tokens}+{output_tokens}={input_tokens+output_tokens}, "
                f"Cost: ${cost:.4f}"
            )

        except BadRequestError as e:
            logger.error(f"Vision API BadRequest: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error in vision streaming: {e}")
            raise

    @retry(
        retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def analyze_image(
        self,
        session: AsyncSession,
        user_id: int,
        image_bytes: bytes,
        user_language: str = "ru",
        user_prompt: Optional[str] = None,
        detail: str = ModelConfig.VISION_DETAIL_LEVEL,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Analyze image using GPT-4o Vision with automatic retries

        Retries up to 3 times with exponential backoff for API errors.
        BadRequestError (invalid image) is NOT retried.

        Args:
            session: Database session
            user_id: User's database ID (NOT Telegram ID)
            image_bytes: Image file content
            user_language: User's language ('ru' or 'en')
            user_prompt: Optional custom prompt (uses default chart analysis if None)
            detail: Detail level - "low", "high", or "auto"
            market_data: Optional market data from CoinGecko API

        Returns:
            Tuple of (analysis_text, stats_dict)
            stats_dict contains: tokens, cost, etc.

        Raises:
            BadRequestError: If image is invalid or too large
        """
        # Build prompt based on available data
        if user_prompt is None:
            if market_data:
                # Enhanced prompt with market data
                user_prompt = get_enhanced_vision_prompt(
                    user_language,
                    coin_name=market_data.get(
                        "name",
                        "криптовалюты" if user_language == "ru" else "cryptocurrency",
                    ),
                    current_price=market_data.get("current_price", 0),
                    change_24h=market_data.get("price_change_percentage_24h", 0),
                    volume_24h=market_data.get("total_volume"),
                    market_cap=market_data.get("market_cap"),
                )
            else:
                # Basic prompt without market data
                user_prompt = get_vision_analysis_prompt(user_language)

        try:
            # Encode image
            base64_image = self.encode_image(image_bytes)

            # Calculate image tokens BEFORE API call
            image_tokens = calculate_image_tokens(image_bytes, detail)
            prompt_tokens_estimate = self.count_tokens(user_prompt)
            total_input_tokens_estimate = image_tokens + prompt_tokens_estimate

            logger.info(
                f"Vision analysis for user {user_id}: "
                f"Image tokens: {image_tokens}, "
                f"Prompt tokens: {prompt_tokens_estimate}, "
                f"Detail: {detail}"
            )

            # Build messages with system prompt for Syntra persona
            # For vision, use soft sarcasm mode by default (focus on analysis)
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": get_system_prompt(user_language, mode="soft")},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": detail,
                            },
                        },
                    ],
                },
            ]

            # Call OpenAI Vision API
            response = await self.vision_client.chat.completions.create(
                model=ModelConfig.GPT_4O,  # Vision requires GPT-4o
                messages=messages,
                max_tokens=ModelConfig.MAX_TOKENS_VISION,
                temperature=ModelConfig.DEFAULT_TEMPERATURE,
            )

            # Extract response
            analysis = response.choices[0].message.content or ""

            # Get actual token usage from response
            usage = response.usage
            if usage:
                input_tokens = usage.prompt_tokens
                output_tokens = usage.completion_tokens
                total_tokens = usage.total_tokens
            else:
                # Fallback to estimates if usage not provided
                input_tokens = total_input_tokens_estimate
                output_tokens = self.count_tokens(analysis)
                total_tokens = input_tokens + output_tokens

            # Calculate cost
            cost = self.calculate_vision_cost(input_tokens, output_tokens)

            # Track in database
            await track_cost(
                session,
                user_id=user_id,
                service="openai_vision",
                tokens=input_tokens + output_tokens,
                cost=cost,
                model=ModelConfig.GPT_4O,
            )

            # Prepare stats
            stats = {
                "image_tokens": image_tokens,
                "prompt_tokens": prompt_tokens_estimate,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
                "detail": detail,
                "model": ModelConfig.GPT_4O,
            }

            logger.info(
                f"Vision analysis completed for user {user_id}. "
                f"Tokens: {input_tokens}+{output_tokens}={total_tokens}, "
                f"Cost: ${cost:.4f}"
            )

            return analysis, stats

        except BadRequestError as e:
            logger.error(f"Vision API BadRequest: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error in vision analysis: {e}")
            raise

    def calculate_vision_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for Vision API call

        Vision always uses OpenAI GPT-4o, regardless of AI_PROVIDER setting.

        Args:
            input_tokens: Input tokens (includes image tokens)
            output_tokens: Output tokens

        Returns:
            Cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * Pricing.GPT_4O_VISION_INPUT
        output_cost = (output_tokens / 1_000_000) * Pricing.GPT_4O_VISION_OUTPUT

        return input_cost + output_cost

    async def generate_chat_title(
        self, user_message: str, assistant_response: str, user_language: str = "ru"
    ) -> str:
        """
        Generate short chat title (3-5 words) from first message exchange

        Uses GPT-4o-mini for fast and cheap title generation.

        Args:
            user_message: User's first message
            assistant_response: AI's first response
            user_language: User's language ('ru' or 'en')

        Returns:
            Short title (3-5 words) summarizing the chat topic
        """
        try:
            # Build prompt for title generation
            if user_language == "ru":
                prompt = f"""Создай краткое название чата (3-5 слов) на основе этого диалога:

Пользователь: {user_message[:200]}
Ассистент: {assistant_response[:200]}

Требования:
- Только название, без кавычек и точки
- 3-5 слов максимум
- На русском языке
- Отражает тему разговора
- Без эмодзи

Примеры хороших названий:
- Анализ Bitcoin
- Сравнение ETH и SOL
- Прогноз криптовалют
- Технический анализ BTC

Название:"""
            else:
                prompt = f"""Create a short chat title (3-5 words) based on this dialogue:

User: {user_message[:200]}
Assistant: {assistant_response[:200]}

Requirements:
- Title only, no quotes or period
- 3-5 words maximum
- In English
- Reflects the conversation topic
- No emojis

Examples of good titles:
- Bitcoin Analysis
- ETH vs SOL Comparison
- Crypto Forecast
- BTC Technical Analysis

Title:"""

            # Generate title using GPT-4o-mini (cheap and fast)
            title = await self.simple_completion(
                prompt=prompt,
                model=ModelConfig.GPT_4O_MINI,
                temperature=0.7,
            )

            # Clean up title (remove quotes, extra spaces, etc.)
            title = title.strip().strip('"').strip("'").strip()

            # Limit length
            if len(title) > 60:
                title = title[:60].rsplit(" ", 1)[0] + "..."

            # Fallback if generation failed
            if not title or len(title) < 3:
                title = "New Chat" if user_language == "en" else "Новый чат"

            logger.info(f"Generated chat title: '{title}'")
            return title

        except Exception as e:
            logger.error(f"Failed to generate chat title: {e}")
            return "New Chat" if user_language == "en" else "Новый чат"
