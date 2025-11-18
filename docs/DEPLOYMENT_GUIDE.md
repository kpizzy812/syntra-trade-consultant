# 🚀 Деплой на ai.syntratrade.xyz

> Инструкция по деплою Syntra Mini App на собственный сервер

## 📋 Архитектура

```
ai.syntratrade.xyz          → Next.js Frontend (порт 3000)
ai.syntratrade.xyz/api      → FastAPI Backend (порт 8000)
syntratrade.xyz             → Основной лендинг (без изменений)
```

---

## 1️⃣ Подготовка на локальной машине

### Build frontend

```bash
cd frontend
npm run build
```

Это создаст `.next/standalone/` директорию для деплоя.

---

## 2️⃣ Деплой на сервер

### Загрузить на сервер

```bash
# Из корня проекта
rsync -avz --exclude 'node_modules' --exclude '.next' --exclude '.git' \
  ./ syntra:/root/syntraai/

# Загрузить build frontend
rsync -avz frontend/.next/standalone/ syntra:/root/syntraai/frontend/.next/standalone/
rsync -avz frontend/.next/static/ syntra:/root/syntraai/frontend/.next/static/
rsync -avz frontend/public/ syntra:/root/syntraai/frontend/public/
```

### На сервере: установить зависимости

```bash
ssh syntra

cd /root/syntraai

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Создать .env
cp .env.example .env
nano .env  # Обновить переменные
```

### Обновить .env на сервере

```bash
# Основные переменные
BOT_TOKEN=your_bot_token
DATABASE_URL=postgresql+asyncpg://...
OPENAI_API_KEY=sk-...

# Mini App URL (ВАЖНО!)
WEBAPP_URL=https://ai.syntratrade.xyz

# Backend API URL для frontend
NEXT_PUBLIC_API_URL=https://ai.syntratrade.xyz/api

# Environment
ENVIRONMENT=production
```

---

## 3️⃣ Nginx конфигурация

Создать файл `/etc/nginx/sites-available/ai.syntratrade.xyz`:

```nginx
# Upstream для backend API
upstream syntra_api {
    server 127.0.0.1:8000;
    keepalive 64;
}

# Upstream для frontend
upstream syntra_frontend {
    server 127.0.0.1:3000;
    keepalive 64;
}

# HTTPS сервер
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ai.syntratrade.xyz;

    # SSL сертификаты (certbot автоматически добавит)
    ssl_certificate /etc/letsencrypt/live/ai.syntratrade.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ai.syntratrade.xyz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers для Telegram Mini App
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "frame-ancestors 'self' https://web.telegram.org https://telegram.org" always;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # API routes → FastAPI backend
    location /api {
        proxy_pass http://syntra_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        proxy_pass http://syntra_api/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Static files от Next.js
    location /_next/static {
        alias /root/syntraai/frontend/.next/static;
        expires 1y;
        access_log off;
        add_header Cache-Control "public, immutable";
    }

    # Public files
    location /public {
        alias /root/syntraai/frontend/public;
        expires 7d;
        access_log off;
    }

    # Все остальное → Next.js frontend
    location / {
        proxy_pass http://syntra_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Размеры загрузок
    client_max_body_size 10M;
}

# HTTP → HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name ai.syntratrade.xyz;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}
```

### Включить сайт

```bash
# Создать symlink
ln -s /etc/nginx/sites-available/ai.syntratrade.xyz /etc/nginx/sites-enabled/

# Проверить конфигурацию
nginx -t

# Перезагрузить nginx
systemctl reload nginx
```

---

## 4️⃣ SSL сертификат (Let's Encrypt)

```bash
# Установить certbot (если еще не установлен)
apt update
apt install certbot python3-certbot-nginx

# Получить сертификат
certbot --nginx -d ai.syntratrade.xyz

# Автообновление уже настроено через systemd timer
```

---

## 5️⃣ Systemd сервисы

### Backend API сервис

Создать `/etc/systemd/system/syntra-api.service`:

```ini
[Unit]
Description=Syntra Mini App API (FastAPI)
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/syntraai
Environment="PATH=/root/syntraai/.venv/bin"
ExecStart=/root/syntraai/.venv/bin/python api_server.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/syntra-api.log
StandardError=append:/var/log/syntra-api-error.log

[Install]
WantedBy=multi-user.target
```

### Frontend сервис

Создать `/etc/systemd/system/syntra-frontend.service`:

```ini
[Unit]
Description=Syntra Mini App Frontend (Next.js)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/syntraai/frontend/.next/standalone
Environment="PORT=3000"
Environment="NODE_ENV=production"
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/syntra-frontend.log
StandardError=append:/var/log/syntra-frontend-error.log

[Install]
WantedBy=multi-user.target
```

### Telegram Bot сервис

