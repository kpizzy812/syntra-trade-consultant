/**
 * Conditional Telegram Script Loader
 *
 * Загружает Telegram SDK только если пользователь в Telegram Mini App
 * Оптимизация: не загружаем лишний скрипт для веб-пользователей
 */

'use client';

import Script from 'next/script';
import { useEffect, useState } from 'react';

export default function ConditionalTelegramScript() {
  const [shouldLoad, setShouldLoad] = useState(false);

  useEffect(() => {
    // Проверяем признаки Telegram окружения
    const hasWebApp = !!(window as any).Telegram?.WebApp;
    const hasTelegramUA = /Telegram/i.test(navigator.userAgent);
    const hasTgWebAppData = window.location.search.includes('tgWebAppData');

    console.log('🔍 ConditionalTelegramScript checks:', {
      hasWebApp,
      hasTelegramUA,
      hasTgWebAppData,
      userAgent: navigator.userAgent,
      search: window.location.search,
    });

    const isTelegramEnv =
      typeof window !== 'undefined' && (hasWebApp || hasTelegramUA || hasTgWebAppData);

    setShouldLoad(!!isTelegramEnv);

    if (isTelegramEnv) {
      console.log('🎯 Telegram environment detected - loading SDK');
    } else {
      console.log('🌐 Web environment - skipping Telegram SDK');
    }
  }, []);

  // Загружаем SDK только если нужно
  if (!shouldLoad) {
    return null;
  }

  return (
    <Script
      src="https://telegram.org/js/telegram-web-app.js"
      strategy="beforeInteractive"
      onLoad={() => {
        console.log('✅ Telegram SDK loaded');
      }}
      onError={(error) => {
        console.error('❌ Failed to load Telegram SDK:', error);
      }}
    />
  );
}
