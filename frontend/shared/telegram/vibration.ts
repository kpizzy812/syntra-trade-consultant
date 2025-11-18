/**
 * Telegram Haptic Feedback Utilities
 * Вибрация для улучшения UX в Mini App
 */

'use client';

type ImpactStyle = 'light' | 'medium' | 'heavy' | 'rigid' | 'soft';
type NotificationType = 'error' | 'success' | 'warning';

/**
 * Проверка доступности Haptic Feedback
 */
function isHapticAvailable(): boolean {
  return (
    typeof window !== 'undefined' &&
    !!window.Telegram?.WebApp?.HapticFeedback
  );
}

/**
 * Вибрация при клике/тапе
 * Использовать для всех интерактивных элементов
 *
 * @param style - Стиль вибрации (по умолчанию 'light')
 *
 * @example
 * ```tsx
 * <button onClick={() => {
 *   vibrate('light');
 *   handleClick();
 * }}>
 *   Click me
 * </button>
 * ```
 */
export function vibrate(style: ImpactStyle = 'light'): void {
  if (!isHapticAvailable()) return;

  try {
    window.Telegram!.WebApp.HapticFeedback.impactOccurred(style);
  } catch (error) {
    console.error('Vibration failed:', error);
  }
}

/**
 * Вибрация при уведомлении
 * Использовать для успеха, ошибки, предупреждения
 *
 * @param type - Тип уведомления
 *
 * @example
 * ```tsx
 * // При успешной операции
 * vibrateNotification('success');
 *
 * // При ошибке
 * vibrateNotification('error');
 * ```
 */
export function vibrateNotification(type: NotificationType): void {
  if (!isHapticAvailable()) return;

  try {
    window.Telegram!.WebApp.HapticFeedback.notificationOccurred(type);
  } catch (error) {
    console.error('Notification vibration failed:', error);
  }
}

/**
 * Вибрация при смене выбора
 * Использовать для tab bar, селектов, свитчей
 *
 * @example
 * ```tsx
 * <TabBar onChange={(tab) => {
 *   vibrateSelection();
 *   setActiveTab(tab);
 * }} />
 * ```
 */
export function vibrateSelection(): void {
  if (!isHapticAvailable()) return;

  try {
    window.Telegram!.WebApp.HapticFeedback.selectionChanged();
  } catch (error) {
    console.error('Selection vibration failed:', error);
  }
}

// Экспортируем типы для использования в компонентах
export type { ImpactStyle, NotificationType };
