# Интеграция множественных чатов (GPT-style)

**Дата:** 2025-01-25
**Статус:** ✅ Готово и протестировано

## Что сделано

### 1. API Client (`frontend/shared/api/client.ts`)

Добавлены методы для управления чатами:

```typescript
api.chats = {
  listChats(limit, offset)      // Получить список чатов
  createChat(title)              // Создать новый чат
  getChat(chatId)                // Получить чат по ID
  getChatMessages(chatId, limit) // Получить сообщения чата
  renameChat(chatId, title)      // Переименовать чат
  deleteChat(chatId)             // Удалить чат
  getDefaultChat()               // Получить/создать дефолтный чат
}
```

### 2. Sidebar в GPT-стиле (`frontend/components/layout/Sidebar.tsx`)

**Основные фичи:**

- ✅ **Чаты сверху** - основной фокус интерфейса
- ✅ **Кнопка "New Chat"** - на видном месте
- ✅ **3 последних чата** - быстрый доступ
- ✅ **"Show all chats"** - раскрытие полного списка
- ✅ **Навигация внизу** - Home, Profile, Referral
- ✅ **Сворачивается до иконок** - экономия места (w-20 → w-64)
- ✅ **Hover actions** - удаление чатов при наведении
- ✅ **Адаптивность** - чаты показываются только на `/chat`

**Структура:**

```
┌─────────────────────┐
│ Logo + Collapse Btn │ ← Header
├─────────────────────┤
│ [+ New Chat]        │ ← Кнопка создания
├─────────────────────┤
│ 💬 Bitcoin анализ   │
│ 💬 ETH predictions  │ ← 3 последних чата
│ 💬 Market overview  │
│ Show all chats →    │ ← Раскрыть всё
├─────────────────────┤
│ 🏠 Home             │
│ 👤 Profile          │ ← Навигация
│ 🎁 Referral         │
├─────────────────────┤
│ FREE | 5/10 today   │ ← Инфо о юзере
└─────────────────────┘
```

### 3. Chat Page обновлен (`frontend/app/chat/page.tsx`)

**Добавлено:**

```typescript
// URL параметр для выбора чата
/chat?chat_id=123

// State для текущего чата
const [currentChatId, setCurrentChatId] = useState<number | null>(null);
const [isLoadingHistory, setIsLoadingHistory] = useState(false);

// Загрузка истории при смене чата
useEffect(() => {
  const chatIdParam = searchParams.get('chat_id');
  if (chatIdParam) {
    const chatId = parseInt(chatIdParam);
    setCurrentChatId(chatId);
    loadChatHistory(chatId);
  }
}, [searchParams]);

// Передача chat_id в API
await api.chat.streamMessage(
  content,
  onToken,
  onError,
  onDone,
  image,
  currentChatId || undefined  // ← Новый параметр
);
```

**Индикатор загрузки:**
- Показывается spinner при загрузке истории чата

### 4. Backend готов (из предыдущей сессии)

- ✅ API endpoints: `/api/chats` (CRUD операции)
- ✅ Database models: `Chat`, `ChatMessage`
- ✅ Auto-title generation: GPT-4o-mini генерирует названия
- ✅ Tier-aware memory: FREE/BASIC/PREMIUM/VIP лимиты

## Как работает

### Создание нового чата

1. Пользователь нажимает **"New Chat"** в сайдбаре
2. `api.chats.createChat()` создает чат на backend
3. Редирект на `/chat?chat_id=<новый_id>`
4. Показываются initial messages (пустой чат)

### Переключение между чатами

1. Клик на чат в сайдбаре
2. Редирект на `/chat?chat_id=<id>`
3. `loadChatHistory(id)` загружает историю
4. Сообщения отображаются в MessageList

### Отправка сообщения

1. User вводит сообщение
2. `handleSendMessage()` передает `currentChatId` в API
3. Backend сохраняет в нужный чат
4. Streaming response отображается в реальном времени

### Удаление чата

1. Hover на чат → появляется кнопка удаления
2. Confirm dialog
3. `api.chats.deleteChat(id)` удаляет чат
4. Список обновляется

## Архитектура

```
Frontend (Next.js)
├── components/layout/Sidebar.tsx
│   ├── Chats list (3 recent + show all)
│   ├── New Chat button
│   ├── Navigation (Home, Profile, Referral)
│   └── User info
│
├── app/chat/page.tsx
│   ├── currentChatId state
│   ├── loadChatHistory(chatId)
│   ├── handleSendMessage(content, chat_id)
│   └── Loading indicator
│
└── shared/api/client.ts
    └── api.chats.* methods

Backend (FastAPI)
├── src/api/chats.py
│   ├── GET /api/chats (list)
│   ├── POST /api/chats (create)
│   ├── GET /api/chats/{id} (get)
│   ├── GET /api/chats/{id}/messages (messages)
│   ├── PUT /api/chats/{id}/title (rename)
│   └── DELETE /api/chats/{id} (delete)
│
├── src/api/chat.py
│   ├── POST /api/chat/stream (with chat_id)
│   └── Auto-title generation
│
└── src/database/models.py
    ├── Chat (id, user_id, title, ...)
    └── ChatMessage (id, chat_id, role, content, ...)
```

## UX Features

### Desktop (lg+)
- **Sidebar всегда видим** - GPT-style
- **Сворачивается** - кнопка в header (w-64 → w-20)
- **Чаты только на /chat** - на других страницах просто навигация
- **Smooth animations** - framer-motion transitions

### Mobile (< lg)
- **TabBar внизу** - стандартная навигация
- **Sidebar скрыт** - используется только на desktop
- **Full screen chat** - максимум места для сообщений

## Следующие шаги (опционально)

1. **SVG Icons** (UltraThink-style)
   - Заменить emoji на премиальные SVG иконки
   - Добавить glow effects

2. **Search в чатах**
   - Поиск по названиям и содержимому
   - Фильтрация по датам

3. **Группировка чатов**
   - Today / Yesterday / Last 7 days / Older
   - Collapsible секции

4. **Keyboard shortcuts**
   - `Cmd+N` - новый чат
   - `Cmd+K` - поиск чатов
   - `Cmd+[` / `Cmd+]` - навигация между чатами

5. **Chat export**
   - Экспорт истории в Markdown/PDF
   - Share chat link

## Тестирование

✅ **Build прошел успешно** - `npm run build`
✅ **TypeScript** - нет ошибок
✅ **API endpoints** - все работают
✅ **Chat создание/удаление** - работает
✅ **History loading** - работает
✅ **Sidebar collapse** - работает

## Файлы изменены

### Frontend:
- ✅ `frontend/shared/api/client.ts` - API методы для чатов
- ✅ `frontend/components/layout/Sidebar.tsx` - GPT-style sidebar
- ✅ `frontend/app/chat/page.tsx` - множественные чаты
- ✅ `frontend/components/chat/ChatSidebar.tsx` - standalone компонент (не используется)

### Backend (из предыдущей сессии):
- ✅ `src/api/chats.py` - CRUD endpoints
- ✅ `src/api/chat.py` - обновлен для chat_id
- ✅ `src/api/router.py` - подключен chats router
- ✅ `src/database/models.py` - Chat, ChatMessage models
- ✅ `src/database/crud.py` - функции для чатов
- ✅ `src/services/openai_service.py` - поддержка chat_id

---

**Готово к продакшну!** 🚀
