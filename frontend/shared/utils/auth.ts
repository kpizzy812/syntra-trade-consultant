/**
 * Auth Utilities
 * Вспомогательные функции для работы с аутентификацией
 */

'use client';

/**
 * Logout function for WEB users (magic link auth)
 * Очищает localStorage и редиректит на лендинг
 *
 * NOTE: НЕ использовать для Telegram Mini App!
 * Telegram auth происходит через initData и не требует явного logout.
 */
export function logoutWebUser() {
  if (typeof window === 'undefined') return;

  console.log('[Auth] Logging out web user...');

  // Очищаем auth данные
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user');

  // Редирект на лендинг
  window.location.href = '/landing';
}

/**
 * Check if user is authenticated via Web (magic link)
 */
export function isWebAuth(): boolean {
  if (typeof window === 'undefined') return false;

  const token = localStorage.getItem('auth_token');
  return !!token;
}

/**
 * Check if current platform is Telegram Mini App
 */
export function isTelegramPlatform(): boolean {
  if (typeof window === 'undefined') return false;

  // Check for Telegram WebApp
  return !!(window as any).Telegram?.WebApp;
}
