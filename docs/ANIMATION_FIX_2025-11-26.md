# Исправление квадратных анимаций свечения на лендинге

**Дата:** 2025-11-26
**Файлы:** `frontend/app/landing/landing.css`

## Проблема

На лендинге присутствовали квадратные анимации свечения вокруг карточек Premium тарифа и Final CTA блока. Эффект создавался через `conic-gradient` с постоянным вращением (`rotate`), что выглядело неестественно и угловато.

## Решение

### 1. Карточки тарифов (`.pricing-card`)

**Было:**
```css
.pricing-card::before {
  background: conic-gradient(...);
  animation: rotatePricing 10s linear infinite;
}
```

**Стало:**
```css
.pricing-card::before {
  background: radial-gradient(
    circle at center,
    rgba(59, 130, 246, 0.15) 0%,
    transparent 70%
  );
  animation: pulseGlow 2s ease-in-out infinite;
}
```

### 2. Premium карточка (`.pricing-card-featured`)

Добавлена усиленная анимация свечения:
```css
.pricing-card-featured::before {
  background: radial-gradient(
    circle at center,
    rgba(59, 130, 246, 0.25) 0%,
    transparent 65%
  );
  animation: pulseGlowStrong 2s ease-in-out infinite;
}
```

### 3. Final CTA блок (`.final-cta`)

**Было:**
```css
.final-cta::before {
  background: conic-gradient(...);
  animation: rotateCTA 15s linear infinite;
}
```

**Стало:**
```css
.final-cta::before {
  background: radial-gradient(
    ellipse at center,
    rgba(59, 130, 246, 0.2) 0%,
    transparent 60%
  );
  animation: breatheGlow 4s ease-in-out infinite;
}
```

## Новые анимации

### `pulseGlow` - мягкое пульсирование
Используется для обычных карточек тарифов:
- Opacity: 0.6 → 1 → 0.6
- Scale: 1 → 1.02 → 1
- Длительность: 2s

### `pulseGlowStrong` - усиленное пульсирование
Используется для Premium карточки:
- Opacity: 0.8 → 1 → 0.8
- Scale: 1 → 1.05 → 1
- Длительность: 2s

### `breatheGlow` - дыхание
Используется для Final CTA блока:
- Opacity: 0.4 → 0.8 → 0.4
- Scale: 0.95 → 1.05 → 0.95
- Длительность: 4s

## Результат

✅ Убраны квадратные угловатые анимации
✅ Добавлены плавные радиальные свечения
✅ Эффект выглядит более премиально и естественно
✅ Билд прошел успешно без ошибок

## Удалённые анимации

- `@keyframes rotatePricing` - больше не используется
- `@keyframes rotateCTA` - заменена на `breatheGlow`
