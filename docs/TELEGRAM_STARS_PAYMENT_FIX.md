# Исправление оплаты через Telegram Stars в Mini App

## Дата: 2025-01-22

## Проблемы, которые были исправлены

### 1. ❌ Фейковый успех оплаты
**Проблема:** При нажатии кнопки оплаты показывался toast "успешно" и закрывалась модалка, хотя пользователь еще не оплатил инвойс.

**Причина:** Backend endpoint `/api/payment/stars/create-invoice` возвращал `success=true` сразу после создания инвойса, а frontend принимал это за успешную оплату.

**Решение:**
- Реализован метод `createInvoiceLink()` в backend для создания invoice URL
- Frontend теперь открывает инвойс через `WebApp.openInvoice()` API
- Обработка статусов оплаты через callback: `paid`, `cancelled`, `failed`, `pending`

### 2. ❌ Скидки за длительность не отображались
**Проблема:** При выборе 3 или 12 месяцев скидки 15% и 25% не показывались на кнопках выбора длительности, и неправильно рассчитывалась итоговая цена.

**Причина:**
- Функция `calculatePrice()` применяла только реферальную скидку
- В breakdown показывалась неправильная базовая цена
- На кнопках не было индикации скидок

**Решение:**
- Добавлены функции `getOriginalPrice()` (месячная цена × количество месяцев) и `getPriceWithDurationDiscount()`
- Правильный расчет: базовая цена → скидка за длительность → реферальная скидка → итого
- Добавлено отображение скидок на кнопках: "3 Months -15%", "12 Months -25%"

### 3. ❌ Лишние тоасты "открыть в Telegram"
**Проблема:** Показывались 2 тоаста с сообщением о необходимости открыть в Telegram, хотя оплата должна происходить внутри Mini App.

**Причина:** Старая логика пыталась отправить инвойс через бота вместо использования Mini App API.

**Решение:**
- Полностью переработана логика оплаты
- Используется `WebApp.openInvoice()` для открытия инвойса внутри приложения
- Убраны лишние тоасты
- Добавлена проверка доступности Mini App API

## Технические изменения

### Frontend

#### 1. Типы Telegram WebApp (`frontend/types/telegram.d.ts`)
```typescript
// Добавлен тип для статусов оплаты
export type InvoiceStatus = 'paid' | 'cancelled' | 'failed' | 'pending';

// Добавлен метод openInvoice
openInvoice(url: string, callback?: (status: InvoiceStatus) => void): void;
```

#### 2. Premium Purchase Modal (`frontend/components/modals/PremiumPurchaseModal.tsx`)

**Импорты:**
- Добавлен `useTelegram()` hook
- Добавлен импорт типа `InvoiceStatus`

**Расчет цен:**
```typescript
// Было: только referralDiscount
const calculatePrice = (basePrice: number): number => {
  const discountAmount = basePrice * (referralDiscount / 100);
  return basePrice - discountAmount;
};

// Стало: правильный учет всех скидок
const getOriginalPrice = (): number => {
  // Месячная цена × количество месяцев
  return selectedPlan.pricing.monthly * selectedDuration;
};

const getPriceWithDurationDiscount = (): number => {
  // Цена уже со скидкой за длительность
  if (selectedDuration === 1) return selectedPlan.pricing.monthly;
  if (selectedDuration === 3) return selectedPlan.pricing.quarterly; // -15%
  return selectedPlan.pricing.yearly; // -25%
};

// Применяем реферальную скидку к цене со скидкой за длительность
const finalPrice = calculatePrice(getPriceWithDurationDiscount());
```

**Обработка оплаты Telegram Stars:**
```typescript
if (paymentProvider === 'telegram_stars') {
  // Проверка доступности WebApp
  if (!webApp || !isMiniApp) {
    toast.error('Telegram Stars payment is only available in Mini App');
    return;
  }

  // Проверка наличия метода openInvoice
  if (!webApp.openInvoice) {
    toast.error('Please update Telegram to use in-app payments');
    return;
  }

  // Создание invoice link
  const response = await api.payment.createStarsInvoice({
    tier: selectedTier,
    duration_months: selectedDuration,
  });

  if (response.success && response.data?.invoice_url) {
    // Открытие инвойса в Mini App
    webApp.openInvoice(response.data.invoice_url, (status: InvoiceStatus) => {
      if (status === 'paid') {
        toast.success('Payment successful! Subscription activated 🎉');
        onSuccess?.(); // Обновить данные пользователя
        handleClose(); // Закрыть модалку
      } else if (status === 'cancelled') {
        toast.error('Payment cancelled');
      } else if (status === 'failed') {
        toast.error('Payment failed. Please try again.');
      } else if (status === 'pending') {
        toast.loading('Processing payment...', { duration: 3000 });
      }
    });
  }
}
```

**UI изменения:**
- Кнопки выбора длительности теперь показывают скидки
- Breakdown показывает правильную структуру цены:
  - Base Price (оригинальная цена)
  - Duration Discount (-15% или -25%)
  - Referral Discount (если есть)
  - Total

### Backend

#### 1. Telegram Stars Service (`src/services/telegram_stars_service.py`)

