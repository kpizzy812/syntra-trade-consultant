/**
 * Platform-agnostic Haptic Feedback Utilities
 * Uses Platform Abstraction Layer for cross-platform support
 */

'use client';

import { hapticImpact, hapticNotification, hapticSelection } from '@/lib/platform/platformHelper';
import type { HapticStyle, NotificationType } from '@/lib/platform';

// Re-export types for backward compatibility
export type ImpactStyle = HapticStyle;
export type { NotificationType };

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
export function vibrate(style: HapticStyle = 'light'): void {
  hapticImpact(style);
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
  hapticNotification(type);
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
  hapticSelection();
}
