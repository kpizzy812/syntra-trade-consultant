#!/bin/bash
# Frontend Deployment Script
# Деплой исправленного frontend на production сервер

set -e

echo "🚀 Starting frontend deployment..."

# 1. Проверяем что билд существует
if [ ! -d "frontend/.next" ]; then
    echo "❌ Build not found! Run 'npm run build' first"
    exit 1
fi

echo "✅ Build directory found"

# 2. Создаем архив
echo "📦 Creating deployment archive..."
cd frontend
tar -czf ../frontend-deploy.tar.gz .next/ public/ package.json package-lock.json
cd ..

echo "✅ Archive created: frontend-deploy.tar.gz"

# 3. Загружаем на сервер
echo "📤 Uploading to server..."
scp frontend-deploy.tar.gz kpeezy:/tmp/

echo "✅ Uploaded to server"

# 4. Деплоим на сервере
echo "🔄 Deploying on server..."
ssh kpeezy << 'EOF'
set -e

cd /root/syntraai/frontend

# Backup current build
if [ -d ".next" ]; then
    echo "📦 Backing up current build..."
    mv .next .next.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
fi

# Extract new build
echo "📦 Extracting new build..."
tar -xzf /tmp/frontend-deploy.tar.gz

# Restart frontend service
echo "🔄 Restarting frontend service..."
pm2 restart tradient-front

# Check status
echo "✅ Checking service status..."
pm2 info tradient-front | grep -E "status|uptime|restarts"

# Cleanup
rm /tmp/frontend-deploy.tar.gz

echo "✅ Deployment complete!"
EOF

echo ""
echo "🎉 Frontend deployed successfully!"
echo ""
echo "🔍 Check the app:"
echo "   https://ai.syntratrade.xyz/"
echo ""
echo "📊 Check logs:"
echo "   ssh kpeezy 'pm2 logs tradient-front --lines 50'"
