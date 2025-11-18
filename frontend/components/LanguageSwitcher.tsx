'use client';

import { useLocale } from 'next-intl';
import { useRouter, usePathname } from 'next/navigation';
import { useTransition } from 'react';

export default function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [isPending, startTransition] = useTransition();

  const switchLanguage = async (newLocale: string) => {
    if (locale === newLocale || isPending) return;

    startTransition(async () => {
      // Update locale cookie
      document.cookie = `NEXT_LOCALE=${newLocale}; path=/; max-age=31536000`;

      // Update user language preference in backend
      try {
        const { api } = await import('@/shared/api/client');
        await api.profile.updateSettings({ language: newLocale });
      } catch (error) {
        console.error('Failed to update language preference:', error);
      }

      // Reload page with new locale
      router.refresh();
    });
  };

  return (
    <div className="flex items-center gap-2 glassmorphism rounded-xl p-2">
      <button
        onClick={() => switchLanguage('en')}
        disabled={isPending}
        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
          locale === 'en'
            ? 'bg-blue-500 text-white'
            : 'text-gray-400 hover:text-white hover:bg-white/5'
        } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        EN
      </button>
      <button
        onClick={() => switchLanguage('ru')}
        disabled={isPending}
        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
          locale === 'ru'
            ? 'bg-blue-500 text-white'
            : 'text-gray-400 hover:text-white hover:bg-white/5'
        } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        RU
      </button>
    </div>
  );
}
