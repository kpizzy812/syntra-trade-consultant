"use client";

import { useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  extractUTMParams,
  saveUTMParams,
  createTrafficSource,
  saveTrafficSource,
} from '@/lib/analytics/utm-tracker';

/**
 * Компонент для автоматического отслеживания UTM параметров
 * Добавь его в layout или на страницу лендинга
 */
export default function UTMTracker() {
  const searchParams = useSearchParams();

  useEffect(() => {
    if (!searchParams) return;

    // Извлекаем UTM параметры из URL
    const utmParams = extractUTMParams(searchParams);

    // Проверяем, есть ли хоть один UTM параметр
    const hasUTMParams = Object.values(utmParams).some(value => value !== undefined);

    if (hasUTMParams) {
      // Сохраняем в sessionStorage для использования на всех страницах
      saveUTMParams(utmParams);

      // Создаем полный объект источника трафика
      const trafficSource = createTrafficSource(utmParams);

      // Сохраняем в историю для аналитики
      saveTrafficSource(trafficSource);

      // Опционально: отправляем на бэкенд
      // sendToBackend(trafficSource);

      console.log('📊 Traffic source tracked:', trafficSource);
    }
  }, [searchParams]);

  // Компонент невидимый, только отслеживает
  return null;
}
