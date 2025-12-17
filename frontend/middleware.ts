import { NextRequest, NextResponse } from 'next/server';

export const config = {
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)'],
};

export function middleware(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const langParam = searchParams.get('lang');

  // Если есть параметр lang в URL, устанавливаем cookie
  if (langParam && (langParam === 'en' || langParam === 'ru')) {
    const response = NextResponse.next();

    response.cookies.set('NEXT_LOCALE', langParam, {
      path: '/',
      maxAge: 31536000, // 1 год
      sameSite: 'lax',
    });

    console.log(`🌍 Middleware: Setting locale cookie to ${langParam}`);
    return response;
  }

  // Simple pass-through
  return NextResponse.next();
}
