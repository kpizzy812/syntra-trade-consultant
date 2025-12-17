/**
 * useKeyboardVisible Hook
 * Отслеживает состояние виртуальной клавиатуры на мобильных устройствах
 * Использует Visual Viewport API для детектирования изменений размера viewport
 */

'use client';

import { useState, useEffect } from 'react';

/**
 * Хук для отслеживания видимости клавиатуры на мобильных устройствах
 * @returns {boolean} true если клавиатура открыта, false если закрыта
 */
export function useKeyboardVisible(): boolean {
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);

  useEffect(() => {
    // Проверяем доступность Visual Viewport API
    if (typeof window === 'undefined' || !window.visualViewport) {
      return;
    }

    const visualViewport = window.visualViewport;

    // Сохраняем начальную высоту viewport
    const initialHeight = visualViewport.height;

    // Обработчик изменения размера viewport
    const handleResize = () => {
      const currentHeight = visualViewport.height;

      // Если высота viewport уменьшилась более чем на 150px - клавиатура открыта
      // 150px - минимальный порог для детектирования клавиатуры (избегаем ложных срабатываний)
      const heightDiff = initialHeight - currentHeight;
      const keyboardVisible = heightDiff > 150;

      setIsKeyboardVisible(keyboardVisible);

      // Debug logging (можно убрать в продакшене)
      if (process.env.NODE_ENV === 'development') {
        console.log('📱 Keyboard state:', {
          initialHeight,
          currentHeight,
          heightDiff,
          keyboardVisible
        });
      }
    };

    // Подписываемся на события изменения размера
    visualViewport.addEventListener('resize', handleResize);
    visualViewport.addEventListener('scroll', handleResize);

    // Cleanup при размонтировании
    return () => {
      visualViewport.removeEventListener('resize', handleResize);
      visualViewport.removeEventListener('scroll', handleResize);
    };
  }, []);

  return isKeyboardVisible;
}
