"use client";

import { useEffect, useRef } from 'react';
import { usePostHog } from '@/components/providers/PostHogProvider';
import { getSavedUTMParams } from '@/lib/analytics/utm-tracker';

interface ScrollTrackingOptions {
  sectionId: string;
  sectionName: string;
  threshold?: number; // Процент видимости секции для срабатывания (0-1)
}

/**
 * Хук для отслеживания скролла до определенной секции
 * Отправляет событие в PostHog когда пользователь доскролливает до секции
 */
export function useScrollTracking({ sectionId, sectionName, threshold = 0.5 }: ScrollTrackingOptions) {
  const posthog = usePostHog();
  const hasTracked = useRef(false);

  useEffect(() => {
    if (!posthog || !posthog.__loaded || hasTracked.current) {
      return;
    }

    const element = document.getElementById(sectionId);
    if (!element) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasTracked.current) {
            hasTracked.current = true;

            const utmParams = getSavedUTMParams();

            posthog.capture('section_viewed', {
              section_id: sectionId,
              section_name: sectionName,
              scroll_depth: Math.round((window.scrollY / document.body.scrollHeight) * 100),
              ...utmParams,
              timestamp: new Date().toISOString(),
              page_url: window.location.href,
            });

            // Отключаем observer после первого срабатывания
            observer.disconnect();
          }
        });
      },
      {
        threshold,
        rootMargin: '0px',
      }
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [posthog, sectionId, sectionName, threshold]);
}

/**
 * Хук для отслеживания глубины скролла страницы
 * Отправляет событие когда пользователь достигает определенных вех (25%, 50%, 75%, 100%)
 */
export function useScrollDepthTracking() {
  const posthog = usePostHog();
  const milestones = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!posthog || !posthog.__loaded) {
      return;
    }

    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.body.scrollHeight - window.innerHeight;
      const scrollPercent = Math.round((scrollTop / docHeight) * 100);

      // Отслеживаем вехи: 25%, 50%, 75%, 100%
      const checkpoints = [25, 50, 75, 100];

      checkpoints.forEach((checkpoint) => {
        if (scrollPercent >= checkpoint && !milestones.current.has(checkpoint)) {
          milestones.current.add(checkpoint);

          const utmParams = getSavedUTMParams();

          posthog.capture('scroll_depth_reached', {
            scroll_depth: checkpoint,
            ...utmParams,
            timestamp: new Date().toISOString(),
            page_url: window.location.href,
          });
        }
      });
    };

    // Throttle scroll events
    let ticking = false;
    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          handleScroll();
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', onScroll);
    };
  }, [posthog]);
}
