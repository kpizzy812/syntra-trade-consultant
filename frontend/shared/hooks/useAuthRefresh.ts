/**
 * Auth Refresh Hook
 * Мониторинг времени жизни initData (Telegram) и JWT tokens (Web)
 * Автоматическое обновление и проверка валидности
 */

'use client';

import { useEffect, useRef } from 'react';
import { useUserStore } from '@/shared/store/userStore';

// Константы времени (в секундах)
const EXPIRATION_TIME = 24 * 60 * 60; // 24 часа = 86400 секунд
const CHECK_INTERVAL = 60 * 1000; // Проверять каждую минуту
const JWT_WARNING_TIME = 24 * 60 * 60; // Предупреждать за 24 часа до истечения JWT

interface AuthStatus {
  isExpired: boolean;
  timeLeft: number; // в секундах
}

/**
 * Парсит auth_date из initData строки
 */
function parseAuthDate(initData: string): number | null {
  try {
    const params = new URLSearchParams(initData);
    const authDate = params.get('auth_date');
    return authDate ? parseInt(authDate) : null;
  } catch (error) {
    console.error('Failed to parse auth_date:', error);
    return null;
  }
}

/**
 * Вычисляет статус авторизации
 */
function getAuthStatus(authDate: number): AuthStatus {
  const now = Math.floor(Date.now() / 1000);
  const timeElapsed = now - authDate;
  const timeLeft = EXPIRATION_TIME - timeElapsed;

  return {
    isExpired: timeLeft <= 0,
    timeLeft: Math.max(0, timeLeft),
  };
}


/**
 * Decode JWT token (без валидации подписи - только для чтения exp)
 */
function decodeJWT(token: string): any | null {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('[Auth] Failed to decode JWT:', error);
    return null;
  }
}

/**
 * Проверить валидность JWT токена
 */
function isJWTExpired(token: string): boolean {
  const payload = decodeJWT(token);
  if (!payload || !payload.exp) {
    return true;
  }

  const now = Math.floor(Date.now() / 1000);
  return now >= payload.exp;
}

/**
 * Хук для мониторинга и refresh авторизации
 * Поддерживает:
 * - Telegram initData (Telegram Mini App)
 * - JWT tokens (Web authentication)
 */
export function useAuthRefresh() {
  const initData = useUserStore((state) => state.initData);
  const clearUser = useUserStore((state) => state.clearUser);
  const hasReloadedRef = useRef(false);

  useEffect(() => {
    // Функция проверки статуса для Telegram
    const checkTelegramAuth = () => {
      if (!initData) return;

      const authDate = parseAuthDate(initData);
      if (!authDate) {
        console.error('[Auth] No auth_date in initData');
        return;
      }

      const status = getAuthStatus(authDate);

      // Сессия истекла - тихо обновляем
      if (status.isExpired && !hasReloadedRef.current) {
        hasReloadedRef.current = true;

        console.info('[Auth] Telegram session expired, refreshing app...');

        // Очищаем пользователя
        clearUser();

        // Тихо обновляем страницу (без toast уведомлений)
        window.location.reload();
      }
    };

    // Функция проверки статуса для Web JWT
    const checkWebAuth = () => {
      if (typeof window === 'undefined') return;

      const token = localStorage.getItem('auth_token');
      if (!token) return;

      // Проверяем истёк ли JWT
      if (isJWTExpired(token)) {
        console.info('[Auth] JWT token expired, clearing auth...');

        // Очищаем токен и пользователя
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user');
        clearUser();

        // Перезагружаем страницу для редиректа на auth flow
        if (!hasReloadedRef.current) {
          hasReloadedRef.current = true;
          window.location.reload();
        }
      }
    };

    // Функция проверки всех типов авторизации
    const checkAllAuth = () => {
      checkTelegramAuth();
      checkWebAuth();
    };

    // Первая проверка сразу
    checkAllAuth();

    // Периодическая проверка каждую минуту
    const interval = setInterval(checkAllAuth, CHECK_INTERVAL);

    return () => {
      clearInterval(interval);
    };
  }, [initData, clearUser]);

  return null;
}

/**
 * Хук для получения информации о статусе сессии (опциональный)
 * Можно использовать для отображения UI
 */
export function useAuthStatus(): AuthStatus | null {
  const initData = useUserStore((state) => state.initData);

  if (!initData) {
    return null;
  }

  const authDate = parseAuthDate(initData);
  if (!authDate) {
    return null;
  }

  return getAuthStatus(authDate);
}
