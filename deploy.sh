#!/bin/bash
set -e

echo "🚀 Деплой Syntra Mini App на ai.syntratrade.xyz"
echo ""

# Проверка что мы в правильной директории
if [ ! -f "bot.py" ]; then
    echo "❌ Ошибка: Запусти скрипт из корня проекта Syntra Trade Consultant"
    exit 1
fi

# Локальный билд фронтенда
echo "🏗️  Building frontend locally..."
cd frontend
echo "🗑️  Clearing Next.js cache..."
rm -rf .next
npm run build
cd ..
echo "✅ Frontend built successfully"
echo ""

# Загрузка на сервер
echo "📤 Uploading to server kpeezy:/root/syntraai/..."
echo ""

# Загрузить основные файлы (включая .next билд)
rsync -avz --progress \
  --exclude 'node_modules' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.venv' \
  --exclude 'backups' \
  --exclude 'logs' \
  --exclude 'cryptoai' \
  ./ kpeezy:/root/syntraai/

# Загрузить .env если существует
if [ -f ".env" ]; then
  echo "📦 Uploading .env file..."
  rsync -avz .env kpeezy:/root/syntraai/.env
fi

echo ""
echo "✅ Files uploaded successfully"
echo ""

# Рестарт на сервере (билд уже загружен)
echo "🔄 Installing deps and restarting on server..."
ssh kpeezy << 'EOF'
cd /root/syntraai

# Install/update Python dependencies
echo "📦 Installing Python dependencies..."
source .venv/bin/activate
pip install -r requirements.txt --quiet

# Install Node.js dependencies (без билда - он уже загружен)
echo "📦 Installing Node.js dependencies..."
cd frontend
npm install --quiet
cd ..

# Restart services
echo "🔄 Restarting systemd services..."
systemctl restart syntraai-api
systemctl restart syntraai-frontend
systemctl restart syntraai-bot

# Check status
echo ""
echo "📊 Services status:"
systemctl status syntraai-api --no-pager -l | head -n 3
systemctl status syntraai-frontend --no-pager -l | head -n 3
systemctl status syntraai-bot --no-pager -l | head -n 3
EOF

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 URLs:"
echo "   Frontend:    https://ai.syntratrade.xyz"
echo "   API Health:  https://ai.syntratrade.xyz/api/health"
echo "   Bot:         Telegram /start"
echo ""
echo "📝 Check logs:"
echo "   ssh kpeezy 'journalctl -u syntraai-api -f'"
echo "   ssh kpeezy 'journalctl -u syntraai-frontend -f'"
echo "   ssh kpeezy 'journalctl -u syntraai-bot -f'"
echo ""
