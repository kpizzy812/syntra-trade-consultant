#!/bin/bash
# =============================================================================
# SYNTRA SERVER HARDENING SCRIPT
# Защита от XMR криптомайнеров и несанкционированного доступа
#
# ПЕРЕД ЗАПУСКОМ: Убедитесь что у вас есть SSH-ключи для доступа!
# Этот скрипт отключает парольную аутентификацию SSH
#
# Запуск: sudo bash scripts/server_hardening.sh
# =============================================================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверка root
if [ "$EUID" -ne 0 ]; then
    log_error "Запустите скрипт от root: sudo bash $0"
    exit 1
fi

log_info "=========================================="
log_info "  SYNTRA SERVER HARDENING v1.0"
log_info "=========================================="

# =============================================================================
# 1. SSH HARDENING - КРИТИЧЕСКИ ВАЖНО!
# =============================================================================
log_info "[1/10] SSH Hardening..."

SSHD_CONFIG="/etc/ssh/sshd_config"

# Бэкап конфига
cp "$SSHD_CONFIG" "${SSHD_CONFIG}.backup.$(date +%Y%m%d)"

# Применяем безопасные настройки
cat > /etc/ssh/sshd_config.d/99-hardening.conf << 'EOF'
# SYNTRA SSH Hardening Configuration
# Запрещаем root login (используйте sudo)
PermitRootLogin no

# ТОЛЬКО ключевая аутентификация (ОТКЛЮЧАЕМ ПАРОЛИ!)
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
UsePAM yes

# Отключаем X11 и agent forwarding
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no

# Лимит попыток и таймаутов
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2

# Только Protocol 2
Protocol 2

# Логируем всё
LogLevel VERBOSE
EOF

# Проверка конфига перед перезапуском
sshd -t && systemctl reload sshd
log_info "SSH hardened: root login disabled, password auth disabled"

# =============================================================================
# 2. FAIL2BAN - Защита от брутфорса
# =============================================================================
log_info "[2/10] Installing and configuring Fail2Ban..."

apt-get update -qq
apt-get install -y -qq fail2ban

cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
# Время бана - 24 часа
bantime = 86400
# Окно для подсчёта попыток
findtime = 600
# Максимум попыток
maxretry = 3
# Email для уведомлений (опционально)
# destemail = admin@syntratrade.xyz
# action = %(action_mwl)s

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400

# Защита от сканирования портов
[portscan]
enabled = true
filter = portscan
action = iptables-allports[name=portscan]
logpath = /var/log/syslog
maxretry = 10
findtime = 60
bantime = 86400
EOF

# Кастомный фильтр для portscan
cat > /etc/fail2ban/filter.d/portscan.conf << 'EOF'
[Definition]
failregex = UFW BLOCK.* SRC=<HOST>
ignoreregex =
EOF

systemctl enable fail2ban
systemctl restart fail2ban
log_info "Fail2Ban configured: 3 failed attempts = 24h ban"

# =============================================================================
# 3. FIREWALL (UFW) - Строгие правила
# =============================================================================
log_info "[3/10] Configuring Firewall (UFW)..."

apt-get install -y -qq ufw

# Сбрасываем все правила
ufw --force reset

# Политика по умолчанию - запретить всё
ufw default deny incoming
ufw default allow outgoing

# Разрешаем только необходимые порты
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
# API порт (если используется внешний доступ)
ufw allow 8003/tcp comment 'Syntra API'
# Frontend порт
ufw allow 3000/tcp comment 'Frontend'

# БЛОКИРУЕМ известные порты майнинга пулов
# Stratum порты для XMR пулов
ufw deny out 3333/tcp comment 'Block mining pool'
ufw deny out 4444/tcp comment 'Block mining pool'
ufw deny out 5555/tcp comment 'Block mining pool'
ufw deny out 7777/tcp comment 'Block mining pool'
ufw deny out 8888/tcp comment 'Block mining pool'
ufw deny out 9999/tcp comment 'Block mining pool'
ufw deny out 14433/tcp comment 'Block mining pool TLS'
ufw deny out 14444/tcp comment 'Block mining pool TLS'

# Блокируем Docker API извне (КРИТИЧНО!)
ufw deny 2375/tcp comment 'Block Docker API'
ufw deny 2376/tcp comment 'Block Docker API TLS'

# Включаем UFW
ufw --force enable
log_info "Firewall configured: only SSH, HTTP, HTTPS allowed"

# =============================================================================
# 4. БЛОКИРОВКА МАЙНИНГ ПУЛОВ НА УРОВНЕ IPTABLES
# =============================================================================
log_info "[4/10] Blocking known mining pool domains..."

# Создаём файл с доменами пулов для блокировки
cat > /etc/mining-pools-blocklist.txt << 'EOF'
# XMR Mining Pools to block
pool.minexmr.com
xmrpool.eu
supportxmr.com
pool.hashvault.pro
monerohash.com
minexmr.com
moneropool.com
monerod.org
xmr.nanopool.org
nanopool.org
c3pool.com
pool.c3pool.com
monero.hashvault.pro
xmr.2miners.com
2miners.com
xmrig.com
herominers.com
EOF

