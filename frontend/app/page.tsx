/**
 * Syntra AI Trading - Root Redirect
 *
 * Smart routing based on platform:
 * - Telegram Mini App → /chat (main app)
 * - Web Browser → /landing (marketing page with lang and ref params)
 *
 * URL Format:
 * ai.syntratrade.xyz?ref=ABC123 → /landing?lang=ru&ref=ABC123
 */

'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { usePlatform } from '@/lib/platform';
import { getPreferredLocale } from '@/shared/lib/locale';

export default function Home() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { platformType, isReady } = usePlatform();

  useEffect(() => {
    // Wait for platform detection
    if (!isReady) return;

    console.log('🎯 Root page: detected platform =', platformType);

    // Platform-specific routing
    if (platformType === 'telegram') {
      // Telegram Mini App → открываем главную страницу приложения
      console.log('📱 Redirecting Telegram user to /chat');
      router.replace('/chat');
    } else {
      // Web Browser → открываем landing page с параметрами

      // Detect language
      const lang = getPreferredLocale();

      // Collect all URL parameters (ref, utm_source, utm_campaign, etc)
      const params = new URLSearchParams();
      params.set('lang', lang);

      // Preserve all query parameters from original URL
      searchParams.forEach((value, key) => {
        params.set(key, value);
      });

      const targetUrl = `/landing?${params.toString()}`;
      console.log('🌐 Redirecting web user to', targetUrl);
      router.replace(targetUrl);
    }
  }, [platformType, isReady, router, searchParams]);

  // Loading state пока платформа определяется
  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="text-center">
        <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-gray-400">
          {isReady ? 'Redirecting...' : 'Detecting platform...'}
        </p>
      </div>
    </div>
  );
}
