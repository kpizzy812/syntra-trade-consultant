"""
Генерация реальных примеров для landing page
Вызывает OpenAI service напрямую, минуя API
"""

import asyncio
import sys
import os
import json

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.openai_service import OpenAIService
from src.database.engine import get_session, init_db
from src.database.crud import get_or_create_user
from config.config import validate_config

# Вопросы для примеров
QUESTIONS = [
    "Дай полный технический анализ BTC прямо сейчас",
    "Какие альткоины стоит смотреть в этом цикле?",
    "Что сейчас с Fear & Greed индексом?",
]


async def generate_examples():
    """
    Генерация примеров через OpenAI service
    """
    print("🚀 Запускаем генерацию примеров для landing...\n")

    # Валидируем конфиг
    try:
        validate_config()
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return

    # Инициализируем БД
    try:
        await init_db()
        print("✅ База данных инициализирована\n")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return

    # Создаем OpenAI service
    try:
        openai_service = OpenAIService()
        print("✅ OpenAI service создан\n")
    except Exception as e:
        print(f"❌ Ошибка инициализации OpenAI service: {e}")
        return

    results = []

    # Создаем DB session
    async for session in get_session():
        # Создаем/получаем тестового пользователя
        try:
            user, created = await get_or_create_user(
                session,
                telegram_id=999999999,
                username="landing_generator",
                first_name="Landing",
                last_name="Generator",
                telegram_language="ru"
            )
            await session.commit()

            if created:
                print(f"✅ Создан тестовый пользователь (ID: {user.id})\n")
            else:
                print(f"✅ Используем существующего пользователя (ID: {user.id})\n")

        except Exception as e:
            print(f"❌ Ошибка создания пользователя: {e}")
            return

        # Генерируем ответы
        for i, question in enumerate(QUESTIONS, 1):
            print(f"\n{'='*80}")
            print(f"📝 Вопрос {i}/{len(QUESTIONS)}: {question}")
            print(f"{'='*80}")
            print("⏳ Генерируем ответ...\n")

            try:
                # Вызываем OpenAI напрямую
                full_response = ""

                async for chunk in openai_service.stream_completion(
                    session=session,
                    user_id=user.id,
                    user_message=question,
                    user_language="ru",
                    user_tier="premium",  # Premium для лучших ответов
                    use_tools=True
                ):
                    if chunk:
                        full_response += chunk
                        print(chunk, end='', flush=True)

                print("\n")
                print(f"✅ Получен ответ ({len(full_response)} символов)\n")

                results.append({
                    'question': question,
                    'response': full_response
                })

            except Exception as e:
                print(f"❌ Ошибка при генерации: {e}\n")
                import traceback
                traceback.print_exc()
                results.append({
                    'question': question,
                    'response': f"Error: {str(e)}"
                })

        break  # Выходим после первой итерации

    # Сохраняем результаты
    print(f"\n{'='*80}")
    print("💾 РЕЗУЛЬТАТЫ:")
    print(f"{'='*80}\n")

    for i, result in enumerate(results, 1):
        print(f"\n--- Пример {i} ---")
        print(f"Вопрос: {result['question']}")
        preview = result['response'][:300] if len(result['response']) > 300 else result['response']
        print(f"Ответ:\n{preview}...\n")

    # Сохраняем в файл
    output_file = "docs/LANDING_CHAT_EXAMPLES.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Результаты сохранены в: {output_file}")


if __name__ == "__main__":
    asyncio.run(generate_examples())