**Новый метод `create_invoice_link()`:**
```python
async def create_invoice_link(
    self,
    bot: Bot,
    user_id: int,
    tier: SubscriptionTier,
    duration_months: int,
    user_language: str = "ru",
) -> Optional[str]:
    """
    Create invoice link for Mini App payment

    Uses Bot API's createInvoiceLink method.
    The link can be opened in Mini App using WebApp.openInvoice(url).

    Returns:
        Invoice URL or None if failed
    """
    # Создание invoice через bot.create_invoice_link()
    invoice_url = await bot.create_invoice_link(
        title=title,
        description=description,
        prices=[LabeledPrice(label=tier_names[tier], amount=plan["stars"])],
        payload=payload,
        currency="XTR",  # Telegram Stars
        provider_token="",  # Пустая строка для Stars
        photo_url="https://i.ibb.co/ymkfW6vP/SYNTRABOT.png",
    )

    return invoice_url
```

#### 2. Payment API (`src/api/payment.py`)

**Обновлен endpoint `/api/payment/stars/create-invoice`:**
```python
@router.post("/stars/create-invoice", response_model=PaymentResponse)
async def create_stars_invoice(...):
    """
    Create Telegram Stars invoice link for Mini App payment

    Returns invoice URL to open in Mini App via WebApp.openInvoice()
    """
    # Создание invoice link
    invoice_url = await stars_service.create_invoice_link(
        bot=bot,
        user_id=user.id,
        tier=tier,
        duration_months=request.duration_months,
        user_language=user.language or "ru",
    )

    # Возврат invoice URL
    return PaymentResponse(
        success=True,
        message="Invoice link created successfully",
        data={
            "invoice_url": invoice_url,  # URL для openInvoice()
            "tier": tier.value,
            "duration_months": request.duration_months,
            "price_usd": plan["usd"],
            "price_stars": plan["stars"],
            "discount": plan["discount"],
        },
    )
```

## Как работает новая система оплаты

### Шаг 1: Пользователь выбирает тариф и длительность
- Отображаются скидки: 3 месяца (-15%), 12 месяцев (-25%)
- В breakdown показывается полная структура цены

### Шаг 2: Создание invoice link
1. Frontend вызывает `POST /api/payment/stars/create-invoice`
2. Backend создает invoice link через `bot.create_invoice_link()`
3. Возвращается URL инвойса

### Шаг 3: Открытие инвойса в Mini App
1. Frontend проверяет наличие `webApp.openInvoice`
2. Открывает инвойс: `webApp.openInvoice(invoice_url, callback)`
3. Telegram показывает нативное окно оплаты

### Шаг 4: Обработка результата
Callback получает статус:
- **`paid`** → Success toast, обновление данных, закрытие модалки
- **`cancelled`** → Пользователь закрыл инвойс
- **`failed`** → Ошибка оплаты
- **`pending`** → Обработка в процессе

### Шаг 5: Обработка successful_payment (backend)
После успешной оплаты Telegram отправляет webhook с `successful_payment`, который обрабатывается в `telegram_stars_service.process_successful_payment()` для активации подписки.

## Тестирование

### Checklist для проверки:

- [ ] При выборе 3 месяцев показывается скидка -15%
- [ ] При выборе 12 месяцев показывается скидка -25%
- [ ] В breakdown правильно отображается структура цены
- [ ] При нажатии Pay открывается нативное окно Telegram Stars
- [ ] После успешной оплаты показывается success toast
- [ ] Подписка активируется корректно
- [ ] При отмене оплаты показывается cancelled toast
- [ ] Не показываются лишние тоасты

## Важные замечания

1. **Telegram Stars доступны только в Mini App**
   - Проверка `isMiniApp` обязательна
   - В веб-версии показывается соответствующее сообщение

2. **Версия Telegram**
   - Метод `openInvoice` доступен с определенной версии
   - Добавлена проверка наличия метода

3. **Цены уже включают скидку за длительность**
   - `quarterly` = monthly × 3 × 0.85
   - `yearly` = monthly × 12 × 0.75

4. **Реферальная скидка применяется после скидки за длительность**
   - Сначала применяется скидка за длительность
   - Потом применяется реферальная скидка
   - Это дает более выгодные условия для пользователей

## API Reference

### Bot API
- **Метод:** `create_invoice_link`
- **Документация:** https://core.telegram.org/bots/api#createinvoicelink
- **Параметры для Stars:**
  - `currency`: "XTR"
  - `provider_token`: "" (пустая строка)
  - `prices`: массив с одним элементом
  - `amount`: количество Stars (не центы!)

### Mini App API
- **Метод:** `WebApp.openInvoice(url, callback)`
- **Документация:** https://core.telegram.org/bots/webapps#invoice
- **Callback статусы:**
  - `paid` - успешная оплата
  - `cancelled` - отменено пользователем
  - `failed` - ошибка оплаты
  - `pending` - в процессе

## Связанные файлы

### Frontend
- `frontend/types/telegram.d.ts`
- `frontend/components/modals/PremiumPurchaseModal.tsx`
- `frontend/components/providers/TelegramProvider.tsx`

### Backend
- `src/services/telegram_stars_service.py`
- `src/api/payment.py`
- `src/database/models.py` (Payment, Subscription)

## Автор
Исправления выполнены 2025-01-22
