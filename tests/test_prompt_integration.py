"""
Тест интеграции новой архитектуры промптов
"""
import sys
sys.path.insert(0, '/Users/a1/Projects/Syntra Trade Consultant')

from config.prompts import (
    SYNTRA_CORE_PROMPT,
    get_system_prompt,
    get_few_shot_examples,
    FEW_SHOT_EXAMPLES
)
from config.prompt_selector import (
    get_system_prompt as get_system_prompt_selector,
    get_few_shot_examples as get_few_shot_examples_selector,
)


def test_core_prompt():
    """Тест базового промпта"""
    print("🧪 ТЕСТ 1: SYNTRA_CORE_PROMPT")
    print("=" * 80)
    print(f"  Длина: {len(SYNTRA_CORE_PROMPT)} символов")

    # Проверка на наличие секции КАТЕГОРИИ РЫНКА
    has_categories = "КАТЕГОРИИ РЫНКА" in SYNTRA_CORE_PROMPT
    has_l2 = "Layer-2" in SYNTRA_CORE_PROMPT and "Arbitrum" in SYNTRA_CORE_PROMPT
    has_warning = "НИКОГДА не подменяй L2" in SYNTRA_CORE_PROMPT

    print(f"  Есть секция 'КАТЕГОРИИ РЫНКА': {has_categories} {'✓' if has_categories else '✗'}")
    print(f"  Есть определение L2: {has_l2} {'✓' if has_l2 else '✗'}")
    print(f"  Есть предупреждение о подмене: {has_warning} {'✓' if has_warning else '✗'}")
    print()


def test_system_prompt_modes():
    """Тест промптов в разных режимах"""
    print("🧪 ТЕСТ 2: get_system_prompt() в разных режимах")
    print("=" * 80)

    for mode in ["soft", "medium", "hard"]:
        prompt = get_system_prompt(mode)
        print(f"  {mode}: {len(prompt)} символов", end="")

        # Проверяем что категории есть в промпте
        has_categories = "КАТЕГОРИИ РЫНКА" in prompt
        print(f" | Категории: {'✓' if has_categories else '✗'}")

    print()


def test_few_shot_examples():
    """Тест few-shot примеров"""
    print("🧪 ТЕСТ 3: Few-shot примеры")
    print("=" * 80)

    for mode in ["soft", "medium", "hard"]:
        examples = get_few_shot_examples(mode)
        print(f"  {mode}: {len(examples)} примеров", end="")

        # Проверяем структуру
        if examples:
            has_structure = all(
                "role" in ex and "content" in ex
                for ex in examples
            )
            print(f" | Структура: {'✓' if has_structure else '✗'}")
        else:
            print(" | Пусто")

    print()


def test_prompt_selector():
    """Тест интеграции через prompt_selector"""
    print("🧪 ТЕСТ 4: Интеграция через prompt_selector")
    print("=" * 80)

    # Тест RU
    prompt_ru = get_system_prompt_selector(language="ru", mode="medium")
    examples_ru = get_few_shot_examples_selector(language="ru", mode="medium")

    print(f"  RU prompt: {len(prompt_ru)} символов")
    print(f"  RU examples: {len(examples_ru)} примеров")

    # Проверяем что категории есть
    has_categories = "КАТЕГОРИИ РЫНКА" in prompt_ru
    print(f"  Категории в RU prompt: {'✓' if has_categories else '✗'}")

    # Тест EN (должен вернуть старый промпт без категорий)
    prompt_en = get_system_prompt_selector(language="en", mode="medium")
    examples_en = get_few_shot_examples_selector(language="en", mode="medium")

    print(f"  EN prompt: {len(prompt_en)} символов")
    print(f"  EN examples: {len(examples_en)} примеров")

    print()


def test_message_structure():
    """Тест структуры messages[] для OpenAI"""
    print("🧪 ТЕСТ 5: Структура messages[] для OpenAI API")
    print("=" * 80)

    # Симулируем структуру из openai_service.py
    system_prompt = get_system_prompt("medium")
    few_shot = get_few_shot_examples("medium")

    messages = [
        {"role": "system", "content": system_prompt}
    ]
    messages.extend(few_shot)

    # Добавляем тестовое сообщение пользователя
    messages.append({"role": "user", "content": "Какой L2 перспективнее для докупок?"})

    print(f"  Всего сообщений: {len(messages)}")
    print(f"  Структура:")
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content_len = len(msg.get("content", ""))
        print(f"    {i+1}. {role}: {content_len} символов")

    print()

    # Проверяем что system prompt идёт первым
    if messages[0]["role"] == "system":
        print("  ✓ System prompt идёт первым (для кеширования)")
    else:
        print("  ✗ System prompt НЕ идёт первым!")

    # Проверяем что few-shot после system
    if messages[1]["role"] in ["user", "assistant"]:
        print("  ✓ Few-shot примеры после system prompt")
    else:
        print("  ✗ Few-shot примеры НЕ после system prompt!")

    print()


def test_category_recognition():
    """Тест распознавания категорий в промпте"""
    print("🧪 ТЕСТ 6: Распознавание категорий")
    print("=" * 80)

    prompt = get_system_prompt("medium")

    categories = {
        "Layer-2 (L2)": ["Arbitrum", "Optimism", "zkSync", "Mantle"],
        "Layer-1 (L1)": ["BTC", "ETH", "SOL", "BNB"],
        "DeFi": ["AAVE", "UNI", "SUSHI", "CRV"],
        "Мемкоины": ["DOGE", "SHIB", "PEPE"],
        "AI-токены": ["FET", "AGIX", "OCEAN", "TAO"],
        "GameFi": ["AXS", "GALA", "SAND", "MANA"],
    }

    for category, tokens in categories.items():
        found = any(token in prompt for token in tokens)
        print(f"  {category}: {'✓' if found else '✗'}")

    # Проверка критичного правила
    has_no_substitution = "НИКОГДА не подменяй" in prompt
    print(f"\n  Правило 'НЕ подменяй категории': {'✓' if has_no_substitution else '✗'}")

    print()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("  ТЕСТЫ ИНТЕГРАЦИИ НОВОЙ АРХИТЕКТУРЫ ПРОМПТОВ")
    print("="*80 + "\n")

    test_core_prompt()
    test_system_prompt_modes()
    test_few_shot_examples()
    test_prompt_selector()
    test_message_structure()
    test_category_recognition()

    print("="*80)
    print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
    print("="*80)
