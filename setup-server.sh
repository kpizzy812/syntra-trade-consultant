#!/bin/bash
# Скрипт для первоначальной настройки ai.syntratrade.xyz на сервере
# Запускать на СЕРВЕРЕ (ssh syntra), а не локально!

set -e

echo "🚀 Настройка ai.syntratrade.xyz на сервере"
echo ""

# Проверка что мы на сервере
if [ ! -d "/root" ]; then
    echo "❌ Этот скрипт нужно запускать на сервере (ssh syntra)"
    exit 1
fi

# 1. Создание директории
echo "📁 Создание директории /root/syntraai..."
mkdir -p /root/syntraai
cd /root/syntraai

# 2. Python venv
echo "🐍 Создание Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# 3. Создать директорию для certbot
echo "🔒 Создание директории для certbot..."
mkdir -p /var/www/certbot

# 4. Создать лог файлы
echo "📝 Создание лог файлов..."
touch /var/log/syntra-api.log
touch /var/log/syntra-api-error.log
touch /var/log/syntra-frontend.log
touch /var/log/syntra-frontend-error.log
touch /var/log/syntra-bot.log
touch /var/log/syntra-bot-error.log

# 5. Проверка Node.js
echo "📦 Проверка Node.js..."
if ! command -v node &> /dev/null; then
    echo "⚠️  Node.js не установлен! Устанавливаю..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs
fi

NODE_VERSION=$(node -v)
echo "✅ Node.js установлен: $NODE_VERSION"

# 6. Проверка nginx
echo "🌐 Проверка nginx..."
if ! command -v nginx &> /dev/null; then
    echo "⚠️  Nginx не установлен! Устанавливаю..."
    apt update
    apt install -y nginx
fi

# 7. Проверка certbot
echo "🔒 Проверка certbot..."
if ! command -v certbot &> /dev/null; then
    echo "⚠️  Certbot не установлен! Устанавливаю..."
    apt install -y certbot python3-certbot-nginx
fi

echo ""
echo "✅ Базовая настройка сервера завершена!"
echo ""
echo "📋 Следующие шаги:"
echo ""
echo "1. Добавь A-запись в DNS:"
echo "   Type: A"
echo "   Name: ai"
echo "   Value: $(curl -s ifconfig.me)"
echo ""
echo "2. Дождись обновления DNS (5-10 минут)"
echo "   Проверить: ping ai.syntratrade.xyz"
echo ""
echo "3. Загрузи код через deploy.sh с локальной машины:"
echo "   ./deploy.sh"
echo ""
echo "4. После загрузки кода, вернись на сервер и:"
echo "   - Создай .env файл: nano /root/syntraai/.env"
echo "   - Установи nginx конфиг"
echo "   - Получи SSL сертификат"
echo "   - Создай systemd сервисы"
echo ""
echo "Подробная инструкция: /root/syntraai/docs/DEPLOYMENT_GUIDE.md"
echo ""
