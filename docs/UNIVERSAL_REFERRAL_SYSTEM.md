# 🌐 Universal Referral System - Multi-Platform

## 🚨 Текущая проблема

### Сейчас (Telegram-only):
```python
# src/api/referral.py:132
referral_link = f"https://t.me/{bot_username}?start=ref_{code}"
```

**Проблема:**
- ❌ Работает только для Telegram
- ❌ Веб-пользователи не могут использовать рефки
- ❌ Нет tracking для web/mobile
- ❌ User model привязан к `telegram_id`

**Пример:**
```
Telegram юзер: @ivan → referral_code: ABC123
Отправляет другу: https://t.me/syntra_bot?start=ref_ABC123
Друг открывает в браузере → не работает! ❌
```

---

## ✅ Решение: Universal Smart Links

### Концепция:
```
https://syntra.ai/r/ABC123 (универсальная ссылка)
         ↓
  Auto-detect platform
         ↓
┌────────┼────────┬─────────┐
│        │        │         │
Telegram  Web    iOS     Android
```

### Как работает:

#### 1. Короткая универсальная ссылка
```
https://syntra.ai/r/ABC123
```

#### 2. Backend определяет откуда открыто
```python
# api_server.py или Next.js middleware
@app.get("/r/{code}")
async def redirect_referral(code: str, request: Request):
    user_agent = request.headers.get("user-agent", "")

    # Telegram
    if "Telegram" in user_agent:
        return redirect(f"https://t.me/syntra_bot?start=ref_{code}")

    # iOS
    elif "iPhone" in user_agent or "iPad" in user_agent:
        # TODO: Deep link в iOS app (когда будет)
        return redirect(f"https://syntra.ai?ref={code}")

    # Android
    elif "Android" in user_agent:
        # TODO: Deep link в Android app (когда будет)
        return redirect(f"https://syntra.ai?ref={code}")

    # Web (desktop/mobile browser)
    else:
        return redirect(f"https://syntra.ai?ref={code}")
```

#### 3. Tracking работает везде
```python
# Web: ?ref=ABC123
# Telegram: ?start=ref_ABC123
# iOS/Android: deep link schema syntra://r/ABC123

# Всегда сохраняем:
- Откуда пришел (telegram/web/ios/android)
- UTM параметры
- Конверсии
```

---

## 📊 Database Changes

### Текущая User модель:
```python
class User(Base):
    id: Mapped[int]
    telegram_id: Mapped[int]  # ❌ Только Telegram
    username: Mapped[Optional[str]]
    referral_code: Mapped[Optional[str]]  # ✅ Универсальный код (хорошо!)
```

### Проблема:
- `telegram_id` обязательный и unique
- Веб-юзеры не имеют `telegram_id`

### Решение A: Nullable telegram_id + добавить email

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Platform-specific identifiers (nullable!)
    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        unique=True,  # Остается unique, но nullable
        nullable=True,  # ✅ Может быть None для веб-юзеров
        comment="Telegram user ID (null for web users)"
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        comment="Email for web users (null for telegram-only users)"
    )

    # Constraint: либо telegram_id, либо email должен быть
    __table_args__ = (
        CheckConstraint(
            'telegram_id IS NOT NULL OR email IS NOT NULL',
            name='user_must_have_identifier'
        ),
    )

    # Universal fields
    username: Mapped[Optional[str]]
    first_name: Mapped[Optional[str]]
    referral_code: Mapped[Optional[str]] = mapped_column(
        unique=True,
        comment="Universal referral code (works across all platforms)"
    )

    # NEW: Platform tracking
    registration_platform: Mapped[str] = mapped_column(
        String(20),
        default="telegram",
        comment="Platform where user registered: telegram, web, ios, android"
    )
```

### Migration:
```python
# alembic/versions/xxx_universal_user_model.py
def upgrade():
    # 1. Сделать telegram_id nullable
    op.alter_column('users', 'telegram_id',
        existing_type=sa.BigInteger(),
        nullable=True)  # Было False

    # 2. Добавить email
    op.add_column('users',
        sa.Column('email', sa.String(255), unique=True, nullable=True))

    # 3. Добавить registration_platform
    op.add_column('users',
        sa.Column('registration_platform', sa.String(20),
                  server_default='telegram', nullable=False))

    # 4. Добавить constraint
    op.create_check_constraint(
        'user_must_have_identifier',
        'users',
        'telegram_id IS NOT NULL OR email IS NOT NULL'
    )
