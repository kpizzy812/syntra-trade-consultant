"use client";

import { usePostHog } from '@/components/providers/PostHogProvider';
import { getSavedUTMParams } from '@/lib/analytics/utm-tracker';
import { ButtonHTMLAttributes, forwardRef } from 'react';

interface TrackedButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  eventName: string;
  eventProperties?: Record<string, any>;
  href?: string;
  target?: string;
  rel?: string;
}

/**
 * Кнопка с автоматическим отслеживанием кликов через PostHog
 * Включает UTM параметры в каждое событие
 */
export const TrackedButton = forwardRef<HTMLButtonElement, TrackedButtonProps>(
  ({ eventName, eventProperties = {}, onClick, children, href, target, rel, ...props }, ref) => {
    const posthog = usePostHog();

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      // Отслеживаем клик в PostHog
      if (posthog && posthog.__loaded) {
        const utmParams = getSavedUTMParams();

        posthog.capture(eventName, {
          ...eventProperties,
          ...utmParams,
          button_text: typeof children === 'string' ? children : eventName,
          timestamp: new Date().toISOString(),
          page_url: window.location.href,
        });
      }

      // Если есть href, открываем ссылку
      if (href) {
        if (target === '_blank') {
          window.open(href, target, rel);
        } else {
          window.location.href = href;
        }
      }

      // Вызываем оригинальный onClick если есть
      if (onClick) {
        onClick(e);
      }
    };

    return (
      <button ref={ref} onClick={handleClick} {...props}>
        {children}
      </button>
    );
  }
);

TrackedButton.displayName = 'TrackedButton';
