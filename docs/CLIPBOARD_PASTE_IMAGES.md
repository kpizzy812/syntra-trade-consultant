# Clipboard Paste Images Feature

## Описание

Добавлена поддержка вставки изображений из буфера обмена в чат через **Cmd+V** (Mac) / **Ctrl+V** (Windows/Android).

## Реализация

### Технические детали

- **Файл**: [frontend/components/chat/ChatInput.tsx](../frontend/components/chat/ChatInput.tsx)
- **API**: Clipboard API (`ClipboardEvent.clipboardData.items`)
- **Браузерная поддержка**: Chrome 66+, Edge 79+, Firefox 63+, Safari 13.1+

### Обработчик события

```typescript
const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
  const items = e.clipboardData?.items;
  if (!items) return;

  // Поиск изображения в clipboard
  for (let i = 0; i < items.length; i++) {
    const item = items[i];

    if (item.type.startsWith('image/')) {
      e.preventDefault(); // Предотвращаем стандартное поведение для изображений

      const file = item.getAsFile();
      // Валидация размера (макс 10MB)
      // Конвертация в base64
      // Установка превью
      // PostHog аналитика
    }
  }
};
```

### Ограничения

- **Максимальный размер**: 10MB
- **Поддерживаемые форматы**: Все image/* (PNG, JPEG, GIF, WebP и т.д.)
- **Количество**: Обрабатывается только первое изображение из буфера

## Использование

### Desktop (Web)
1. Скопируйте изображение (правый клик → Copy Image)
2. Откройте чат
3. Нажмите **Cmd+V** (Mac) или **Ctrl+V** (Windows) в поле ввода
4. Изображение появится в превью над инпутом

### Mobile (Telegram Mini App)
1. Скопируйте изображение из галереи или другого приложения
2. Откройте чат в Telegram Mini App
3. Нажмите и удерживайте поле ввода → **Paste**
4. Изображение появится в превью

## Аналитика

При вставке изображения отправляется PostHog event:

```typescript
posthog.capture('image_pasted', {
  tier: user.subscription?.tier || 'free',
  image_type: file.type,           // 'image/png', 'image/jpeg', etc.
  image_size: file.size,            // размер в байтах
  platform: 'miniapp',
});
```

## Источники

Реализация основана на современных веб-стандартах:

- [How to paste images | Clipboard | web.dev](https://web.dev/patterns/clipboard/paste-images)
- [Clipboard API - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard_API)
- [ClipboardEvent - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/ClipboardEvent)
- [TypeScript definition for onPaste React event](https://felixgerschau.com/react-typescript-onpaste-event-type/)

## UX улучшения

- ✅ Мгновенное превью вставленного изображения
- ✅ Тактильная вибрация при успешной вставке
- ✅ Валидация размера с понятным сообщением об ошибке
- ✅ Кнопка удаления превью (красный крестик)
- ✅ Поддержка как вставки, так и выбора через file picker

## Совместимость с существующим функционалом

Новый обработчик `onPaste` работает параллельно с существующей функцией прикрепления через кнопку "+":

- **Кнопка "+"**: Открывает системный file picker
- **Cmd+V / Ctrl+V**: Вставляет из буфера обмена

Оба способа используют одинаковую логику:
- Валидация размера (10MB)
- Конвертация в base64
- Отображение превью
- Отправка в API
