#!/bin/bash
# Syntra AI Mini App - Панель управления
# Деплой, сервисы, логи, бэкапы в одном месте

set -e

# Настройки
SERVER="kpeezy"
PROJECT_DIR="/var/www/syntraai"
BACKUP_DIR="./backups"

# Функция: заголовок
show_header() {
    clear
    echo "╔════════════════════════════════════════════════╗"
    echo "║    Syntra AI Mini App - Панель управления     ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""
}

# Функция: полный деплой
full_deploy() {
    show_header
    echo "🚀 Полный деплой (Локальный билд + Синк + Перезапуск)"
    echo ""

    # 1. Build frontend locally
    echo "🏗️  Building frontend locally..."
    cd frontend
    echo "🗑️  Clearing Next.js cache..."
    rm -rf .next
    npm run build
    cd ..
    echo "✅ Frontend built successfully"
    echo ""

    # 2. Sync files (including .next build)
    echo "📤 Syncing files to server..."

    rsync -avz --progress --delete \
      --exclude 'node_modules' \
      --exclude '.git' \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '.venv' \
      --exclude 'backups' \
      --exclude 'logs' \
      --exclude 'cryptoai' \
      --exclude 'frontend/.env.local' \
      ./ ${SERVER}:${PROJECT_DIR}/

    if [ -f ".env" ]; then
      rsync -avz .env ${SERVER}:${PROJECT_DIR}/.env
    fi

    echo "✓ Files synced"
    echo ""

    # 3. Install deps and restart on server (no build needed)
    echo "🔄 Installing dependencies and restarting on server..."
    ssh ${SERVER} << 'EOF'
set -e  # Exit immediately if any command fails
cd /var/www/syntraai

# Install Python dependencies
source .venv/bin/activate
pip install -r requirements.txt --quiet

# Run database migrations
echo "🗄️  Running database migrations..."
alembic upgrade head
echo "✅ Database migrations completed"

# Install Node.js dependencies (no build - already uploaded)
cd frontend

# CRITICAL: Remove .env.local to prevent localhost:8003 issue
echo "🗑️  Removing .env.local (if exists)..."
rm -f .env.local .env.local.backup

echo "📦 Installing Node.js dependencies..."
npm install --quiet

# Fix permissions for .next directory (allow read access)
chmod -R 755 .next
echo "✅ Fixed permissions for .next directory"

cd ..

# Restart services
echo "🔄 Restarting services..."
systemctl restart syntraai-api
systemctl restart syntraai-frontend
systemctl restart syntraai-bot

# Wait for services to start
sleep 3
EOF

    echo "✓ Dependencies installed and services restarted"
    echo ""

    # 3. Check status
    echo "📊 Services status:"
    ssh ${SERVER} << 'EOF'
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
}

# Функция: старт сервисов
start_services() {
    show_header
    echo "▶️  Запуск всех сервисов"
    echo ""

    ssh ${SERVER} 'systemctl start syntraai-api syntraai-frontend syntraai-bot'

    echo "✓ Сервисы запущены"
    sleep 2
    service_status
}

# Функция: стоп сервисов
stop_services() {
    show_header
    echo "⏹️  Остановка всех сервисов"
    echo ""

    ssh ${SERVER} 'systemctl stop syntraai-api syntraai-frontend syntraai-bot'

    echo "✓ Сервисы остановлены"
    sleep 2
}

# Функция: перезапуск сервисов
restart_services() {
    show_header
    echo "🔄 Перезапуск всех сервисов"
    echo ""

    ssh ${SERVER} 'systemctl restart syntraai-api syntraai-frontend syntraai-bot'

    echo "✓ Сервисы перезапущены"
    sleep 2
    service_status
}

# Функция: статус сервисов
service_status() {
    show_header
    echo "📊 Статус сервисов"
    echo ""

    ssh ${SERVER} << 'EOF'
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "API (порт 8003):"
systemctl status syntraai-api --no-pager -l | head -n 5
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Frontend (порт 3003):"
systemctl status syntraai-frontend --no-pager -l | head -n 5
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Bot:"
systemctl status syntraai-bot --no-pager -l | head -n 5
EOF

    echo ""
}

