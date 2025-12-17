"""
Упрощенная генерация примеров - использует существующего пользователя
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.openai_service import OpenAIService
from src.database.engine import get_session, init_db
from sqlalchemy import select
from src.database.models import User
from config.config import validate_config

QUESTIONS = [
    "Дай полный технический анализ BTC прямо сейчас",
    "Какие альткоины стоит смотреть в этом цикле?",
    "Что сейчас с Fear & Greed индексом?",
]


async def main():
    print("🚀 Генерация примеров для landing...\n")

    validate_config()
    await init_db()

    openai_service = OpenAIService()
    print("✅ OpenAI service готов\n")

    results = []

    async for session in get_session():
        # Получаем ЛЮБОГО существующего пользователя
        result = await session.execute(
            select(User).limit(1)
        )
        user = result.scalar_one_or_none()

        if not user:
            print("❌ Нет пользователей в БД")
            return

        print(f"✅ Используем пользователя: {user.username} (ID: {user.id})\n")

        for i, question in enumerate(QUESTIONS, 1):
            print(f"\n{'='*80}")
            print(f"📝 {i}/{len(QUESTIONS)}: {question}")
            print(f"{'='*80}\n")

            try:
                full_response = ""

                async for chunk in openai_service.stream_completion(
                    session=session,
                    user_id=user.id,
                    user_message=question,
                    user_language="ru",
                    user_tier="premium",
                    use_tools=True
                ):
                    if chunk:
                        full_response += chunk
                        print(chunk, end='', flush=True)

                print(f"\n\n✅ Готово ({len(full_response)} символов)\n")

                results.append({
                    'question': question,
                    'response': full_response
                })

            except Exception as e:
                print(f"\n❌ Ошибка: {e}\n")
                import traceback
                traceback.print_exc()
                results.append({
                    'question': question,
                    'response': f"Error: {str(e)}"
                })

        break

    # Сохраняем
    output_file = "docs/LANDING_CHAT_EXAMPLES.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Сохранено в: {output_file}\n")

    for i, r in enumerate(results, 1):
        print(f"\n--- Пример {i} ---")
        print(f"Q: {r['question']}")
        print(f"A: {r['response'][:200]}...\n")


if __name__ == "__main__":
    asyncio.run(main())