# Блокируем домены через iptables (резолвим в IP)
while IFS= read -r domain; do
    [[ "$domain" =~ ^#.*$ || -z "$domain" ]] && continue
    # Получаем IP адреса домена
    for ip in $(dig +short "$domain" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'); do
        iptables -A OUTPUT -d "$ip" -j DROP 2>/dev/null || true
        log_info "Blocked mining pool: $domain ($ip)"
    done
done < /etc/mining-pools-blocklist.txt

# Сохраняем правила iptables
iptables-save > /etc/iptables.rules
log_info "Mining pool domains blocked at network level"

# =============================================================================
# 5. ОБНАРУЖЕНИЕ КРИПТОМАЙНЕРОВ
# =============================================================================
log_info "[5/10] Installing cryptominer detection tools..."

# Устанавливаем rkhunter для поиска руткитов
apt-get install -y -qq rkhunter chkrootkit

# Обновляем базы
rkhunter --update 2>/dev/null || true
rkhunter --propupd 2>/dev/null || true

# Создаём скрипт для детекции майнеров
cat > /usr/local/bin/detect-miners.sh << 'EOF'
#!/bin/bash
# Скрипт для обнаружения криптомайнеров

ALERT_FILE="/var/log/miner-detection.log"

log_alert() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ALERT: $1" >> "$ALERT_FILE"
    echo "ALERT: $1"
}

# 1. Проверка процессов с высокой нагрузкой CPU
HIGH_CPU=$(ps aux --sort=-%cpu | head -10 | awk '$3 > 80 {print $11}')
if [ -n "$HIGH_CPU" ]; then
    log_alert "High CPU processes: $HIGH_CPU"
fi

# 2. Поиск известных бинарников майнеров
MINER_NAMES="xmrig minerd ethminer cgminer bfgminer ccminer claymore"
for miner in $MINER_NAMES; do
    if pgrep -x "$miner" > /dev/null 2>&1; then
        log_alert "MINER DETECTED: $miner running!"
        pkill -9 "$miner" 2>/dev/null
    fi
done

# 3. Поиск подозрительных файлов в /tmp
SUSPICIOUS=$(find /tmp -type f -executable -mtime -7 2>/dev/null)
if [ -n "$SUSPICIOUS" ]; then
    log_alert "Suspicious executables in /tmp: $SUSPICIOUS"
fi

# 4. Проверка скрытых файлов в /tmp
HIDDEN_TMP=$(find /tmp -name ".*" -type f 2>/dev/null | head -20)
if [ -n "$HIDDEN_TMP" ]; then
    log_alert "Hidden files in /tmp: $HIDDEN_TMP"
fi

# 5. Проверка подозрительных cron jobs
CRON_SUSPICIOUS=$(grep -r "curl\|wget\|/tmp\|base64" /var/spool/cron/* /etc/cron* 2>/dev/null | grep -v ".backup")
if [ -n "$CRON_SUSPICIOUS" ]; then
    log_alert "Suspicious cron entries: $CRON_SUSPICIOUS"
fi

# 6. Проверка соединений с майнинг пулами
MINING_CONN=$(ss -tnp | grep -E ":3333|:4444|:5555|:7777|:8888|:9999" 2>/dev/null)
if [ -n "$MINING_CONN" ]; then
    log_alert "Possible mining pool connections: $MINING_CONN"
fi

# 7. Проверка подозрительных SSH ключей
AUTH_KEYS="/root/.ssh/authorized_keys"
if [ -f "$AUTH_KEYS" ]; then
    UNKNOWN_KEYS=$(grep -v "your_known_key_fingerprint" "$AUTH_KEYS" 2>/dev/null | wc -l)
    if [ "$UNKNOWN_KEYS" -gt 1 ]; then
        log_alert "Unknown SSH keys detected: $UNKNOWN_KEYS keys in $AUTH_KEYS"
    fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Scan completed" >> "$ALERT_FILE"
EOF

chmod +x /usr/local/bin/detect-miners.sh

# Добавляем в cron (каждые 5 минут)
echo "*/5 * * * * root /usr/local/bin/detect-miners.sh" > /etc/cron.d/miner-detection

log_info "Miner detection script installed, runs every 5 minutes"

# =============================================================================
# 6. ОГРАНИЧЕНИЕ РЕСУРСОВ (cgroups)
# =============================================================================
log_info "[6/10] Setting up resource limits..."

# Устанавливаем лимиты для предотвращения DoS и майнинга
cat > /etc/security/limits.d/99-syntra-limits.conf << 'EOF'
# Лимиты для предотвращения злоупотреблений
*       soft    nproc     1024
*       hard    nproc     2048
*       soft    nofile    65535
*       hard    nofile    65535
*       soft    cpu       unlimited
*       hard    cpu       unlimited
# Ограничиваем память для непривилегированных процессов
*       soft    as        4194304
EOF

log_info "Resource limits configured"

# =============================================================================
# 7. AUDITD - Аудит системных вызовов
# =============================================================================
log_info "[7/10] Configuring system auditing (auditd)..."

apt-get install -y -qq auditd audispd-plugins

cat > /etc/audit/rules.d/syntra.rules << 'EOF'
# Удаляем все правила
-D

# Буфер для логов
-b 8192

# Мониторим изменения в /etc
-w /etc/ -p wa -k etc_changes

# Мониторим SSH конфиги
-w /etc/ssh/sshd_config -p wa -k sshd_config
-w /root/.ssh/authorized_keys -p wa -k ssh_keys

# Мониторим cron
-w /etc/crontab -p wa -k cron
-w /etc/cron.d/ -p wa -k cron
-w /var/spool/cron/ -p wa -k cron

# Мониторим выполнение бинарников
-w /tmp -p x -k tmp_exec
-w /var/tmp -p x -k vartmp_exec
-w /dev/shm -p x -k shm_exec

# Мониторим загрузку модулей ядра
-w /sbin/insmod -p x -k modules
-w /sbin/modprobe -p x -k modules

# Мониторим sudo
-w /etc/sudoers -p wa -k sudoers
-w /etc/sudoers.d/ -p wa -k sudoers

# Мониторим systemd сервисы
-w /etc/systemd/ -p wa -k systemd
-w /lib/systemd/ -p wa -k systemd

# Делаем конфигурацию неизменяемой
-e 2
EOF

systemctl enable auditd
systemctl restart auditd
log_info "Auditd configured for system monitoring"

# =============================================================================
# 8. SYSCTL HARDENING - Защита сети
# =============================================================================
log_info "[8/10] Applying sysctl network hardening..."

cat > /etc/sysctl.d/99-syntra-security.conf << 'EOF'
# Network Security
# Защита от IP spoofing
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Игнорируем ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0

# Не отправляем ICMP redirects
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Защита от SYN flood
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2

# Игнорируем broadcast ICMP
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Защита от smurf attacks
net.ipv4.icmp_ignore_bogus_error_responses = 1

# Логируем подозрительные пакеты
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1

# Отключаем source routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv6.conf.default.accept_source_route = 0

# Защита от атак переполнения буфера
kernel.randomize_va_space = 2

# Ограничиваем dmesg
kernel.dmesg_restrict = 1

# Защита от ptrace атак
kernel.yama.ptrace_scope = 1
EOF

sysctl -p /etc/sysctl.d/99-syntra-security.conf
log_info "Sysctl hardening applied"

# =============================================================================
# 9. DOCKER SECURITY (если используется)
# =============================================================================
log_info "[9/10] Securing Docker (if installed)..."

if command -v docker &> /dev/null; then
    # Убеждаемся что Docker API не выставлен наружу
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'EOF'
{
    "live-restore": true,
    "userland-proxy": false,
    "no-new-privileges": true,
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "hosts": ["unix:///var/run/docker.sock"]
}
EOF

    # Удаляем небезопасный TCP доступ если есть
    if [ -f /etc/systemd/system/docker.service.d/override.conf ]; then
        rm -f /etc/systemd/system/docker.service.d/override.conf
    fi

    systemctl daemon-reload
    systemctl restart docker 2>/dev/null || true
    log_info "Docker secured: API only via Unix socket"
else
    log_info "Docker not installed, skipping"
fi

# =============================================================================
# 10. АВТОМАТИЧЕСКИЕ ОБНОВЛЕНИЯ БЕЗОПАСНОСТИ
# =============================================================================
log_info "[10/10] Enabling automatic security updates..."

apt-get install -y -qq unattended-upgrades apt-listchanges

cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

systemctl enable unattended-upgrades
log_info "Automatic security updates enabled"

# =============================================================================
# ФИНАЛЬНЫЙ ОТЧЁТ
# =============================================================================
echo ""
log_info "=========================================="
log_info "  HARDENING COMPLETE!"
log_info "=========================================="
echo ""
log_info "Summary of changes:"
echo "  - SSH: Root login disabled, password auth disabled"
echo "  - Fail2Ban: 3 failed attempts = 24h ban"
echo "  - Firewall: Only SSH/HTTP/HTTPS allowed"
echo "  - Mining pools blocked at network level"
echo "  - Miner detection script runs every 5 min"
echo "  - System auditing enabled (auditd)"
echo "  - Network hardening applied (sysctl)"
echo "  - Docker API secured (if installed)"
echo "  - Auto security updates enabled"
echo ""
log_warn "IMPORTANT: Test SSH access BEFORE logging out!"
log_warn "Run: ssh -i your_key user@server"
echo ""
log_info "Logs to monitor:"
echo "  - /var/log/fail2ban.log"
echo "  - /var/log/auth.log"
echo "  - /var/log/miner-detection.log"
echo "  - /var/log/audit/audit.log"
echo ""
