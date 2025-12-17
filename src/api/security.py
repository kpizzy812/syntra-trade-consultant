# coding: utf-8
"""
Security Module for Syntra API

Provides security middleware, input validation, and protection against common attacks:
- Rate limiting enhancements
- Request validation
- IP blocking
- Suspicious activity detection
- Input sanitization
"""

import os
import re
import hashlib
import ipaddress
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Set, Tuple
from collections import defaultdict
import asyncio

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


# =============================================================================
# CONFIGURATION
# =============================================================================

# Максимум запросов за период (per IP)
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
MAX_REQUESTS_PER_HOUR = int(os.getenv("MAX_REQUESTS_PER_HOUR", "1000"))

# Автоматический бан после N подозрительных действий
SUSPICIOUS_ACTIONS_THRESHOLD = int(os.getenv("SUSPICIOUS_ACTIONS_THRESHOLD", "10"))

# Время бана (в секундах)
BAN_DURATION_SECONDS = int(os.getenv("BAN_DURATION_SECONDS", "3600"))  # 1 hour

# Whitelisted IPs (не блокируются)
WHITELISTED_IPS: Set[str] = set(
    os.getenv("WHITELISTED_IPS", "127.0.0.1,::1").split(",")
)

# Блокированные User-Agents (боты, сканеры)
BLOCKED_USER_AGENTS = [
    "sqlmap",
    "nikto",
    "nmap",
    "masscan",
    "zgrab",
    "gobuster",
    "dirbuster",
    "wfuzz",
    "hydra",
    "metasploit",
    "burp",
    "nuclei",
    "acunetix",
    "nessus",
    "openvas",
]

# Подозрительные паттерны в URL/query
SUSPICIOUS_PATTERNS = [
    r"\.\.\/",  # Path traversal
    r"etc/passwd",
    r"etc/shadow",
    r"/proc/",
    r"<script",  # XSS
    r"javascript:",
    r"onerror=",
    r"onload=",
    r"UNION\s+SELECT",  # SQL injection
    r"SELECT\s+.*\s+FROM",
    r"INSERT\s+INTO",
    r"DROP\s+TABLE",
    r"UPDATE\s+.*\s+SET",
    r"DELETE\s+FROM",
    r"--\s*$",  # SQL comment
    r";\s*DROP",
    r"OR\s+1\s*=\s*1",
    r"AND\s+1\s*=\s*1",
    r"\${",  # Template injection
    r"{{",
    r"%{",
    r"eval\(",  # Code injection
    r"exec\(",
    r"system\(",
    r"__import__",
    r"subprocess",
    r"os\.system",
    r"base64_decode",  # PHP injection
    r"<?php",
    r"<%",
    r"cmd\.exe",  # OS command injection
    r"/bin/sh",
    r"/bin/bash",
    r"\|.*cat\s",
    r";\s*ls\s",
    r";\s*wget\s",
    r";\s*curl\s",
]

# Компилируем паттерны для производительности
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


# =============================================================================
# IN-MEMORY STORAGE (для production использовать Redis)
# =============================================================================

class SecurityStorage:
    """
    In-memory storage for rate limiting and IP tracking.
    For production, replace with Redis for distributed systems.
    """

    def __init__(self):
        self.request_counts: Dict[str, list] = defaultdict(list)  # IP -> [timestamps]
        self.suspicious_counts: Dict[str, int] = defaultdict(int)  # IP -> count
        self.banned_ips: Dict[str, datetime] = {}  # IP -> ban_until
        self.lock = asyncio.Lock()

    async def add_request(self, ip: str) -> Tuple[int, int]:
        """Add request and return (requests_last_minute, requests_last_hour)"""
        now = datetime.now(UTC)

        async with self.lock:
            # Удаляем старые записи
            self.request_counts[ip] = [
                ts for ts in self.request_counts[ip]
                if now - ts < timedelta(hours=1)
            ]

            # Добавляем новый запрос
            self.request_counts[ip].append(now)

            # Считаем запросы
            minute_ago = now - timedelta(minutes=1)
            requests_minute = sum(1 for ts in self.request_counts[ip] if ts > minute_ago)
            requests_hour = len(self.request_counts[ip])

            return requests_minute, requests_hour

    async def add_suspicious_action(self, ip: str) -> int:
        """Add suspicious action and return total count"""
        async with self.lock:
            self.suspicious_counts[ip] += 1
            return self.suspicious_counts[ip]

    async def ban_ip(self, ip: str, duration_seconds: int = BAN_DURATION_SECONDS):
        """Ban IP for specified duration"""
        async with self.lock:
            self.banned_ips[ip] = datetime.now(UTC) + timedelta(seconds=duration_seconds)
            logger.warning(f"IP {ip} banned for {duration_seconds} seconds")

    async def is_banned(self, ip: str) -> bool:
        """Check if IP is banned"""
        async with self.lock:
            if ip not in self.banned_ips:
                return False

            if datetime.now(UTC) > self.banned_ips[ip]:
                # Бан истёк
                del self.banned_ips[ip]
                self.suspicious_counts[ip] = 0  # Сбрасываем счётчик
                return False

            return True

    async def cleanup(self):
        """Периодическая очистка старых данных"""
        async with self.lock:
            now = datetime.now(UTC)
            hour_ago = now - timedelta(hours=1)

            # Очищаем старые запросы
            for ip in list(self.request_counts.keys()):
                self.request_counts[ip] = [
                    ts for ts in self.request_counts[ip]
                    if ts > hour_ago
                ]
                if not self.request_counts[ip]:
                    del self.request_counts[ip]

            # Очищаем истёкшие баны
            for ip in list(self.banned_ips.keys()):
                if now > self.banned_ips[ip]:
                    del self.banned_ips[ip]
                    if ip in self.suspicious_counts:
                        del self.suspicious_counts[ip]


