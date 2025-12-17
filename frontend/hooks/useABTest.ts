"use client";

import { useState, useEffect } from 'react';
import { usePostHog } from '@/components/providers/PostHogProvider';

/**
 * Варианты для A/B теста заголовка Hero секции
 */
export const HERO_TITLE_VARIANTS = {
  A: 'AI-платформа для криптотрейдеров',
  B: 'Твой личный AI-помощник по крипте',
  C: 'AI, который объясняет крипту простым языком',
} as const;

export type HeroTitleVariant = keyof typeof HERO_TITLE_VARIANTS;

/**
 * Хук для A/B тестирования заголовков через PostHog
 * Использует PostHog feature flags для определения варианта
 *
 * @returns variant - выбранный вариант (A, B или C)
 */
export function useHeroTitleABTest(): HeroTitleVariant {
  const posthog = usePostHog();
  const [variant, setVariant] = useState<HeroTitleVariant>('A'); // Default вариант

  useEffect(() => {
    if (!posthog || !posthog.__loaded) {
      return;
    }

    // Получаем вариант из PostHog feature flag
    // Feature flag должен быть настроен в PostHog dashboard
    const featureFlagVariant = posthog.getFeatureFlag('hero-title-test');

    if (featureFlagVariant && typeof featureFlagVariant === 'string') {
      const upperVariant = featureFlagVariant.toUpperCase();
      if (upperVariant in HERO_TITLE_VARIANTS) {
        setVariant(upperVariant as HeroTitleVariant);
      }
    } else {
      // Если feature flag не настроен, делаем локальное A/B/C распределение
      const randomVariant = getRandomVariant();
      setVariant(randomVariant);

      // Отправляем событие в PostHog о назначении варианта
      posthog.capture('ab_test_assigned', {
        test_name: 'hero_title_test',
        variant: randomVariant,
        title: HERO_TITLE_VARIANTS[randomVariant],
        timestamp: new Date().toISOString(),
      });
    }
  }, [posthog]);

  return variant;
}

/**
 * Получить случайный вариант для A/B/C теста
 * Равномерное распределение 33/33/34%
 */
function getRandomVariant(): HeroTitleVariant {
  const random = Math.random();
  if (random < 0.33) return 'A';
  if (random < 0.66) return 'B';
  return 'C';
}

/**
 * Хук для отслеживания конверсии в A/B тесте
 * Вызывай эту функцию когда пользователь совершает целевое действие
 */
export function useABTestConversion() {
  const posthog = usePostHog();

  return (conversionEvent: string, properties?: Record<string, any>) => {
    if (posthog && posthog.__loaded) {
      posthog.capture(`ab_test_conversion_${conversionEvent}`, {
        ...properties,
        timestamp: new Date().toISOString(),
      });
    }
  };
}
