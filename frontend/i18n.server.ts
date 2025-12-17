import 'server-only';
import { headers } from 'next/headers';
import { locales, defaultLocale, type Locale } from './i18n';

/**
 * Get locale on server side from cookie
 */
export async function getServerLocale(): Promise<Locale> {
  const headersList = await headers();
  const cookieHeader = headersList.get('cookie') || '';
  const cookieMatch = cookieHeader.match(/NEXT_LOCALE=([^;]+)/);
  const localeCookie = cookieMatch ? cookieMatch[1] : null;

  const locale = localeCookie && locales.includes(localeCookie as Locale)
    ? (localeCookie as Locale)
    : defaultLocale;

  return locale;
}
