# 🔧 Troubleshooting: $SYNTRA Points не отображаются

**Дата:** 2025-12-03

---

## ✅ Что проверено на проде:

1. ✅ Файлы задеплоены:
   - `frontend/components/points/PointsBalance.tsx` ✅
   - `frontend/components/points/PointsModal.tsx` ✅
   - `frontend/components/layout/Header.tsx` (с импортом PointsBalance) ✅
   - `frontend/messages/ru.json` (с секцией points) ✅
   - `frontend/messages/en.json` (с секцией points) ✅

2. ✅ Frontend собран:
   - Build ID: `Vo48Zoo-VTHW751Ls7D5m` (03.12.2025 01:02)
   - Процесс перезапущен: `pm2 restart tradient-front` ✅
   - Статус: `online` ✅

3. ✅ API роуты зарегистрированы:
   - `src/api/points.py` на месте ✅
   - Router включен в `src/api/router.py` ✅

---

## 🔍 Возможные причины проблемы:

### 1. **Browser Cache (90% вероятность)**

**Симптомы:**
- Старая версия страницы загружается из кеша
- Points баланс не появляется даже после деплоя

**Решение:**
```bash
# В браузере:
Ctrl+Shift+R (Windows/Linux)
Cmd+Shift+R (Mac)

# Или:
1. Открыть DevTools (F12)
2. Right-click на кнопке Refresh
3. Выбрать "Empty Cache and Hard Reload"

# Или:
1. Открыть Settings браузера
2. Clear browsing data
3. Выбрать "Cached images and files"
4. Clear data
```

**Для Telegram Mini App:**
```bash
1. Закрыть полностью Telegram
2. Переоткрыть
3. Или: удалить Mini App и добавить заново
```

---

### 2. **Пользователь не авторизован**

**Симптомы:**
- `user` в userStore = `null`
- PointsBalance не рендерится (условие `user && showBalance`)

**Как проверить:**
```javascript
// В DevTools Console:
localStorage.getItem('syntra-user-storage')

// Должно вернуть JSON с user объектом
```

**Решение:**
```bash
1. Проверить что пользователь залогинен
2. Проверить что initData валиден
3. Попробовать re-login через /start в боте
```

---

### 3. **У пользователя нет points в базе**

**Симптомы:**
- API endpoint `/api/points/balance` возвращает 404 или пустой ответ
- PointsBalance рендерится но не показывается (условие `if (!balance) return null`)

**Как проверить на проде:**
```bash
# SSH на сервер
ssh syntra

# Проверить базу данных
cd /root/syntraai
python3 -c "
import asyncio
from src.database.engine import get_session_local
from src.database.models import User
from sqlalchemy import select

async def check_user(telegram_id):
    async with get_session_local() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            print(f'User: {user.first_name}')
            print(f'Points: {user.points}')
            print(f'Level: {user.points_level}')
        else:
            print('User not found')

asyncio.run(check_user(YOUR_TELEGRAM_ID))
"
```

**Решение:**
```bash
# Если points = 0, нужно начислить начальные поинты через бота:
# 1. Написать боту любое сообщение (начислится за text_request)
# 2. Или админ может начислить: /points_grant <user_id> 100
```

---

### 4. **API endpoint не работает**

**Симптомы:**
- Ошибка в Console: `Failed to fetch points balance`
- API возвращает 500/404

**Как проверить:**
```bash
# На проде
ssh syntra
curl -X GET http://localhost:8001/api/points/balance \
  -H "Authorization: Bearer YOUR_TOKEN"

# Или проверить логи API
pm2 logs tradient-api --lines 50
```

**Решение:**
```bash
# Перезапустить API
pm2 restart tradient-api

# Проверить что points_service работает
pm2 logs tradient-api | grep -i point
```

---

### 5. **Frontend build не применился**

**Симптомы:**
- После `pm2 restart` изменения всё равно не видны
- В Network tab видны старые файлы

**Решение:**
```bash
# На проде пересобрать frontend
ssh syntra
cd /root/syntraai/frontend
npm run build
pm2 restart tradient-front
```

---

## 📊 Пошаговая диагностика:

### Шаг 1: Проверить что компонент рендерится
```javascript
// В DevTools Console на странице Mini App:
document.querySelector('[class*="PointsBalance"]') ||
document.querySelector('button img[alt="$SYNTRA"]')

// Если null - компонент не рендерится
// Причина: либо user = null, либо showBalance = false
```

### Шаг 2: Проверить user в store
```javascript
// В DevTools Console:
JSON.parse(localStorage.getItem('syntra-user-storage'))

// Должно показать: { state: { user: {...}, isAuthenticated: true } }
```

### Шаг 3: Проверить API запрос
```javascript
// В DevTools Network tab:
// Фильтр: "balance"
// Должен быть запрос: GET /api/points/balance
// Status: 200 OK
// Response: { balance: ..., level: ..., ... }
```

### Шаг 4: Проверить points store
```javascript
// В DevTools Console:
JSON.parse(localStorage.getItem('syntra-points-storage'))

// Должно показать: { state: { balance: {...}, isLoading: false } }
```

---

## 🚀 Быстрое решение (90% случаев):

```bash
1. Hard refresh: Ctrl+Shift+R (или Cmd+Shift+R)
2. Если не помогло: Clear cache в браузере
3. Если не помогло: Переоткрыть Telegram полностью
4. Если не помогло: Написать боту любое сообщение (начислит поинты)
5. Если не помогло: Проверить DevTools Console на ошибки
```

---

## 📞 Если всё ещё не работает:

1. Открыть DevTools (F12)
2. Перейти в Console tab
3. Скопировать все ошибки (если есть)
4. Перейти в Network tab
5. Проверить запрос `/api/points/balance`
6. Скопировать response

Эта информация покажет точную причину.

---

## ✅ Expected Behavior (как должно работать):

1. Пользователь открывает Mini App
2. Header загружается с LanguageSwitcher + PointsBalance
3. PointsBalance автоматически делает `GET /api/points/balance`
4. Если баланс есть → показывает логотип + число + level icon
5. При клике → открывается PointsModal с описанием

---

**Status:** Deployed to Production
**Last Update:** 2025-12-03 03:44 UTC