# Функция: логи
view_logs() {
    show_header
    echo "📝 Просмотр логов"
    echo ""
    echo "Выберите сервис:"
    echo "  1) API (application logs)"
    echo "  2) API (errors only)"
    echo "  3) Frontend (application logs)"
    echo "  4) Frontend (errors only)"
    echo "  5) Bot (application logs)"
    echo "  6) Bot (errors only)"
    echo "  7) Все логи (combined)"
    echo "  0) Назад"
    echo ""
    read -p "Выбор: " log_choice

    case $log_choice in
        1)
            echo "Логи API (последние 500 строк + live, Ctrl+C для выхода):"
            ssh ${SERVER} 'tail -n 500 -f /var/log/syntraai-api.log'
            ;;
        2)
            echo "Ошибки API (последние 500 строк + live, Ctrl+C для выхода):"
            ssh ${SERVER} 'tail -n 500 -f /var/log/syntraai-api-error.log'
            ;;
        3)
            echo "Логи Frontend (последние 500 строк + live, Ctrl+C для выхода):"
            ssh ${SERVER} 'tail -n 500 -f /var/log/syntraai-frontend.log'
            ;;
        4)
            echo "Ошибки Frontend (последние 500 строк + live, Ctrl+C для выхода):"
            ssh ${SERVER} 'tail -n 500 -f /var/log/syntraai-frontend-error.log'
            ;;
        5)
            echo "Логи Bot (последние 500 строк + live, Ctrl+C для выхода):"
            ssh ${SERVER} 'tail -n 500 -f /var/log/syntraai-bot.log'
            ;;
        6)
            echo "Ошибки Bot (последние 500 строк + live, Ctrl+C для выхода):"
            ssh ${SERVER} 'tail -n 500 -f /var/log/syntraai-bot-error.log'
            ;;
        7)
            echo "Все логи в хронологическом порядке (последние 500 строк + live, Ctrl+C для выхода):"
            ssh ${SERVER} << 'LOGSEOF'
# Показываем последние 500 строк из всех логов, сортируя по времени
for log in /var/log/syntraai-*.log; do
    tail -n 500 "$log" | awk -v file="$(basename $log)" '{print $1, $2, file, $0}'
done | sort -k1,2 | cut -d" " -f3- | tail -n 500

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 LIVE MODE - новые логи появляются ниже"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Следим за всеми логами в live режиме
tail -f /var/log/syntraai-*.log 2>/dev/null | while read line; do
    if [[ $line == "==>"* ]]; then
        # Это разделитель файла, показываем его красиво
        file=$(echo "$line" | sed 's/==> \(.*\) <==/[\1]/')
        echo -e "\n\033[1;36m$file\033[0m"
    else
        # Обычная строка лога
        echo "$line"
    fi
done
LOGSEOF
            ;;
        0)
            return
            ;;
        *)
            echo "❌ Неверный выбор"
            sleep 2
            ;;
    esac
}

