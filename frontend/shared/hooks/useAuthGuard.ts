/**
 * Auth Guard Hook
 * Проверяет валидность JWT токена и управляет состоянием аутентификации
 *
 * Usage:
 * const { isChecking, isAuthenticated } = useAuthGuard();
 */

'use client';

import { useEffect, useState } from 'react';
import { jwtDecode } from 'jwt-decode';
import { api } from '@/shared/api/client';

interface AuthGuardResult {
  isChecking: boolean;
  isAuthenticated: boolean;
  user: any | null;
}

interface JWTPayload {
  exp: number;
  sub?: string;
  user_id?: number;
  email?: string;
}

/**
 * Hook для проверки аутентификации пользователя
 * Проверяет наличие и валидность JWT токена в localStorage
 */
export function useAuthGuard(): AuthGuardResult {
  const [isChecking, setIsChecking] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<any | null>(null);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      // Проверяем наличие токена в localStorage
      const token = localStorage.getItem('auth_token');
      const userStr = localStorage.getItem('user');

      if (!token || !userStr) {
        setIsAuthenticated(false);
        setUser(null);
        setIsChecking(false);
        return;
      }

      // 🔒 SECURITY: Проверяем expiration токена локально ПЕРЕД отправкой на backend
      try {
        const decoded = jwtDecode<JWTPayload>(token);
        const now = Date.now() / 1000; // JWT exp в секундах, Date.now() в миллисекундах

        if (decoded.exp && decoded.exp < now) {
          // Токен истёк - очищаем и не делаем лишний запрос на backend
          console.warn('[AuthGuard] Token expired:', {
            expired: new Date(decoded.exp * 1000).toISOString(),
            now: new Date(now * 1000).toISOString(),
          });
          clearAuth();
          setIsChecking(false);
          return;
        }
      } catch (jwtError) {
        // Если не можем декодировать JWT - скорее всего токен повреждён
        console.error('[AuthGuard] Invalid JWT token:', jwtError);
        clearAuth();
        setIsChecking(false);
        return;
      }

      // Валидируем токен через API (только если локально валидный)
      const response = await api.auth.validateToken();

      if (response && response.user) {
        // Токен валиден
        setIsAuthenticated(true);
        setUser(response.user);

        // Обновляем user данные в localStorage на случай если они изменились
        localStorage.setItem('user', JSON.stringify(response.user));
      } else {
        // Невалидный ответ
        clearAuth();
      }
    } catch (error) {
      console.error('[AuthGuard] Token validation failed:', error);
      // Токен истёк или невалиден - очищаем localStorage
      clearAuth();
    } finally {
      setIsChecking(false);
    }
  };

  const clearAuth = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    setIsAuthenticated(false);
    setUser(null);
  };

  return {
    isChecking,
    isAuthenticated,
    user,
  };
}

/**
 * Simple check if user is authenticated (synchronous)
 * Проверяет только наличие токена, без валидации
 */
export function isUserAuthenticated(): boolean {
  if (typeof window === 'undefined') return false;

  const token = localStorage.getItem('auth_token');
  const user = localStorage.getItem('user');

  return !!(token && user);
}

/**
 * Get stored user data from localStorage (synchronous)
 */
export function getStoredUser(): any | null {
  if (typeof window === 'undefined') return null;

  const userStr = localStorage.getItem('user');
  if (!userStr) return null;

  try {
    return JSON.parse(userStr);
  } catch {
    return null;
  }
}
