# coding: utf-8
"""
Extended OpenAI Service with Function Calling (Tools) Support

This extends the base OpenAI service with intelligent function calling capabilities.
AI decides when to call functions to get crypto data automatically.
"""
import json
import logging
from typing import AsyncGenerator, Optional, List, Dict, Any
from datetime import datetime

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import OPENAI_API_KEY, ModelConfig
from src.database.crud import add_chat_message, get_chat_history, track_cost
from src.services.openai_service import OpenAIService
from src.services.crypto_tools import CRYPTO_TOOLS, execute_tool


logger = logging.getLogger(__name__)


class OpenAIServiceWithTools(OpenAIService):
    """
    Extended OpenAI service with intelligent function calling

    Features:
    - AI automatically decides when to call crypto tools
    - Streaming responses with tool execution
    - Automatic data fetching (prices, news, comparisons)
    - Cost tracking for tool calls
    """

    async def stream_completion_with_tools(
        self,
        session: AsyncSession,
        user_id: int,
        user_message: str,
        user_language: str = "ru",
        model: Optional[str] = None,
        max_tool_iterations: int = 5,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion with intelligent function calling

        AI automatically decides:
        - When to fetch crypto prices
        - When to get news
        - When to compare coins
        - When to get market overview

        Args:
            session: Database session
            user_id: User's Telegram ID
            user_message: User's message
            user_language: User's language ('ru' or 'en')
            model: Model to use (auto-selected if None)
            max_tool_iterations: Max number of tool call iterations (prevent loops)

        Yields:
            Text chunks from AI response
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

            logger.info(
                f"Starting streaming with tools for user {user_id}. "
                f"Model: {model}, Tools: {len(CRYPTO_TOOLS)}"
            )

            # Track metrics
            total_input_tokens = 0
            total_output_tokens = 0
            tool_calls_made = []
            iteration = 0
            full_response = ""

            # Iterative loop for tool calling
            while iteration < max_tool_iterations:
                iteration += 1

                # Create streaming completion with tools
                stream = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=CRYPTO_TOOLS,
                    tool_choice="auto",  # Let AI decide when to use tools
                    max_tokens=ModelConfig.MAX_TOKENS_RESPONSE,
                    temperature=ModelConfig.DEFAULT_TEMPERATURE,
                    stream=True,
                )

                # Process stream
                current_tool_calls = {}
                current_content = ""

                async for chunk in stream:
                    # Handle content chunks
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        current_content += content
                        full_response += content
                        yield content

                    # Handle tool call chunks
                    if chunk.choices and chunk.choices[0].delta.tool_calls:
                        for tool_call in chunk.choices[0].delta.tool_calls:
                            idx = tool_call.index
                            if idx not in current_tool_calls:
                                current_tool_calls[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                }

                            if tool_call.id:
                                current_tool_calls[idx]["id"] = tool_call.id

                            if tool_call.function and tool_call.function.name:
                                current_tool_calls[idx][
                                    "name"
                                ] = tool_call.function.name

                            if tool_call.function and tool_call.function.arguments:
                                current_tool_calls[idx][
                                    "arguments"
                                ] += tool_call.function.arguments

                    # Track token usage
                    if hasattr(chunk, "usage") and chunk.usage:
                        total_input_tokens += chunk.usage.prompt_tokens
                        total_output_tokens += chunk.usage.completion_tokens

                # Check if AI made tool calls
                if current_tool_calls:
                    logger.info(f"AI requested {len(current_tool_calls)} tool calls")

                    # Execute tool calls
                    tool_results = []
                    for idx, tool_call in current_tool_calls.items():
                        tool_name = tool_call["name"]
                        tool_id = tool_call["id"]
                        arguments_str = tool_call["arguments"]

                        try:
                            # Parse arguments
                            arguments = json.loads(arguments_str)

                            # Execute tool
                            logger.info(f"Executing tool: {tool_name} with {arguments}")
                            result = await execute_tool(tool_name, arguments)

                            tool_results.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "content": result,
                                }
                            )

                            tool_calls_made.append(
                                {
                                    "name": tool_name,
                                    "arguments": arguments,
                                    "result_preview": result[:100],
                                }
                            )

                        except Exception as e:
                            logger.error(f"Error executing tool {tool_name}: {e}")
                            tool_results.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "content": json.dumps(
                                        {"success": False, "error": str(e)}
                                    ),
                                }
                            )

                    # Add assistant message with tool calls
                    messages.append(
                        {
                            "role": "assistant",
                            "content": current_content or None,
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": tc["arguments"],
                                    },
                                }
                                for tc in current_tool_calls.values()
                            ],
                        }
                    )

                    # Add tool results
                    messages.extend(tool_results)

                    # Continue to next iteration (AI will use tool results)
                    logger.info(
                        f"Tool calls completed. Continuing to iteration {iteration + 1}"
                    )
                    continue

                else:
                    # No more tool calls - AI provided final response
                    logger.info("No tool calls. Final response received.")
                    break

            # Estimate tokens if not provided
            if total_input_tokens == 0:
                total_input_tokens = self.count_tokens(history_text + user_message)
            if total_output_tokens == 0:
                total_output_tokens = self.count_tokens(full_response)

            # Calculate cost
            cost = self.calculate_cost(model, total_input_tokens, total_output_tokens)

            # Save assistant response to history
            await add_chat_message(
                session, user_id=user_id, role="assistant", content=full_response
            )

            # Track cost
            await track_cost(
                session,
                user_id=user_id,
                service="openai_tools",
                tokens=total_input_tokens + total_output_tokens,
                cost=cost,
                model=model,
            )

            logger.info(
                f"Streaming with tools completed for user {user_id}. "
                f"Tokens: {total_input_tokens}+{total_output_tokens}, "
                f"Cost: ${cost:.4f}, "
                f"Tools called: {len(tool_calls_made)}"
            )

        except Exception as e:
            logger.exception(f"Error in stream_completion_with_tools: {e}")
            yield ""


# Global instance
openai_service_with_tools = OpenAIServiceWithTools()
