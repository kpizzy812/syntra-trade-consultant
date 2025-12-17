# coding: utf-8
"""
Markdown to Telegram HTML converter

Telegram HTML поддерживает:
- <b>bold</b>
- <i>italic</i>
- <u>underline</u>
- <s>strikethrough</s>
- <code>inline code</code>
- <pre>code block</pre>
- <blockquote>цитата</blockquote>
- <a href="url">ссылка</a>

Преимущества HTML над Markdown:
- Более предсказуемое поведение
- Поддержка blockquote
- Не нужно экранировать символы
"""

import re


def convert_to_telegram_html(text: str) -> str:
    """
    Конвертирует Markdown в Telegram HTML формат

    ВАЖНО: Если AI уже сгенерировал HTML теги, они сохраняются.
    Конвертер обрабатывает только markdown синтаксис.

    Args:
        text: Текст с Markdown или HTML разметкой

    Returns:
        str: Текст с HTML разметкой для Telegram
    """
    if not text:
        return text

    result = text

    # Список допустимых HTML тегов Telegram
    ALLOWED_TAGS = ['b', 'i', 'u', 's', 'code', 'pre', 'blockquote', 'a']

    # 0. Защищаем существующие HTML теги перед экранированием
    # Используем уникальные плейсхолдеры без спецсимволов markdown
    placeholders = {}
    placeholder_counter = [0]

    def save_tag(match):
        tag = match.group(0)
        # Используем символы которые не конфликтуют с markdown: *, _, `, [
        key = f"\x00TAG{placeholder_counter[0]}\x00"
        placeholders[key] = tag
        placeholder_counter[0] += 1
        return key

    # Сохраняем открывающие и закрывающие теги
    tag_pattern = r'</?(?:' + '|'.join(ALLOWED_TAGS) + r')(?:\s[^>]*)?>'
    result = re.sub(tag_pattern, save_tag, result, flags=re.IGNORECASE)

    # 1. Экранируем оставшиеся HTML-специальные символы
    result = result.replace('&', '&amp;')
    result = result.replace('<', '&lt;')
    result = result.replace('>', '&gt;')

    # 2. Конвертируем ### заголовки в <b>жирный</b> с эмодзи
    result = re.sub(
        r'^###\s*(.+)$',
        r'📌 <b>\1</b>',
        result,
        flags=re.MULTILINE
    )

    # 3. Конвертируем ## заголовки
    result = re.sub(
        r'^##\s*(.+)$',
        r'📊 <b>\1</b>',
        result,
        flags=re.MULTILINE
    )

    # 4. Конвертируем # заголовки
    result = re.sub(
        r'^#\s*(.+)$',
        r'🎯 <b>\1</b>',
        result,
        flags=re.MULTILINE
    )

    # 5. Конвертируем **двойные звёздочки** в <b>
    result = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', result)

    # 6. Конвертируем _курсив_ в <i> (до одинарных звёздочек)
    result = re.sub(r'_([^_]+)_', r'<i>\1</i>', result)

    # 7. Конвертируем *одинарные звёздочки* в <b> (после курсива)
    result = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', result)

    # 8. Конвертируем ```code block``` в <pre>
    result = re.sub(r'```([^`]+)```', r'<pre>\1</pre>', result, flags=re.DOTALL)

    # 9. Конвертируем `код` в <code>
    result = re.sub(r'`([^`]+)`', r'<code>\1</code>', result)

    # 10. Конвертируем > цитаты в <blockquote>
    lines = result.split('\n')
    new_lines = []
    quote_buffer = []

    for line in lines:
        if line.startswith('&gt;'):
            quote_text = line[4:].strip() if len(line) > 4 else ''
            quote_buffer.append(quote_text)
        else:
            if quote_buffer:
                quote_content = '\n'.join(quote_buffer)
                new_lines.append(f'<blockquote>{quote_content}</blockquote>')
                quote_buffer = []
            new_lines.append(line)

    if quote_buffer:
        quote_content = '\n'.join(quote_buffer)
        new_lines.append(f'<blockquote>{quote_content}</blockquote>')

    result = '\n'.join(new_lines)

    # 11. Конвертируем [текст](url) в <a href="url">текст</a>
    result = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', result)

    # 12. Убираем горизонтальные линии
    result = re.sub(r'^-{3,}$', '', result, flags=re.MULTILINE)

    # 13. Убираем лишние пустые строки
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    # 14. Восстанавливаем сохранённые HTML теги
    for key, tag in placeholders.items():
        result = result.replace(key, tag)

    return result.strip()


# Алиас для обратной совместимости
def convert_to_telegram_markdown(text: str) -> str:
    """
    Алиас для convert_to_telegram_html
    Оставлен для обратной совместимости
    """
    return convert_to_telegram_html(text)
