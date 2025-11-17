# coding: utf-8
"""
OpenAI API Service with streaming support and Vision capabilities
"""
import base64
import json
import logging
from typing import AsyncGenerator, Optional, List, Tuple, Dict, Any
from datetime import datetime

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

from config.config import OPENAI_API_KEY, ModelConfig, Pricing
from config.prompt_selector import (
    get_system_prompt,
    get_vision_analysis_prompt,
    get_enhanced_vision_prompt,
    get_coin_detection_prompt,
)
from src.database.crud import add_chat_message, get_chat_history, track_cost
from src.utils.vision_tokens import calculate_image_tokens, estimate_vision_cost
from src.services.crypto_tools import CRYPTO_TOOLS, execute_tool


logger = logging.getLogger(__name__)


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
        """Initialize OpenAI client"""
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.encoding = tiktoken.encoding_for_model("gpt-4o")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))

    def select_model(self, user_message: str, history_tokens: int = 0) -> str:
        """
        Smart model selection based on message complexity and keywords

        Args:
            user_message: User's message
            history_tokens: Tokens in chat history

        Returns:
            Model name (gpt-4o or gpt-4o-mini)
        """
        message_tokens = self.count_tokens(user_message)
        total_tokens = message_tokens + history_tokens

        # Keywords indicating complex analysis requiring GPT-4o
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

        # Use GPT-4o if:
        # 1. Message has complex keywords, OR
        # 2. Total tokens exceed threshold
        if has_complex_keywords or total_tokens > ModelConfig.MODEL_ROUTING_THRESHOLD:
            logger.info(
                f"Using GPT-4O (tokens: {total_tokens}, complex: {has_complex_keywords})"
            )
            return ModelConfig.GPT_4O
        else:
            logger.info(f"Using GPT-4O-MINI (tokens: {total_tokens})")
            return ModelConfig.GPT_4O_MINI

    async def get_context_messages(
        self,
        session: AsyncSession,
        user_id: int,
        current_message: str,
        user_language: str = "ru",
        max_history: int = 5,
    ) -> List[ChatCompletionMessageParam]:
        """
        Build context messages from chat history

        Args:
            session: Database session
            user_id: User's database ID (NOT Telegram ID)
            current_message: Current user message
            user_language: User's language ('ru' or 'en')
            max_history: Maximum number of history messages to include

        Returns:
            List of messages for OpenAI API
        """
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": get_system_prompt(user_language)}
        ]

        # Get recent chat history
        history = await get_chat_history(session, user_id, limit=max_history)

        # Add history messages (oldest first)
        for msg in reversed(history):
            messages.append({"role": msg.role, "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": current_message})

        return messages

    async def stream_completion(
        self,
        session: AsyncSession,
        user_id: int,
        user_message: str,
        user_language: str = "ru",
        model: Optional[str] = None,
        use_tools: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from OpenAI with Function Calling support

        Args:
            session: Database session
            user_id: User's database ID (NOT Telegram ID)
            user_message: User's message
            user_language: User's language ('ru' or 'en')
            model: Model to use (auto-selected if None)
            use_tools: Enable Function Calling (crypto tools)

        Yields:
            Text chunks from OpenAI
        """
        try:
            # Build context messages
            messages = await self.get_context_messages(
                session, user_id, user_message, user_language
            )

            # Calculate history tokens
            history_text = "\n".join([m["content"] for m in messages[:-1]])
            history_tokens = self.count_tokens(history_text)

            # Select model if not provided
            if model is None:
                model = self.select_model(user_message, history_tokens)

            # Save user message to history
            await add_chat_message(
                session, user_id=user_id, role="user", content=user_message
            )

            # Create streaming completion with tools
            logger.info(
                f"Starting OpenAI stream for user {user_id} with model {model}, tools: {use_tools}"
            )

            # Build API call parameters
            api_params = {
                "model": model,
                "messages": messages,
                "max_tokens": ModelConfig.MAX_TOKENS_RESPONSE,
                "temperature": ModelConfig.DEFAULT_TEMPERATURE,
                "stream": True,
            }

            # Add tools if enabled
            if use_tools:
                api_params["tools"] = CRYPTO_TOOLS
                api_params["tool_choice"] = "auto"  # Let AI decide when to use tools

            stream = await self.client.chat.completions.create(**api_params)

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

                        # Execute tool
                        logger.info(
                            f"Executing tool: {tool_name} with args: {tool_args}"
                        )
                        tool_result = await execute_tool(tool_name, tool_args)

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

                second_stream = await self.client.chat.completions.create(**api_params)

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

            # Save assistant response to history
            await add_chat_message(
                session, user_id=user_id, role="assistant", content=full_response
            )

            # Track cost
            await track_cost(
                session,
                user_id=user_id,
                service="openai",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
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
        Calculate cost for API call

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        if model == ModelConfig.GPT_4O:
            input_cost = (input_tokens / 1_000_000) * Pricing.GPT_4O_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.GPT_4O_OUTPUT
        elif model == ModelConfig.GPT_4O_MINI:
            input_cost = (input_tokens / 1_000_000) * Pricing.GPT_4O_MINI_INPUT
            output_cost = (output_tokens / 1_000_000) * Pricing.GPT_4O_MINI_OUTPUT
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
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.exception(f"Error in simple completion: {e}")
            return ""

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

            response = await self.client.chat.completions.create(
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
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": get_system_prompt(user_language)},
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
            stream = await self.client.chat.completions.create(
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
                model=ModelConfig.GPT_4O,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
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
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": get_system_prompt(user_language)},
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
            response = await self.client.chat.completions.create(
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
                model=ModelConfig.GPT_4O,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
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

        Args:
            input_tokens: Input tokens (includes image tokens)
            output_tokens: Output tokens

        Returns:
            Cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * Pricing.GPT_4O_VISION_INPUT
        output_cost = (output_tokens / 1_000_000) * Pricing.GPT_4O_VISION_OUTPUT

        return input_cost + output_cost
