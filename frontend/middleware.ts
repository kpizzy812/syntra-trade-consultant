import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export const config = {
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)'],
};

export function middleware(req: NextRequest) {
  // Simple pass-through - no locale routing needed
  // Telegram Mini App will handle language internally
  return NextResponse.next();
}
