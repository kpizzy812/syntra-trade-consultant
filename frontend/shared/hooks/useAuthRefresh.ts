/**
 * Auth Refresh Hook
 * Мониторинг времени жизни initData и автоматическое обновление
 */

'use client';

import { useEffect, useRef } from 'react';
import { useUserStore } from '@/shared/store/userStore';

// Константы времени (в секундах)
const EXPIRATION_TIME = 24 * 60 * 60; // 24 часа = 86400 секунд
const CHECK_INTERVAL = 60 * 1000; // Проверять каждую минуту

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
 * Хук для мониторинга и refresh авторизации
 */
export function useAuthRefresh() {
  const initData = useUserStore((state) => state.initData);
  const clearUser = useUserStore((state) => state.clearUser);
  const hasReloadedRef = useRef(false);

  useEffect(() => {
    if (!initData) {
      return;
    }

    const authDate = parseAuthDate(initData);
    if (!authDate) {
      console.error('[Auth] No auth_date in initData');
      return;
    }

    // Функция проверки статуса
    const checkAuthStatus = () => {
      const status = getAuthStatus(authDate);

      // Сессия истекла - тихо обновляем
      if (status.isExpired && !hasReloadedRef.current) {
        hasReloadedRef.current = true;

        console.info('[Auth] Session expired, refreshing app...');

        // Очищаем пользователя
        clearUser();

        // Тихо обновляем страницу (без toast уведомлений)
        window.location.reload();
      }
    };

    // Первая проверка сразу
    checkAuthStatus();

    // Периодическая проверка каждую минуту
    const interval = setInterval(checkAuthStatus, CHECK_INTERVAL);

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