# Глобальное хранилище
security_storage = SecurityStorage()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_client_ip(request: Request) -> str:
    """
    Extract real client IP from request.
    Handles proxies (X-Forwarded-For, X-Real-IP).
    """
    # X-Forwarded-For может содержать цепочку прокси
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Берём первый IP (оригинальный клиент)
        ip = forwarded_for.split(",")[0].strip()
        return ip

    # X-Real-IP (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Direct connection
    if request.client:
        return request.client.host

    return "unknown"


def is_private_ip(ip: str) -> bool:
    """Check if IP is private/local"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback
    except ValueError:
        return False


def check_user_agent(user_agent: Optional[str]) -> bool:
    """
    Check if User-Agent is suspicious.
    Returns True if suspicious.
    """
    if not user_agent:
        return False  # Missing UA - allow but monitor

    ua_lower = user_agent.lower()
    for blocked in BLOCKED_USER_AGENTS:
        if blocked in ua_lower:
            return True

    return False


def check_suspicious_content(content: str) -> Tuple[bool, Optional[str]]:
    """
    Check content for suspicious patterns.
    Returns (is_suspicious, matched_pattern).
    """
    if not content:
        return False, None

    for pattern in COMPILED_PATTERNS:
        match = pattern.search(content)
        if match:
            return True, match.group(0)

    return False, None


def sanitize_log_content(content: str, max_length: int = 200) -> str:
    """Sanitize content for logging (prevent log injection)"""
    if not content:
        return ""

    # Удаляем управляющие символы
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)

    # Обрезаем
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."

    return sanitized


# =============================================================================
# SECURITY MIDDLEWARE
# =============================================================================

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security middleware for FastAPI.

    Features:
    - Rate limiting (per IP)
    - IP banning (auto + manual)
    - Suspicious pattern detection
    - User-Agent filtering
    - Request logging
    """

    async def dispatch(self, request: Request, call_next):
        # Получаем IP клиента
        client_ip = get_client_ip(request)

        # Пропускаем whitelisted IPs
        if client_ip in WHITELISTED_IPS:
            return await call_next(request)

        # Проверяем бан
        if await security_storage.is_banned(client_ip):
            logger.warning(f"Blocked banned IP: {client_ip}")
            raise HTTPException(
                status_code=403,
                detail="Access denied. Your IP has been temporarily blocked."
            )

        # Проверяем User-Agent
        user_agent = request.headers.get("User-Agent", "")
        if check_user_agent(user_agent):
            logger.warning(
                f"Blocked suspicious User-Agent from {client_ip}: "
                f"{sanitize_log_content(user_agent)}"
            )
            await security_storage.add_suspicious_action(client_ip)
            raise HTTPException(
                status_code=403,
                detail="Access denied."
            )

        # Rate limiting
        requests_minute, requests_hour = await security_storage.add_request(client_ip)

        if requests_minute > MAX_REQUESTS_PER_MINUTE:
            logger.warning(
                f"Rate limit exceeded (minute) for {client_ip}: "
                f"{requests_minute} requests"
            )
            suspicious_count = await security_storage.add_suspicious_action(client_ip)

            if suspicious_count >= SUSPICIOUS_ACTIONS_THRESHOLD:
                await security_storage.ban_ip(client_ip)

            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down."
            )

        if requests_hour > MAX_REQUESTS_PER_HOUR:
            logger.warning(
                f"Rate limit exceeded (hour) for {client_ip}: "
                f"{requests_hour} requests"
            )
            raise HTTPException(
                status_code=429,
                detail="Hourly request limit exceeded. Please try again later."
            )

        # Проверяем URL на подозрительные паттерны
        url_path = str(request.url.path)
        query_string = str(request.url.query) if request.url.query else ""
        full_url = f"{url_path}?{query_string}" if query_string else url_path

        is_suspicious, matched_pattern = check_suspicious_content(full_url)
        if is_suspicious:
            logger.warning(
                f"Suspicious URL pattern from {client_ip}: "
                f"pattern='{matched_pattern}', url={sanitize_log_content(full_url)}"
            )
            suspicious_count = await security_storage.add_suspicious_action(client_ip)

            if suspicious_count >= SUSPICIOUS_ACTIONS_THRESHOLD:
                await security_storage.ban_ip(client_ip)

            raise HTTPException(
                status_code=400,
                detail="Invalid request."
            )

        # Для POST/PUT запросов проверяем body (если небольшой)
        if request.method in ("POST", "PUT", "PATCH"):
            # Читаем body только если Content-Length разумный
            content_length = request.headers.get("Content-Length", "0")
            try:
                body_size = int(content_length)
            except ValueError:
                body_size = 0

            # Проверяем только небольшие body (< 10KB)
            if 0 < body_size < 10240:
                try:
                    body = await request.body()
                    body_str = body.decode("utf-8", errors="ignore")

                    is_suspicious, matched_pattern = check_suspicious_content(body_str)
                    if is_suspicious:
                        logger.warning(
                            f"Suspicious body pattern from {client_ip}: "
                            f"pattern='{matched_pattern}'"
                        )
                        suspicious_count = await security_storage.add_suspicious_action(client_ip)

                        if suspicious_count >= SUSPICIOUS_ACTIONS_THRESHOLD:
                            await security_storage.ban_ip(client_ip)

                        raise HTTPException(
                            status_code=400,
                            detail="Invalid request content."
                        )
                except Exception:
                    pass  # Если не можем прочитать body - пропускаем

        # Всё в порядке - продолжаем обработку
        response = await call_next(request)

        # Добавляем security headers (дополнительно к тем что в api_server.py)
        response.headers["X-Request-ID"] = hashlib.md5(
            f"{client_ip}{datetime.now(UTC).timestamp()}".encode()
        ).hexdigest()[:16]

        return response


