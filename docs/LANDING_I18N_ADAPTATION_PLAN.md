# План адаптации Landing Page для i18n

## Цель
Полностью адаптировать landing page для использования системы локализации через `useTranslations` из `next-intl`.

## Изменения

### 1. Imports
Добавить:
```typescript
import { useTranslations } from 'next-intl';
import LanguageSwitcher from '@/components/layout/LanguageSwitcher';
```

### 2. Header - добавить LanguageSwitcher
```typescript
<div className="flex items-center gap-3">
  {/* Language Switcher */}
  <LanguageSwitcher size="md" />

  {/* Telegram Channel Button */}
  <Link ...>
    ...
  </Link>

  {/* Open Button */}
  <Link ...>
    {t('landing.header.open')}
  </Link>
</div>
```

### 3. Navigation - использовать переводы
```typescript
const t = useTranslations();

<nav className="hidden md:flex gap-6 text-sm text-white/60">
  <a href="#how">{t('landing.header.nav.how')}</a>
  <a href="#features">{t('landing.header.nav.features')}</a>
  <a href="#forwho">{t('landing.header.nav.forwho')}</a>
  <a href="#referral">{t('landing.header.nav.referral')}</a>
  <a href="#faq">{t('landing.header.nav.faq')}</a>
</nav>
```

### 4. Все секции - заменить хардкод на t()
- Hero section
- Problem section
- Solution section
- How it works section
- For whom section
- Features section
- Personality section
- Pricing section
- Referral section
- FAQ section
- Final CTA section
- Footer

## Детальный план замены

### Hero Section
```typescript
<div className="inline-block...">
  {t('landing.hero.badge')}
</div>

<h1 className="text-4xl...">
  {t('landing.hero.title')}
</h1>

<p className="text-white/70...">
  {t('landing.hero.subtitle')}
</p>

<ul className="space-y-2...">
  <li dangerouslySetInnerHTML={{ __html: t.raw('landing.hero.trial_feature') }} />
  <li>• {t('landing.hero.trial_requests')}</li>
  <li>• {t('landing.hero.trial_after')}</li>
</ul>
```

### Problem Section
```typescript
<h2>{t('landing.problem.title')}</h2>
<p>{t('landing.problem.subtitle')}</p>

<div className="card">
  <h3>{t('landing.problem.noise_title')}</h3>
  <p>{t('landing.problem.noise_text')}</p>
</div>
```

### И так далее для всех секций...

## Важные детали

1. **dangerouslySetInnerHTML** - использовать для текстов с HTML тегами `<strong>`
2. **LanguageSwitcher** - добавить в header справа от логотипа
3. **QuickLoginModal** - передавать текущую локаль из `useCurrentLocale()`

## Статус
- [ ] Адаптировать imports
- [ ] Добавить LanguageSwitcher в header
- [ ] Адаптировать Navigation
- [ ] Адаптировать Hero section
- [ ] Адаптировать Problem section
- [ ] Адаптировать Solution section
- [ ] Адаптировать How section
- [ ] Адаптировать For whom section
- [ ] Адаптировать Features section
- [ ] Адаптировать Personality section
- [ ] Адаптировать Pricing section
- [ ] Адаптировать Referral section
- [ ] Адаптировать FAQ section
- [ ] Адаптировать Final CTA
- [ ] Адаптировать Footer
- [ ] Тестирование переключения языков