Создать `/etc/systemd/system/syntra-bot.service`:

```ini
[Unit]
Description=Syntra Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/syntraai
Environment="PATH=/root/syntraai/.venv/bin"
ExecStart=/root/syntraai/.venv/bin/python bot.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/syntra-bot.log
StandardError=append:/var/log/syntra-bot-error.log

[Install]
WantedBy=multi-user.target
```

### Запустить сервисы

```bash
# Перезагрузить systemd
systemctl daemon-reload

# Включить автозапуск
systemctl enable syntra-api syntra-frontend syntra-bot

# Запустить сервисы
systemctl start syntra-api
systemctl start syntra-frontend
systemctl start syntra-bot

# Проверить статус
systemctl status syntra-api
systemctl status syntra-frontend
systemctl status syntra-bot
```

---

## 6️⃣ Раскомментировать Web App кнопку

После успешного деплоя, обновить `src/bot/handlers/start.py`:

```python
keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        # Row 1: Web App button (первая кнопка в первом ряду)
        [
            InlineKeyboardButton(
                text=i18n.get("menu.open_app", language),
                web_app=WebAppInfo(url=WEBAPP_URL)
            ),
        ],
        # Row 2: Help and Profile
        [
            InlineKeyboardButton(
                text=i18n.get("menu.help", language), callback_data="menu_help"
            ),
            InlineKeyboardButton(
                text=i18n.get("menu.profile", language),
                callback_data="menu_profile",
            ),
        ],
        # Row 3: Referral and Premium
        [
            InlineKeyboardButton(
                text=i18n.get("menu.referral", language),
                callback_data="menu_referral",
            ),
            InlineKeyboardButton(
                text=i18n.get("menu.premium", language),
                callback_data="menu_premium",
            ),
        ],
    ]
)
```

Затем:
```bash
systemctl restart syntra-bot
```

---

## 7️⃣ Проверка

### Проверить сервисы

```bash
# Логи
journalctl -u syntra-api -f
journalctl -u syntra-frontend -f
journalctl -u syntra-bot -f

# Или через файлы
tail -f /var/log/syntra-api.log
tail -f /var/log/syntra-frontend.log
tail -f /var/log/syntra-bot.log
```

### Тестирование

1. **Frontend**: https://ai.syntratrade.xyz
2. **API Health**: https://ai.syntratrade.xyz/api/health
3. **Telegram Bot**: `/start` должен показать кнопку "🚀 Открыть приложение"
4. **Mini App**: Клик по кнопке откроет https://ai.syntratrade.xyz

---

## 8️⃣ Автоматический деплой (опционально)

Создать скрипт `deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Деплой Syntra Mini App на ai.syntratrade.xyz"

# Build frontend локально
echo "📦 Building frontend..."
cd frontend
npm run build
cd ..

# Загрузка на сервер
echo "📤 Uploading to server..."
rsync -avz --exclude 'node_modules' --exclude '.git' --exclude '.next/cache' \
  ./ syntra:/root/syntraai/

rsync -avz frontend/.next/standalone/ syntra:/root/syntraai/frontend/.next/standalone/
rsync -avz frontend/.next/static/ syntra:/root/syntraai/frontend/.next/static/
rsync -avz frontend/public/ syntra:/root/syntraai/frontend/public/

# Рестарт сервисов на сервере
echo "🔄 Restarting services..."
ssh syntra << 'EOF'
cd /root/syntraai
source .venv/bin/activate
pip install -r requirements.txt --quiet
systemctl restart syntra-api
systemctl restart syntra-frontend
systemctl restart syntra-bot
EOF

echo "✅ Deployment complete!"
echo "🌐 Check: https://ai.syntratrade.xyz"
```

Использование:
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 🔧 Полезные команды

### Перезапуск всех сервисов
```bash
systemctl restart syntra-api syntra-frontend syntra-bot
```

### Просмотр логов
```bash
# Все логи
tail -f /var/log/syntra-*.log

# Только ошибки
grep -i error /var/log/syntra-*.log
```

### Обновление кода
```bash
cd /root/syntraai
git pull  # если используешь git
systemctl restart syntra-api syntra-frontend syntra-bot
```

---

## ✅ Чек-лист деплоя

- [ ] Frontend собран (`npm run build`)
- [ ] Файлы загружены на сервер
- [ ] `.env` обновлен с production переменными
- [ ] Nginx конфигурация создана
- [ ] SSL сертификат получен
- [ ] Systemd сервисы созданы и запущены
- [ ] Web App кнопка раскомментирована
- [ ] Бот перезапущен
- [ ] Тестирование: `/start` → Кнопка работает
- [ ] Mini App открывается по HTTPS

---

**Создано**: 2025-01-18
**Сервер**: ai.syntratrade.xyz
**Порты**: Frontend 3000, API 8000
