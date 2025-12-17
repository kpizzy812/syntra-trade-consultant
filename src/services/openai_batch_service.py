# coding: utf-8
"""
OpenAI Batch API Service - для отложенных запросов с экономией 75%

Batch API позволяет:
- Отправлять множество запросов одним батчем
- Получать результаты через 24 часа
- Экономить 75% на стоимости API calls

Идеально для:
- Retention messages (персонализированные)
- Daily market summaries для всех юзеров
- Bulk analytics
- Content generation
"""
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import OPENAI_API_KEY, ModelConfig


from loguru import logger


class BatchStatus(str, Enum):
    """Batch job status"""

    VALIDATING = "validating"  # Проверка входных данных
    FAILED = "failed"  # Ошибка валидации
    IN_PROGRESS = "in_progress"  # В процессе обработки
    FINALIZING = "finalizing"  # Завершается
    COMPLETED = "completed"  # Готово
    EXPIRED = "expired"  # Истек срок (10 дней)
    CANCELLING = "cancelling"  # Отменяется
    CANCELLED = "cancelled"  # Отменено


class OpenAIBatchService:
    """
    Service for working with OpenAI Batch API

    Benefits:
    - 75% cost savings compared to real-time API
    - Process up to 50,000 requests per batch
    - 24-hour turnaround time
    - Same models as real-time API

    Limitations:
    - Not suitable for real-time responses
    - Results available after 24 hours
    - Maximum batch size: 50,000 requests
    - Batch expires after 10 days

    Use cases:
    - Retention messages (personalized)
    - Daily market summaries
    - Bulk user analytics
    - Content generation
    """

    def __init__(self):
        """Initialize Batch API client"""
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.batch_dir = Path("data/batches")
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    async def create_batch_request(
        self,
        requests: List[Dict[str, Any]],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Create and submit a batch request

        Args:
            requests: List of request objects, each with:
                {
                    "custom_id": "unique_id",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [...],
                        "max_tokens": 1000
                    }
                }
            description: Optional description of the batch
            metadata: Optional metadata (max 16 key-value pairs)

        Returns:
            Batch ID for tracking

        Example:
            requests = [
                {
                    "custom_id": "user_123_retention",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": "You are a crypto analyst"},
                            {"role": "user", "content": "Analyze Bitcoin"}
                        ],
                        "max_tokens": 500
                    }
                }
            ]
            batch_id = await service.create_batch_request(requests, "Daily summaries")
        """
        try:
            # Create JSONL file with requests
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            input_file_path = self.batch_dir / f"batch_input_{timestamp}.jsonl"

            with open(input_file_path, "w", encoding="utf-8") as f:
                for req in requests:
                    f.write(json.dumps(req, ensure_ascii=False) + "\n")

            logger.info(
                f"Created batch input file: {input_file_path} ({len(requests)} requests)"
            )

            # Upload file to OpenAI
            with open(input_file_path, "rb") as f:
                file_obj = await self.client.files.create(file=f, purpose="batch")

            logger.info(f"Uploaded batch file to OpenAI: {file_obj.id}")

            # Create batch job
            batch_params = {
                "input_file_id": file_obj.id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",  # Results within 24 hours
            }

            if metadata:
                batch_params["metadata"] = metadata

            batch = await self.client.batches.create(**batch_params)

            logger.info(
                f"Created batch job: {batch.id} "
                f"(status: {batch.status}, requests: {len(requests)})"
            )

            # Save batch metadata locally
            metadata_file = self.batch_dir / f"batch_{batch.id}_metadata.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "batch_id": batch.id,
                        "created_at": datetime.now(UTC).isoformat(),
                        "description": description,
                        "request_count": len(requests),
                        "input_file": str(input_file_path),
                        "status": batch.status,
                        "metadata": metadata,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            return batch.id

        except Exception as e:
            logger.exception(f"Error creating batch request: {e}")
            raise

    async def check_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Check status of a batch job

        Args:
            batch_id: Batch ID returned from create_batch_request

        Returns:
            Batch status dict with:
            {
                "id": "batch_xxx",
                "status": "completed",  # or "in_progress", "failed", etc.
                "request_counts": {
                    "total": 100,
                    "completed": 95,
                    "failed": 5
                },
                "created_at": 1234567890,
                "completed_at": 1234567890,
                "output_file_id": "file_xxx",
                "error_file_id": "file_xxx"
            }
        """
        try:
            batch = await self.client.batches.retrieve(batch_id)

            status_info = {
                "id": batch.id,
                "status": batch.status,
                "request_counts": {
                    "total": batch.request_counts.total,
                    "completed": batch.request_counts.completed,
                    "failed": batch.request_counts.failed,
                },
                "created_at": batch.created_at,
                "completed_at": batch.completed_at,
                "expires_at": batch.expires_at,
                "output_file_id": batch.output_file_id,
                "error_file_id": batch.error_file_id,
            }

            logger.info(
                f"Batch {batch_id} status: {batch.status} "
                f"({batch.request_counts.completed}/{batch.request_counts.total} completed)"
            )

            return status_info

        except Exception as e:
            logger.exception(f"Error checking batch status: {e}")
            raise

    async def get_batch_results(
        self, batch_id: str, include_errors: bool = True
    ) -> Dict[str, Any]:
        """
        Get results from completed batch

        Args:
            batch_id: Batch ID
            include_errors: Whether to include failed requests

        Returns:
            Dict with:
            {
                "status": "completed",
                "results": [
                    {
                        "custom_id": "user_123",
                        "response": {
                            "status_code": 200,
                            "body": {
                                "id": "chatcmpl-xxx",
                                "choices": [
                                    {
                                        "message": {
                                            "role": "assistant",
                                            "content": "Response text"
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ],
                "errors": [
                    {
                        "custom_id": "user_456",
                        "error": {
                            "message": "Error description"
                        }
                    }
                ]
            }
        """
        try:
            # Check batch status first
            batch = await self.client.batches.retrieve(batch_id)

            if batch.status != BatchStatus.COMPLETED:
                logger.warning(
                    f"Batch {batch_id} is not completed yet (status: {batch.status})"
                )
                return {"status": batch.status, "results": [], "errors": []}

            results = []
            errors = []

            # Download output file
            if batch.output_file_id:
                output_content = await self.client.files.content(batch.output_file_id)
                output_text = output_content.read().decode("utf-8")

                # Save to local file
                output_file = self.batch_dir / f"batch_{batch_id}_output.jsonl"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(output_text)

                # Parse results
                for line in output_text.strip().split("\n"):
                    if line:
                        result = json.loads(line)
                        results.append(result)

                logger.info(f"Downloaded {len(results)} results from batch {batch_id}")

            # Download error file if requested
            if include_errors and batch.error_file_id:
                error_content = await self.client.files.content(batch.error_file_id)
                error_text = error_content.read().decode("utf-8")

                # Save to local file
                error_file = self.batch_dir / f"batch_{batch_id}_errors.jsonl"
                with open(error_file, "w", encoding="utf-8") as f:
                    f.write(error_text)

                # Parse errors
                for line in error_text.strip().split("\n"):
                    if line:
                        error = json.loads(line)
                        errors.append(error)

                logger.info(f"Downloaded {len(errors)} errors from batch {batch_id}")

            return {"status": batch.status, "results": results, "errors": errors}

        except Exception as e:
            logger.exception(f"Error getting batch results: {e}")
            raise

    async def cancel_batch(self, batch_id: str) -> bool:
        """
        Cancel a running batch job

        Args:
            batch_id: Batch ID to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            batch = await self.client.batches.cancel(batch_id)
            logger.info(f"Cancelled batch {batch_id} (new status: {batch.status})")
            return True

        except Exception as e:
            logger.exception(f"Error cancelling batch: {e}")
            return False

    async def list_batches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent batch jobs

        Args:
            limit: Maximum number of batches to return

        Returns:
            List of batch info dicts
        """
        try:
            batches = await self.client.batches.list(limit=limit)

            batch_list = []
            for batch in batches.data:
                batch_list.append(
                    {
                        "id": batch.id,
                        "status": batch.status,
                        "created_at": batch.created_at,
                        "completed_at": batch.completed_at,
                        "request_counts": {
                            "total": batch.request_counts.total,
                            "completed": batch.request_counts.completed,
                            "failed": batch.request_counts.failed,
                        },
                    }
                )

            logger.info(f"Retrieved {len(batch_list)} recent batches")
            return batch_list

        except Exception as e:
            logger.exception(f"Error listing batches: {e}")
            raise

    # ========================================================================
    # HELPER METHODS FOR COMMON USE CASES
    # ========================================================================

    def create_retention_message_request(
        self, user_id: int, user_data: Dict[str, Any], message_type: str
    ) -> Dict[str, Any]:
        """
        Create a batch request for personalized retention message

        Args:
            user_id: User's ID
            user_data: User data (name, activity, preferences, etc.)
            message_type: Type of message ('7d_inactive', '14d_inactive', etc.)

        Returns:
            Request dict for batch API
        """
        user_name = user_data.get("first_name", "Friend")
        last_activity_days = user_data.get("days_inactive", 7)

        # Customize prompt based on message type
        if message_type == "7d_inactive":
            prompt = f"""Create a personalized retention message for {user_name} who hasn't used the crypto bot for {last_activity_days} days.

The message should:
- Be friendly and engaging (like Syntra's personality - professional crypto analyst with humor)
- Mention recent market moves (BTC, major news)
- Remind about available features
- Be concise (max 200 words)
- Include a call-to-action

Language: Russian
Style: Professional + light sarcasm (Syntra's style)
"""
        elif message_type == "14d_inactive":
            prompt = f"""Create a re-engagement message for {user_name} who hasn't used the crypto bot for {last_activity_days} days.

The message should:
- Be slightly more urgent but not pushy
- Highlight what they're missing (market opportunities)
- Emphasize the value of staying informed
- Be concise (max 200 words)

Language: Russian
Style: Syntra's style (smart, professional, light irony)
"""
        else:
            prompt = f"Create a retention message for user {user_name}"

        return {
            "custom_id": f"retention_{message_type}_user_{user_id}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": ModelConfig.GPT_4O_MINI,  # Use mini for retention (cheaper)
                "messages": [
                    {
                        "role": "system",
                        "content": "You are Syntra, a professional crypto AI analyst with a personality. Create engaging retention messages.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 300,
                "temperature": 0.8,  # More creative for engagement
            },
        }

    def create_market_summary_request(
        self, user_id: int, user_language: str = "ru"
    ) -> Dict[str, Any]:
        """
        Create a batch request for daily market summary

        Args:
            user_id: User's ID
            user_language: User's language ('ru' or 'en')

        Returns:
            Request dict for batch API
        """
        prompt = (
            "Создай краткую сводку крипторынка за последние 24 часа. "
            if user_language == "ru"
            else "Create a brief crypto market summary for the last 24 hours."
        )

        return {
            "custom_id": f"daily_summary_user_{user_id}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": ModelConfig.GPT_4O_MINI,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are Syntra. Create concise daily market summaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.7,
            },
        }


# Example usage
async def example_usage():
    """Example of how to use the Batch API service"""
    service = OpenAIBatchService()

    # Create batch requests
    requests = [
        service.create_retention_message_request(
            user_id=123,
            user_data={"first_name": "Алексей", "days_inactive": 7},
            message_type="7d_inactive",
        ),
        service.create_retention_message_request(
            user_id=456,
            user_data={"first_name": "Мария", "days_inactive": 14},
            message_type="14d_inactive",
        ),
    ]

    # Submit batch
    batch_id = await service.create_batch_request(
        requests, description="Daily retention messages"
    )

    logger.info(f"Batch created: {batch_id}")

    # Check status (do this after some time)
    # status = await service.check_batch_status(batch_id)
    # print(f"Status: {status}")

    # Get results (when completed)
    # results = await service.get_batch_results(batch_id)
    # for result in results["results"]:
    #     print(f"User {result['custom_id']}: {result['response']['body']['choices'][0]['message']['content']}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
