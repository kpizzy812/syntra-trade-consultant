import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, setRequestLocale } from 'next-intl/server';
import { getServerLocale } from '@/i18n.server';
import Script from 'next/script';
import "./globals.css";
import ToastProvider from "@/components/providers/ToastProvider";
import TonConnectProvider from "@/components/providers/TonConnectProvider";
import TelegramProvider from "@/components/providers/TelegramProvider";
import { PlatformProvider } from "@/lib/platform";
import { PostHogPageView } from "@/components/providers/PostHogProvider";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  metadataBase: new URL('https://ai.syntratrade.xyz'),
  title: "Syntra AI - AI-Powered Crypto Analytics",
  description: "AI crypto analytics platform for traders. Market analysis, risk assessment, and trading insights. Available on Web & Telegram. Start 7-day Premium trial.",
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
    userScalable: false,
  },
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
    ],
    apple: [
      { url: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
  },
  openGraph: {
    title: "Syntra AI - AI-Powered Crypto Analytics",
    description: "AI crypto analytics platform for traders. Market analysis, risk assessment, and trading insights on Web & Telegram. Start 7-day Premium trial.",
    url: 'https://ai.syntratrade.xyz',
    siteName: 'Syntra AI',
    images: [
      {
        url: '/syntra/og-image.jpg',
        width: 1200,
        height: 630,
        alt: 'Syntra AI - AI-Powered Crypto Analytics',
        type: 'image/jpeg',
      },
    ],
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: "Syntra AI - AI-Powered Crypto Analytics",
    description: "AI crypto analytics for traders. Market analysis, risk assessment, trading insights. Web & Telegram. 7-day trial.",
    images: ['/syntra/twitter-image.jpg'],
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Get current locale from cookie (set by middleware)
  const locale = await getServerLocale();

  // Set locale for next-intl
  setRequestLocale(locale);

  // Get messages for this locale
  const messages = await getMessages({ locale });

  return (
    <html lang={locale} className={inter.variable}>
      <head>
        {/*
          Telegram SDK загружается ВСЕГДА и СИНХРОННО
          Это решает timing issue с PlatformProvider
          SDK легкий (~30kb), если не Telegram - initData будет пустым
        */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
      </head>
      <body className="antialiased">
        <NextIntlClientProvider locale={locale} messages={messages}>
          {/* Platform Provider - главный провайдер для multi-platform */}
          <PlatformProvider>
            {/* Legacy providers для обратной совместимости */}
            <TelegramProvider>
              <TonConnectProvider>
                <ToastProvider />
                <PostHogPageView />
                {children}
              </TonConnectProvider>
            </TelegramProvider>
          </PlatformProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
