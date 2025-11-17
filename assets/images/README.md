# Изображения для Syntra Trade Consultant Bot

Структура изображений для разделов бота в стиле киберпанк/футуристик.

## Требуемые изображения

Размер: **1080x1080px** (квадрат) для оптимального отображения в Telegram

### 1. `start.png` - Главное приветствие
**Описание:** Космонавт в киберпанк стиле с логотипом Syntra и синей неоновой подсветкой (как в `syntrasquare.png`)

**Промпт для генерации:**
```
Futuristic astronaut helmet with blue neon glow, dark background, cyberpunk style,
SYNTRA AI BOT logo with blue electric glow, minimal design, professional crypto trading theme,
highly detailed, cinematic lighting, 8k quality, sci-fi aesthetic
```

### 2. `help.png` - Справка / Помощь
**Описание:** Голограмма с инструкциями, цифровой интерфейс

**Промпт для генерации:**
```
Futuristic holographic interface displaying help information, blue neon UI elements,
digital chart patterns and crypto symbols floating in space, dark cyberpunk background,
astronaut hand pointing at hologram, minimal modern design, blue and cyan color scheme
```

### 3. `profile.png` - Профиль пользователя
**Описание:** Личный дашборд, статистика

**Промпт для генерация:**
```
Cyberpunk user profile dashboard, futuristic data visualization, blue neon statistics,
personal trading metrics hologram, astronaut silhouette, dark background with blue accents,
minimalist sci-fi design, professional crypto trading theme
```

### 4. `referral.png` - Реферальная система
**Описание:** Сеть связей, партнерская программа

**Промпт для генерации:**
```
Futuristic network of connected nodes, blue neon connection lines, partnership concept,
people silhouettes connected in network, cyberpunk style, dark background,
blue glowing pathways between users, minimal modern design, crypto theme
```

### 5. `premium.png` - Premium подписка
**Описание:** VIP статус, золотые/синие элементы

**Промпт для генерация:**
```
Premium VIP badge in cyberpunk style, golden crown with blue neon glow,
luxury futuristic design, dark background with blue and gold accents,
astronaut helmet with premium features, exclusive elite theme,
minimal elegant design, high-tech aesthetic
```

## Инструменты для создания

### Рекомендуемые AI-генераторы:
1. **Midjourney** (лучшее качество)
   - Команда: `/imagine` + промпт выше
   - Добавь `--ar 1:1` для квадратного формата

2. **Leonardo.ai** (бесплатный)
   - Model: Leonardo Kino XL или Vision XL
   - Preset: Cinematic
   - Size: 1024x1024

3. **DALL-E 3** (через ChatGPT Plus)
   - Просто вставь промпт
   - Укажи: "square format, 1024x1024"

4. **Stable Diffusion** (локально)
   - Model: SDXL или RealVisXL
   - Sampler: DPM++ 2M Karras
   - Steps: 30-50

### Ручное редактирование (если нужно):
- **Photoshop** / **Photopea** (бесплатная онлайн-альтернатива)
- **Figma** для добавления текста и логотипа

## Стилистические требования

### Цветовая схема:
- **Основной:** Темный (#000000, #0a0a0a, #1a1a2e)
- **Акценты:** Синий неон (#00d4ff, #0099ff, #4d94ff)
- **Дополнительно:** Циан (#00ffff), белый текст

### Общие элементы:
- ✅ Темный фон (черный/очень темно-синий)
- ✅ Неоновая синяя подсветка
- ✅ Минималистичный дизайн
- ✅ Футуристичные элементы (голограммы, цифровые интерфейсы)
- ✅ Космонавт / шлем космонавта (фирменный элемент)
- ✅ Логотип Syntra (круг с молнией в синем неоне)

### Чего избегать:
- ❌ Перегруженности деталями
- ❌ Ярких кислотных цветов (кроме синего)
- ❌ Реалистичных фото (нужен digital art стиль)
- ❌ Текста на изображении (текст добавляется ботом)

## Использование в боте

Поместите готовые изображения в эту папку (`assets/images/`) со следующими именами:
- `start.png` - для команды /start
- `help.png` - для раздела "Помощь"
- `profile.png` - для раздела "Профиль"
- `referral.png` - для раздела "Реферальная система"
- `premium.png` - для раздела "Premium"

Бот автоматически обнаружит изображения и будет использовать их вместо простого текста.

## Текущий статус

- [x] `syntrasquare.png` - Эталонное изображение (космонавт с логотипом)
- [ ] `start.png` - Нужно создать
- [ ] `help.png` - Нужно создать
- [ ] `profile.png` - Нужно создать
- [ ] `referral.png` - Нужно создать
- [ ] `premium.png` - Нужно создать

---

**Примечание:** Код бота уже поддерживает отправку изображений. Как только вы добавите PNG файлы в эту папку, бот автоматически начнет их использовать.
