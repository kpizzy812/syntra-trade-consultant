/**
 * useCurrentLocale - хук для получения текущей локали
 * Работает на клиенте с использованием getPreferredLocale
 */

'use client';

import { useState, useEffect } from 'react';
import { getPreferredLocale } from '@/shared/lib/locale';
import type { Locale } from '@/i18n';

export function useCurrentLocale(): Locale {
  const [locale, setLocale] = useState<Locale>('en');

  useEffect(() => {
    setLocale(getPreferredLocale());
  }, []);

  return locale;
}