# =============================================================================
# INPUT VALIDATION HELPERS
# =============================================================================

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username: str) -> bool:
    """Validate username (alphanumeric + underscore, 3-32 chars)"""
    pattern = r'^[a-zA-Z0-9_]{3,32}$'
    return bool(re.match(pattern, username))


def sanitize_string(s: str, max_length: int = 1000) -> str:
    """
    Sanitize string input:
    - Remove control characters
    - Trim whitespace
    - Limit length
    """
    if not s:
        return ""

    # Удаляем управляющие символы (кроме newline, tab)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', s)

    # Trim
    sanitized = sanitized.strip()

    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def sanitize_html(s: str) -> str:
    """
    Remove potentially dangerous HTML/script tags.
    For user-generated content that will be displayed.
    """
    if not s:
        return ""

    # Удаляем script теги
    s = re.sub(r'<script[^>]*>.*?</script>', '', s, flags=re.DOTALL | re.IGNORECASE)

    # Удаляем on* атрибуты (onclick, onerror, etc.)
    s = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', s, flags=re.IGNORECASE)

    # Удаляем javascript: URLs
    s = re.sub(r'javascript\s*:', '', s, flags=re.IGNORECASE)

    # Удаляем data: URLs (могут содержать вредоносный контент)
    s = re.sub(r'data\s*:[^,]*,', '', s, flags=re.IGNORECASE)

    return s


# =============================================================================
# ADMIN FUNCTIONS
# =============================================================================

async def get_security_stats() -> Dict:
    """Get current security statistics"""
    async with security_storage.lock:
        return {
            "active_ips": len(security_storage.request_counts),
            "banned_ips": len(security_storage.banned_ips),
            "banned_list": list(security_storage.banned_ips.keys()),
            "suspicious_ips": [
                {"ip": ip, "count": count}
                for ip, count in security_storage.suspicious_counts.items()
                if count > 0
            ],
        }


async def manual_ban_ip(ip: str, duration_seconds: int = BAN_DURATION_SECONDS):
    """Manually ban an IP address"""
    await security_storage.ban_ip(ip, duration_seconds)


async def unban_ip(ip: str):
    """Remove IP from ban list"""
    async with security_storage.lock:
        if ip in security_storage.banned_ips:
            del security_storage.banned_ips[ip]
        if ip in security_storage.suspicious_counts:
            del security_storage.suspicious_counts[ip]
        logger.info(f"IP {ip} unbanned")


# =============================================================================
# BACKGROUND CLEANUP TASK
# =============================================================================

async def security_cleanup_task():
    """
    Background task to periodically clean up security storage.
    Run this in the application lifespan.
    """
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        await security_storage.cleanup()
        logger.debug("Security storage cleanup completed")
