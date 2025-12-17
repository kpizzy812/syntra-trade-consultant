"use client";

import Link from 'next/link';
import { getSavedUTMParams, addUTMToUrl, trackBotOpened } from '@/lib/analytics/utm-tracker';
import { usePostHog } from '@/components/providers/PostHogProvider';

interface TrackedLinkProps {
  href: string;
  children: React.ReactNode;
  className?: string;
  target?: string;
  rel?: string;
  trackEvent?: boolean; // Отслеживать клик как событие
  eventName?: string; // Кастомное имя события (по умолчанию "link_clicked")
  eventProperties?: Record<string, any>; // Дополнительные свойства события
}

/**
 * Компонент ссылки с автоматическим добавлением UTM параметров
 * И отслеживанием кликов через PostHog
 * Используй вместо обычного Link для всех важных ссылок
 */
export default function TrackedLink({
  href,
  children,
  className,
  target,
  rel,
  trackEvent = true,
  eventName = 'link_clicked',
  eventProperties = {},
}: TrackedLinkProps) {
  const posthog = usePostHog();

  const handleClick = () => {
    if (trackEvent) {
      // Отслеживаем клик через legacy tracker (для Google Analytics и т.д.)
      trackBotOpened(href);

      // Отслеживаем клик через PostHog
      if (posthog && posthog.__loaded) {
        const utmParams = getSavedUTMParams();

        posthog.capture(eventName, {
          link_url: href,
          link_text: typeof children === 'string' ? children : 'link',
          link_target: target,
          ...eventProperties,
          ...utmParams,
          timestamp: new Date().toISOString(),
          page_url: window.location.href,
        });
      }
    }
  };

  // Если есть сохраненные UTM параметры, добавляем их к ссылке
  // (для случаев, когда нужно передать UTM дальше, например в Telegram)
  const utmParams = getSavedUTMParams();
  const trackedHref = utmParams && href.startsWith('http')
    ? addUTMToUrl(href, utmParams)
    : href;

  return (
    <Link
      href={trackedHref}
      className={className}
      target={target}
      rel={rel}
      onClick={handleClick}
    >
      {children}
    </Link>
  );
}
