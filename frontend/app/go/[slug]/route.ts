import { NextRequest, NextResponse } from 'next/server';
import { getShortLink, buildFullUrl } from '@/config/short-links';

/**
 * Redirect API для коротких ссылок
 *
 * Примеры:
 * https://yoursite.com/go/tt → редирект на /landing?utm_source=tiktok&utm_medium=bio...
 * https://yoursite.com/go/ig → редирект на /landing?utm_source=instagram&utm_medium=bio...
 */

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
) {
  // В Next.js 15+ params стали асинхронными
  const { slug } = await params;

  // Находим короткую ссылку в конфиге
  const shortLink = getShortLink(slug);

  if (!shortLink) {
    // Если ссылка не найдена, редирект на главную
    return NextResponse.redirect(new URL('/landing', request.url));
  }

  // Получаем base URL (поддержка localhost и production)
  const baseUrl = request.nextUrl.origin;

  // Строим полный URL с UTM параметрами
  const fullUrl = buildFullUrl(shortLink, baseUrl);

  // Редиректим с кодом 307 (Temporary Redirect)
  // Можно использовать 301 (Permanent) для SEO, но 307 безопаснее для аналитики
  return NextResponse.redirect(fullUrl, { status: 307 });
}
