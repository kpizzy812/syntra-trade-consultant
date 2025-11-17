# DEPLOYMENT GUIDE - Syntra Trade Consultant

> Полное руководство по развертыванию бота в production и development окружениях

## Содержание
- [Системные требования](#системные-требования)
- [Development окружение](#development-окружение)
- [Production окружение](#production-окружение)
- [Docker деплой](#docker-деплой)
- [Мониторинг и обслуживание](#мониторинг-и-обслуживание)
- [Troubleshooting](#troubleshooting)

---

## Системные требования

### Минимальные требования
- **OS:** Linux (Ubuntu 20.04+), macOS 11+, Windows 10+ (WSL2)
- **Python:** 3.11 или выше
- **RAM:** 512 MB (development), 1 GB (production)
- **Disk:** 2 GB свободного места
- **Database:** PostgreSQL 14+

### Рекомендуемые требования (Production)
- **OS:** Ubuntu 22.04 LTS
- **Python:** 3.12
- **RAM:** 2 GB
- **Disk:** 10 GB SSD
- **Database:** PostgreSQL 16
- **CPU:** 2 cores

---

## Development окружение

### Шаг 1: Клонирование и настройка

```bash
# Клонирование репозитория
git clone <repository-url>
cd "Syntra Trade Consultant"

# Создание виртуального окружения
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Обновление pip
pip install --upgrade pip

# Установка зависимостей
pip install -r requirements.txt
```

### Шаг 2: Настройка переменных окружения

```bash
# Создать .env из примера
cp .env.example .env

# Отредактировать .env
nano .env  # или vim, code, etc.
```

**Обязательные переменные:**

```env
# Telegram Bot
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  # от @BotFather
REQUIRED_CHANNEL=@your_channel_name  # или -1001234567890
ADMIN_IDS=123456789,987654321  # через запятую

# Database
DATABASE_URL=postgresql+asyncpg://syntra:syntra_password@localhost:5433/syntra_bot

# OpenAI
OPENAI_API_KEY=sk-proj-...  # от platform.openai.com

# CryptoPanic (опционально для новостей)
CRYPTOPANIC_TOKEN=your_token_here  # от cryptopanic.com/developers/api
```

**Как получить токены:**

1. **BOT_TOKEN:**
   - Открыть [@BotFather](https://t.me/BotFather) в Telegram
   - Отправить `/newbot`
   - Следовать инструкциям
   - Скопировать полученный токен

2. **REQUIRED_CHANNEL:**
   - Создать публичный канал в Telegram
   - Добавить бота как администратора
   - Скопировать username канала (например, @mychannel)

3. **ADMIN_IDS:**
   - Открыть [@userinfobot](https://t.me/userinfobot)
   - Получить свой Telegram ID
   - Добавить в список через запятую

4. **OPENAI_API_KEY:**
   - Зайти на [platform.openai.com](https://platform.openai.com/)
   - API keys → Create new secret key
   - Скопировать ключ (показывается один раз!)

5. **CRYPTOPANIC_TOKEN:**
   - Зарегистрироваться на [cryptopanic.com](https://cryptopanic.com/)
   - Перейти в [API docs](https://cryptopanic.com/developers/api/)
   - Получить API key

### Шаг 3: Запуск PostgreSQL

```bash
# Через Docker (рекомендуется)
docker-compose up -d postgres

# Проверка статуса
docker ps | grep postgres

# Просмотр логов
docker logs syntra_postgres

# Подключение к БД для проверки
docker exec -it syntra_postgres psql -U syntra -d syntra_bot
```

**Альтернатива: Локальный PostgreSQL**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql-16

# macOS (Homebrew)
brew install postgresql@16
brew services start postgresql@16

# Создать пользователя и БД
sudo -u postgres psql
CREATE USER syntra WITH PASSWORD 'syntra_password';
CREATE DATABASE syntra_bot OWNER syntra;
\q
```

### Шаг 4: Применение миграций

```bash
# Применить все миграции
alembic upgrade head

# Проверка текущей версии
alembic current

# Откат миграции (если нужно)
alembic downgrade -1
```

### Шаг 5: Запуск бота

```bash
# Development режим
python bot.py

# С отображением логов в консоли
LOG_LEVEL=DEBUG python bot.py

# В фоне (Linux/Mac)
nohup python bot.py > bot.log 2>&1 &

# Просмотр логов
tail -f bot.log
tail -f logs/bot.log
```

### Проверка работы

1. Открыть бота в Telegram
2. Отправить `/start`
3. Подписаться на канал (если требуется)
4. Отправить тестовый вопрос
5. Проверить ответ AI

---

## Production окружение

### Подготовка сервера

**1. Обновление системы (Ubuntu 22.04):**

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv python3-pip git postgresql-16
```

**2. Создание пользователя для бота:**

```bash
# Создать пользователя
sudo useradd -m -s /bin/bash syntra

# Переключиться на пользователя
sudo su - syntra
```

**3. Клонирование и настройка:**

```bash
cd /opt
sudo mkdir syntra-bot
sudo chown syntra:syntra syntra-bot
cd syntra-bot

# Клонирование
git clone <repository-url> .

# Виртуальное окружение
python3.12 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt
```

**4. Настройка .env:**

```bash
# Создать .env
cp .env.example .env
nano .env

# ВАЖНО: Изменить пароли и токены!
# Использовать production DATABASE_URL
# Установить ENVIRONMENT=production
```

**5. Настройка PostgreSQL:**

```bash
# Создать пользователя и БД
sudo -u postgres psql

CREATE USER syntra WITH PASSWORD 'STRONG_PASSWORD_HERE';
CREATE DATABASE syntra_bot OWNER syntra;
GRANT ALL PRIVILEGES ON DATABASE syntra_bot TO syntra;
\q

# Применить миграции
cd /opt/syntra-bot
source .venv/bin/activate
alembic upgrade head
```

### Systemd Service

**1. Создать systemd unit файл:**

```bash
sudo nano /etc/systemd/system/syntra-bot.service
```

**Содержимое файла:**

```ini
[Unit]
Description=Syntra Trade Consultant Telegram Bot
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=syntra
Group=syntra
WorkingDirectory=/opt/syntra-bot
Environment="PATH=/opt/syntra-bot/.venv/bin"
ExecStart=/opt/syntra-bot/.venv/bin/python /opt/syntra-bot/bot.py

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/syntra-bot/bot.log
StandardError=append:/var/log/syntra-bot/error.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/syntra-bot/logs

[Install]
WantedBy=multi-user.target
```

**2. Создать директорию для логов:**

```bash
sudo mkdir -p /var/log/syntra-bot
sudo chown syntra:syntra /var/log/syntra-bot
```

**3. Запустить и включить сервис:**

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Запустить сервис
sudo systemctl start syntra-bot

# Проверить статус
sudo systemctl status syntra-bot

# Включить автозапуск
sudo systemctl enable syntra-bot

# Просмотр логов
sudo journalctl -u syntra-bot -f
```

**4. Управление сервисом:**

```bash
# Остановить
sudo systemctl stop syntra-bot

# Перезапустить
sudo systemctl restart syntra-bot

# Отключить автозапуск
sudo systemctl disable syntra-bot

# Просмотр логов (последние 100 строк)
sudo journalctl -u syntra-bot -n 100
```

---

## Docker деплой

### Docker Compose (рекомендуется)

**1. Создать docker-compose.yml:**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16
    container_name: syntra_postgres
    environment:
      POSTGRES_USER: syntra
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-syntra_password_change_me}
      POSTGRES_DB: syntra_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U syntra"]
      interval: 10s
      timeout: 5s
      retries: 5

  bot:
    build: .
    container_name: syntra_bot
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    command: python bot.py

volumes:
  postgres_data:
```

**2. Создать Dockerfile:**

```dockerfile
FROM python:3.12-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копирование requirements
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание директории для логов
RUN mkdir -p /app/logs

# Запуск бота
CMD ["python", "bot.py"]
```

**3. Создать .dockerignore:**

```
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache
.pytest_cache
.hypothesis
*.db
*.sqlite
.env
.DS_Store
```

**4. Запуск:**

```bash
# Билд и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down

# Остановка с удалением volumes
docker-compose down -v
```

**5. Применение миграций в Docker:**

```bash
# Зайти в контейнер
docker exec -it syntra_bot bash

# Применить миграции
alembic upgrade head

# Выйти
exit
```

---

## Мониторинг и обслуживание

### Логирование

**Структура логов:**

```
logs/
├── bot.log          # Основные логи
├── error.log        # Только ошибки
└── debug.log        # Debug логи (если LOG_LEVEL=DEBUG)
```

**Просмотр логов:**

```bash
# Последние 50 строк
tail -n 50 logs/bot.log

# Следить в реальном времени
tail -f logs/bot.log

# Поиск ошибок
grep -i error logs/bot.log

# Логи за сегодня
grep "$(date +%Y-%m-%d)" logs/bot.log
```

**Ротация логов (logrotate):**

```bash
# Создать конфигурацию
sudo nano /etc/logrotate.d/syntra-bot
```

```
/opt/syntra-bot/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    create 0640 syntra syntra
}
```

### Health Checks

**Проверка работы бота:**

```bash
# Проверка процесса
ps aux | grep bot.py

# Проверка подключения к БД
docker exec -it syntra_postgres psql -U syntra -d syntra_bot -c "SELECT COUNT(*) FROM users;"

# Проверка логов на ошибки
tail -n 100 logs/error.log
```

### Мониторинг расходов

**SQL запросы для мониторинга:**

```sql
-- Общие расходы за сегодня
SELECT
    service,
    SUM(cost) as total_cost,
    SUM(tokens) as total_tokens,
    COUNT(*) as requests
FROM cost_tracking
WHERE DATE(timestamp) = CURRENT_DATE
GROUP BY service;

-- Топ-10 пользователей по расходам
SELECT
    u.telegram_id,
    u.username,
    SUM(ct.cost) as total_cost
FROM users u
JOIN cost_tracking ct ON u.id = ct.user_id
WHERE DATE(ct.timestamp) = CURRENT_DATE
GROUP BY u.id, u.telegram_id, u.username
ORDER BY total_cost DESC
LIMIT 10;

-- Расходы за последние 7 дней
SELECT
    DATE(timestamp) as date,
    service,
    SUM(cost) as daily_cost
FROM cost_tracking
WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(timestamp), service
ORDER BY date DESC, service;
```

### Бэкапы базы данных

**Автоматический бэкап (cron):**

```bash
# Создать скрипт бэкапа
nano /opt/syntra-bot/scripts/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/syntra-bot/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/syntra_bot_$TIMESTAMP.sql"

mkdir -p $BACKUP_DIR

# Создать бэкап
docker exec syntra_postgres pg_dump -U syntra syntra_bot > $BACKUP_FILE

# Сжать
gzip $BACKUP_FILE

# Удалить бэкапы старше 7 дней
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup created: $BACKUP_FILE.gz"
```

```bash
# Сделать исполняемым
chmod +x /opt/syntra-bot/scripts/backup.sh

# Добавить в cron (каждый день в 3:00)
crontab -e
```

```cron
0 3 * * * /opt/syntra-bot/scripts/backup.sh >> /var/log/syntra-bot/backup.log 2>&1
```

**Восстановление из бэкапа:**

```bash
# Распаковать
gunzip syntra_bot_20231117_030000.sql.gz

# Восстановить
docker exec -i syntra_postgres psql -U syntra syntra_bot < syntra_bot_20231117_030000.sql
```

---

## Troubleshooting

### Проблема: Бот не запускается

**Проверка:**

```bash
# Проверить логи
tail -n 100 logs/bot.log

# Проверить конфигурацию
python -c "from config.config import validate_config; validate_config()"

# Проверить подключение к БД
python -c "
import asyncio
from src.database.engine import init_db
asyncio.run(init_db())
"
```

**Возможные причины:**

1. Неверный BOT_TOKEN
2. БД не запущена
3. Неверный DATABASE_URL
4. Отсутствуют зависимости

### Проблема: Ошибки OpenAI API

**Проверка:**

```bash
# Проверить API ключ
python -c "
from openai import OpenAI
client = OpenAI()
print(client.models.list())
"
```

**Возможные причины:**

1. Неверный OPENAI_API_KEY
2. Превышен rate limit
3. Недостаточно средств на аккаунте OpenAI
4. Проблемы с сетью

### Проблема: Бот не отвечает на сообщения

**Проверка:**

```bash
# Проверить middleware
grep -i "middleware" logs/bot.log

# Проверить лимиты запросов
docker exec -it syntra_postgres psql -U syntra -d syntra_bot -c "
SELECT * FROM request_limits WHERE date = CURRENT_DATE;
"

# Проверить подписку
docker exec -it syntra_postgres psql -U syntra -d syntra_bot -c "
SELECT telegram_id, username, is_subscribed FROM users;
"
```

**Возможные причины:**

1. Пользователь не подписан на канал
2. Превышен лимит запросов (5/день)
3. Бот не добавлен как админ в канал
4. Ошибка в middleware

### Проблема: Высокие расходы на API

**Анализ:**

```sql
-- Самые дорогие пользователи
SELECT
    u.telegram_id,
    u.username,
    SUM(ct.cost) as total_cost,
    COUNT(*) as requests,
    AVG(ct.tokens) as avg_tokens
FROM users u
JOIN cost_tracking ct ON u.id = ct.user_id
GROUP BY u.id
ORDER BY total_cost DESC
LIMIT 20;

-- Самые дорогие запросы
SELECT
    request_type,
    AVG(cost) as avg_cost,
    AVG(tokens) as avg_tokens,
    COUNT(*) as count
FROM cost_tracking
GROUP BY request_type
ORDER BY avg_cost DESC;
```

**Решения:**

1. Уменьшить max_tokens
2. Использовать gpt-4o-mini вместо gpt-4o
3. Увеличить порог для model routing
4. Ограничить длину контекста
5. Добавить платную подписку для пользователей

---

## Обновление бота

### Development

```bash
# Получить последние изменения
git pull

# Обновить зависимости
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Применить миграции
alembic upgrade head

# Перезапустить
# (убить процесс и запустить заново)
```

### Production (systemd)

```bash
# Остановить бота
sudo systemctl stop syntra-bot

# Обновить код
cd /opt/syntra-bot
git pull

# Обновить зависимости
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Применить миграции
alembic upgrade head

# Запустить бота
sudo systemctl start syntra-bot

# Проверить статус
sudo systemctl status syntra-bot
```

### Production (Docker)

```bash
# Остановить контейнеры
docker-compose down

# Получить обновления
git pull

# Пересобрать и запустить
docker-compose up -d --build

# Применить миграции
docker exec -it syntra_bot alembic upgrade head

# Проверить логи
docker-compose logs -f bot
```

---

## Security Best Practices

1. **Никогда не коммитить .env файл**
2. **Использовать strong passwords для БД**
3. **Ограничить доступ к PostgreSQL** (только localhost)
4. **Использовать HTTPS для webhook** (если используется)
5. **Регулярно обновлять зависимости**
6. **Мониторить логи на подозрительную активность**
7. **Использовать firewall** (ufw, iptables)
8. **Ограничить sudo доступ** для пользователя syntra

---

## Контакты и поддержка

Для вопросов по деплою обращайтесь к разработчикам проекта.

**Полезные ссылки:**
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [systemd Documentation](https://systemd.io/)
- [aiogram Documentation](https://docs.aiogram.dev/)