# Функция: бэкап базы данных
backup_database() {
    show_header
    echo "💾 Бэкап базы данных"
    echo ""

    # Создать директорию для бэкапов
    mkdir -p ${BACKUP_DIR}

    # Имя файла с датой
    BACKUP_FILE="syntraai_backup_$(date +%Y%m%d_%H%M%S).sql"

    echo "Creating database dump..."

    # Создать дамп на сервере
    ssh ${SERVER} << EOF
cd /var/www/syntraai
source .venv/bin/activate

# Получить DATABASE_URL из .env
DB_URL=\$(grep "^DATABASE_URL=" .env | cut -d '=' -f2)

# Парсим URL (postgresql+asyncpg://user:pass@host:port/dbname)
DB_USER=\$(echo \$DB_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
DB_PASS=\$(echo \$DB_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_HOST=\$(echo \$DB_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=\$(echo \$DB_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=\$(echo \$DB_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

# Создать дамп
PGPASSWORD=\$DB_PASS pg_dump -h \$DB_HOST -p \$DB_PORT -U \$DB_USER \$DB_NAME > /tmp/${BACKUP_FILE}

echo "✓ Dump created: /tmp/${BACKUP_FILE}"
EOF

    # Скачать дамп
    echo "Downloading backup..."
    scp ${SERVER}:/tmp/${BACKUP_FILE} ${BACKUP_DIR}/

    # Удалить временный файл на сервере
    ssh ${SERVER} "rm /tmp/${BACKUP_FILE}"

    # Размер файла
    BACKUP_SIZE=$(du -h ${BACKUP_DIR}/${BACKUP_FILE} | cut -f1)

    echo ""
    echo "✅ Бэкап завершен!"
    echo "Файл: ${BACKUP_DIR}/${BACKUP_FILE}"
    echo "Размер: ${BACKUP_SIZE}"
    echo ""

    # Показать все бэкапы
    echo "Все бэкапы:"
    ls -lh ${BACKUP_DIR}/*.sql 2>/dev/null || echo "Нет бэкапов"
    echo ""
}

# Функция: быстрый синк (без билда)
quick_sync() {
    show_header
    echo "⚡ Быстрый синк (без билда)"
    echo ""

    echo "📤 Syncing code..."

    rsync -avz --progress --delete \
      --exclude 'node_modules' \
      --exclude '.git' \
      --exclude '.next' \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '.venv' \
      --exclude 'logs' \
      --exclude 'cryptoai' \
      --exclude 'backups' \
      --exclude 'frontend/.env.local' \
      ./ ${SERVER}:${PROJECT_DIR}/

    if [ -f ".env" ]; then
      rsync -avz .env ${SERVER}:${PROJECT_DIR}/.env
    fi

    echo "✓ Code synced"
    echo ""

    read -p "Перезапустить сервисы? (y/n): " restart_choice
    if [ "$restart_choice" = "y" ]; then
        restart_services
    fi
}

# Функция: пересборка фронтенда с очисткой кэша
rebuild_frontend() {
    show_header
    echo "🏗️  Пересборка фронтенда (локальный билд)"
    echo ""

    # 1. Build locally
    echo "🏗️  Building frontend locally..."
    cd frontend
    echo "🗑️  Clearing Next.js cache..."
    rm -rf .next
    rm -rf node_modules/.cache
    npm run build
    cd ..
    echo "✅ Frontend built successfully"
    echo ""

    # 2. Sync frontend (including .next)
    echo "📤 Syncing frontend to server..."
    rsync -avz --progress --delete \
      --exclude 'node_modules' \
      --exclude 'logs' \
      --exclude '.env.local' \
      ./frontend/ ${SERVER}:${PROJECT_DIR}/frontend/

    echo "✓ Frontend synced"
    echo ""

    # 3. Install deps and restart on server
    echo "🔄 Installing deps and restarting frontend..."
    ssh ${SERVER} << 'EOF'
set -e
cd /var/www/syntraai/frontend

# CRITICAL: Remove .env.local to prevent localhost:8003 issue
echo "🗑️  Removing .env.local (if exists)..."
rm -f .env.local .env.local.backup

# Install dependencies
echo "📦 Installing dependencies..."
npm install --quiet

# Fix permissions
chmod -R 755 .next
echo "✅ Permissions fixed"

# Restart only frontend service
echo "🔄 Restarting frontend service..."
systemctl restart syntraai-frontend

# Wait for service to start
sleep 2

# Check status
echo ""
echo "📊 Frontend service status:"
systemctl status syntraai-frontend --no-pager -l | head -n 3
EOF

    echo ""
    echo "✅ Frontend rebuild complete!"
    echo "🌐 Check: https://ai.syntratrade.xyz"
    echo ""
}

# Главное меню
main_menu() {
    while true; do
        show_header
        echo "Выберите действие:"
        echo ""
        echo "  ДЕПЛОЙ:"
        echo "    1) 🚀 Полный деплой (Билд + Синк + Перезапуск)"
        echo "    2) ⚡ Быстрый синк (только код, без билда)"
        echo "    3) 🏗️  Пересборка фронтенда (с очисткой кэша)"
        echo ""
        echo "  СЕРВИСЫ:"
        echo "    4) ▶️  Запустить все сервисы"
        echo "    5) ⏹️  Остановить все сервисы"
        echo "    6) 🔄 Перезапустить все сервисы"
        echo "    7) 📊 Статус сервисов"
        echo ""
        echo "  МОНИТОРИНГ:"
        echo "    8) 📝 Просмотр логов"
        echo ""
        echo "  БЭКАП:"
        echo "    9) 💾 Бэкап базы данных"
        echo ""
        echo "    0) ❌ Выход"
        echo ""
        read -p "Ваш выбор: " choice

        case $choice in
            1) full_deploy; read -p "Нажмите Enter для продолжения..." ;;
            2) quick_sync; read -p "Нажмите Enter для продолжения..." ;;
            3) rebuild_frontend; read -p "Нажмите Enter для продолжения..." ;;
            4) start_services; read -p "Нажмите Enter для продолжения..." ;;
            5) stop_services; read -p "Нажмите Enter для продолжения..." ;;
            6) restart_services; read -p "Нажмите Enter для продолжения..." ;;
            7) service_status; read -p "Нажмите Enter для продолжения..." ;;
            8) view_logs ;;
            9) backup_database; read -p "Нажмите Enter для продолжения..." ;;
            0)
                echo "До встречи!"
                exit 0
                ;;
            *)
                echo "❌ Неверный выбор"
                sleep 1
                ;;
        esac
    done
}

# Запуск
main_menu
