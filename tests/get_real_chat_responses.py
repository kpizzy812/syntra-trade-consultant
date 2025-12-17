"""
Скрипт для получения реальных ответов от Chat API
Используется для hardcode в LiveChatExamples компонент
"""

import asyncio
import aiohttp
import json
from typing import List, Dict

# API endpoint (на сервере это порт 8003)
API_URL = "http://31.13.208.58:8003"

# Вопросы для примеров
QUESTIONS = [
    "Дай полный технический анализ BTC прямо сейчас",
    "Какие альткоины стоит смотреть в этом цикле?",
    "Что сейчас с Fear & Greed индексом?",
    "Как правильно управлять рисками при трейдинге?",
    "Объясни как работают циклы в крипте и где мы сейчас?",
]

# Создаем тестового пользователя (нужно будет создать в БД или использовать существующего)
# Для этого нужно сначала получить initData через Telegram Web App


async def get_chat_response(session: aiohttp.ClientSession, question: str, auth_token: str = None) -> str:
    """
    Получить ответ от Chat API через SSE stream
    """
    url = f"{API_URL}/api/chat/stream"

    headers = {
        "Content-Type": "application/json",
    }

    if auth_token:
        headers["Authorization"] = f"tma {auth_token}"

    data = {
        "message": question,
        "context": None,
        "image": None
    }

    full_response = ""

    try:
        async with session.post(url, json=data, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"❌ Error {response.status}: {error_text}")
                return f"Error: {response.status}"

            # Читаем SSE stream
            async for line in response.content:
                line_str = line.decode('utf-8').strip()

                if line_str.startswith('data: '):
                    try:
                        data_json = json.loads(line_str[6:])

                        if data_json.get('type') == 'token':
                            full_response += data_json.get('content', '')
                        elif data_json.get('type') == 'done':
                            break
                        elif data_json.get('type') == 'error':
                            print(f"❌ API Error: {data_json.get('error')}")
                            return f"Error: {data_json.get('error')}"
                    except json.JSONDecodeError:
                        pass

    except Exception as e:
        print(f"❌ Exception: {e}")
        return f"Exception: {e}"

    return full_response


async def main():
    """
    Основная функция - получаем ответы на все вопросы
    """
    print("🚀 Запускаем получение реальных ответов от Chat API...\n")

    # TODO: Нужно получить реальный auth token
    # Для теста попробуем без авторизации (может быть есть публичный endpoint)
    auth_token = None

    async with aiohttp.ClientSession() as session:
        responses = []

        for i, question in enumerate(QUESTIONS, 1):
            print(f"📝 Вопрос {i}/{len(QUESTIONS)}: {question}")
            print("⏳ Получаем ответ...")

            response = await get_chat_response(session, question, auth_token)

            responses.append({
                'question': question,
                'response': response
            })

            print(f"✅ Получен ответ ({len(response)} символов)")
            print(f"📄 Первые 200 символов: {response[:200]}...\n")
            print("-" * 80 + "\n")

        # Сохраняем результаты в файл
        output_file = "/Users/a1/Projects/Syntra Trade Consultant/docs/CHAT_API_RESPONSES.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(responses, f, ensure_ascii=False, indent=2)

        print(f"💾 Результаты сохранены в: {output_file}")

        # Выводим результаты в консоль
        print("\n" + "=" * 80)
        print("РЕЗУЛЬТАТЫ:")
        print("=" * 80 + "\n")

        for i, item in enumerate(responses, 1):
            print(f"\n{'=' * 80}")
            print(f"ВОПРОС {i}: {item['question']}")
            print(f"{'=' * 80}")
            print(item['response'])
            print()


if __name__ == "__main__":
    asyncio.run(main())