```

---

## 🔗 API Changes

### Старый endpoint (только Telegram):
```python
# src/api/referral.py
@router.get("/link")
async def get_referral_link(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    code = user.referral_code or generate_referral_code()

    return {
        "referral_code": code,
        "referral_link": f"https://t.me/syntra_bot?start=ref_{code}",  # ❌ Только TG
        "qr_code_url": f"https://api.qrserver.com/.../data={referral_link}"
    }
```

### Новый endpoint (Universal):
```python
# src/api/referral.py
@router.get("/link")
async def get_referral_link(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get universal referral links for all platforms

    Returns:
        {
            "code": "ABC123",
            "universal_link": "https://syntra.ai/r/ABC123",
            "platform_links": {
                "telegram": "https://t.me/syntra_bot?start=ref_ABC123",
                "web": "https://syntra.ai?ref=ABC123",
                "ios": "syntra://r/ABC123",  # Deep link (будущее)
                "android": "syntra://r/ABC123"  # Deep link (будущее)
            },
            "qr_code": "https://api.qrserver.com/.../data=https://syntra.ai/r/ABC123",
            "share_text": "Join Syntra AI and get 5 free questions! 🤖\nhttps://syntra.ai/r/ABC123"
        }
    """
    from config.config import BOT_USERNAME, WEB_APP_URL

    code = user.referral_code
    if not code:
        code = await generate_referral_code(session, user.id)
        user.referral_code = code
        await session.commit()

    # Universal short link (приоритет!)
    universal_link = f"{WEB_APP_URL}/r/{code}"

    return {
        "code": code,
        "universal_link": universal_link,  # ✅ Главная ссылка
        "platform_links": {
            "telegram": f"https://t.me/{BOT_USERNAME}?start=ref_{code}",
            "web": f"{WEB_APP_URL}?ref={code}",
            "ios": f"syntra://r/{code}",  # Будущее
            "android": f"syntra://r/{code}",  # Будущее
        },
        "qr_code": f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={universal_link}",
        "share_text": f"Join Syntra AI and get 5 free questions! 🤖\n{universal_link}",
        "stats": {
            "total_clicks": 0,  # TODO: Tracking
            "telegram_clicks": 0,
            "web_clicks": 0,
            "conversions": 0,
        }
    }
```

---

## 🎯 Redirect Handler (Backend)

### Next.js App Router:
```typescript
// frontend/app/r/[code]/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function GET(
  request: NextRequest,
  { params }: { params: { code: string } }
) {
  const code = params.code
  const userAgent = request.headers.get('user-agent') || ''

  // Track referral click
  await fetch(`${process.env.API_URL}/referral/track/${code}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_agent: userAgent,
      ip: request.ip,
      timestamp: new Date().toISOString(),
    })
  })

  // Platform detection
  const isTelegram = userAgent.includes('Telegram')
  const isIOS = /iPhone|iPad/.test(userAgent)
  const isAndroid = /Android/.test(userAgent)

  // Redirect
  if (isTelegram) {
    return NextResponse.redirect(`https://t.me/syntra_bot?start=ref_${code}`)
  } else if (isIOS || isAndroid) {
    // TODO: Deep link когда будут приложения
    return NextResponse.redirect(`${process.env.NEXT_PUBLIC_WEB_URL}?ref=${code}`)
  } else {
    // Web (desktop/mobile browser)
    return NextResponse.redirect(`${process.env.NEXT_PUBLIC_WEB_URL}?ref=${code}`)
  }
}
```

### FastAPI (альтернатива):
```python
# api_server.py
from fastapi import Request
from fastapi.responses import RedirectResponse
from config.config import BOT_USERNAME, WEB_APP_URL

@app.get("/r/{code}")
async def redirect_referral(code: str, request: Request):
    """Universal referral redirect"""
    user_agent = request.headers.get("user-agent", "")

    # Track click
    await track_referral_click(
        code=code,
        user_agent=user_agent,
        ip=request.client.host,
    )

    # Platform detection
    if "Telegram" in user_agent:
        return RedirectResponse(f"https://t.me/{BOT_USERNAME}?start=ref_{code}")
    elif "iPhone" in user_agent or "iPad" in user_agent:
        # iOS
        return RedirectResponse(f"{WEB_APP_URL}?ref={code}&platform=ios")
    elif "Android" in user_agent:
        # Android
        return RedirectResponse(f"{WEB_APP_URL}?ref={code}&platform=android")
    else:
        # Web (desktop)
        return RedirectResponse(f"{WEB_APP_URL}?ref={code}&platform=web")
```

---

## 📱 Frontend Changes

### Profile page - показываем universal link:
```typescript
// frontend/app/profile/page.tsx
export default function ProfilePage() {
  const { data: referralData } = useSWR('/referral/link')

  return (
    <div>
      <h2>Your Referral Link</h2>

      {/* Главная ссылка */}
      <div className="universal-link">
        <input
          value={referralData?.universal_link}
          readOnly
        />
        <button onClick={() => copyToClipboard(referralData?.universal_link)}>
          Copy
        </button>
      </div>

      {/* Опционально: Platform-specific links */}
      <details>
        <summary>Platform-specific links</summary>
        <ul>
          <li>Telegram: {referralData?.platform_links.telegram}</li>
          <li>Web: {referralData?.platform_links.web}</li>
        </ul>
      </details>

      {/* Share buttons */}
      <div className="share-buttons">
        <button onClick={() => shareToTelegram(referralData?.universal_link)}>
          Share to Telegram
        </button>
        <button onClick={() => shareToWhatsApp(referralData?.universal_link)}>
          Share to WhatsApp
        </button>
        <button onClick={() => shareViaWebShare(referralData)}>
          Share...
        </button>
      </div>
    </div>
  )
}

// Web Share API (работает на mobile)
async function shareViaWebShare(data: any) {
  if (navigator.share) {
    await navigator.share({
      title: 'Join Syntra AI',
      text: data.share_text,
      url: data.universal_link,
    })
  }
}
```

---

## 🎯 Referral Tracking

### Новая таблица: ReferralClick
```python
class ReferralClick(Base):
    """Track referral link clicks"""
    __tablename__ = "referral_clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    referral_code: Mapped[str] = mapped_column(index=True)

    # Tracking data
    clicked_at: Mapped[datetime]
    platform: Mapped[str]  # telegram, web, ios, android
    user_agent: Mapped[Optional[str]]
    ip_address: Mapped[Optional[str]]

    # Conversion tracking
    converted: Mapped[bool] = mapped_column(default=False)
    converted_at: Mapped[Optional[datetime]]
    converted_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
```

### Tracking endpoint:
```python
# src/api/referral.py
@router.post("/track/{code}")
async def track_referral_click(
    code: str,
    data: dict,
    session: AsyncSession = Depends(get_session),
):
    """Track referral link click (no auth required)"""

    # Detect platform from user agent
    user_agent = data.get("user_agent", "")
    platform = "unknown"
    if "Telegram" in user_agent:
        platform = "telegram"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        platform = "ios"
    elif "Android" in user_agent:
        platform = "android"
    else:
        platform = "web"

    # Save click
    click = ReferralClick(
        referral_code=code,
        clicked_at=datetime.utcnow(),
        platform=platform,
        user_agent=user_agent,
        ip_address=data.get("ip"),
    )
    session.add(click)
    await session.commit()

    return {"status": "tracked"}
```

---

## 🚀 Implementation Plan

### Phase 1: Database (1 день)
```bash
✅ Создать миграцию для User модели
  ├─ telegram_id → nullable
  ├─ Добавить email column
  ├─ Добавить registration_platform
  └─ Добавить constraint

✅ Создать ReferralClick таблицу
```

### Phase 2: Backend API (2 дня)
```bash
✅ Обновить /referral/link endpoint
  └─ Возвращать universal links

✅ Создать /r/{code} redirect endpoint
  ├─ Platform detection
  ├─ Tracking
  └─ Redirect logic

✅ Создать /referral/track/{code} endpoint
  └─ Analytics tracking
```

### Phase 3: Frontend (1 день)
```bash
✅ Обновить Profile page
  ├─ Показывать universal link
  ├─ Copy button
  └─ Share buttons

✅ Создать /r/[code]/route.ts в Next.js
  └─ Redirect handler
```

### Phase 4: Testing (1 день)
```bash
✅ Тестировать все платформы:
  ├─ Telegram → работает
  ├─ Web → работает
  ├─ Mobile browser → работает
  └─ QR code → работает
```

---

## 💡 Bonus Features

### Smart QR Code:
```typescript
// QR code который показывает разную информацию
<QRCode
  value="https://syntra.ai/r/ABC123"
  logo="/syntra/logo.png"  // Branding
  size={300}
/>
```

### UTM Integration:
```typescript
// Tracking маркетинговых каналов
const link = `${universal_link}?utm_source=twitter&utm_medium=social&utm_campaign=launch`

// Backend сохраняет UTM параметры:
{
  referral_code: "ABC123",
  utm_source: "twitter",
  utm_medium: "social",
  utm_campaign: "launch",
  platform: "web"
}
```

### A/B Testing:
```typescript
// Разные варианты landing page
if (ref_code) {
  // Variant A: Direct signup CTA
  // Variant B: Show features first
  // Measure conversion rate
}
```

---

## 📊 Analytics Dashboard

### Referral stats с breakdown:
```typescript
// frontend/app/profile/page.tsx
<ReferralStats>
  Total clicks: 150
  ├─ Telegram: 80 (53%)
  ├─ Web: 50 (33%)
  ├─ Mobile: 20 (14%)

  Conversions: 25 (16.7% rate)
  ├─ Telegram: 18 (72%)
  ├─ Web: 7 (28%)

  Revenue share: $125.50
</ReferralStats>
```

---

## ✅ Преимущества

### До (Telegram-only):
```
❌ Только Telegram пользователи
❌ Ссылка не работает в браузере
❌ Нет tracking по платформам
❌ Теряем конверсии
```

### После (Universal):
```
✅ Работает на ВСЕХ платформах
✅ Единая короткая ссылка
✅ Автоматический redirect
✅ Tracking по платформам
✅ Больше конверсий (web + telegram)
✅ Готовы к iOS/Android приложениям
✅ UTM tracking для маркетинга
```

---

## 🎯 Next Steps

1. **Начать с Database migration?**
   - Обновить User модель
   - Создать ReferralClick таблицу

2. **Или сразу Backend?**
   - Обновить API endpoints
   - Создать redirect handler

3. **Или Frontend first?**
   - Показать как будет выглядеть
   - Mockup с universal links

Что делаем первым?
