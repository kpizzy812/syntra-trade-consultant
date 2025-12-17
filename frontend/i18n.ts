import { notFound } from 'next/navigation';
import { getRequestConfig } from 'next-intl/server';

// Supported locales
export const locales = ['en', 'ru'] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = 'en';

export default getRequestConfig(async ({ requestLocale }) => {
  // Locale will be provided by layout.tsx via setRequestLocale
  let locale = await requestLocale;

  // Validate and fallback
  if (!locale || !locales.includes(locale as Locale)) {
    locale = defaultLocale;
  }

  console.log('🌍 i18n: Using locale:', locale);

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
