import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from 'next-intl';
import { getLocale, getMessages } from 'next-intl/server';
import Script from 'next/script';
import "./globals.css";
import ToastProvider from "@/components/providers/ToastProvider";
import TonConnectProvider from "@/components/providers/TonConnectProvider";
import TelegramProvider from "@/components/providers/TelegramProvider";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Syntra - AI Trade Consultant",
  description: "AI-powered crypto trading assistant in Telegram",
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
    userScalable: false,
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Get current locale and messages
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className={inter.variable}>
      <head>
        {/* Telegram WebApp SDK - должен загрузиться первым */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
      </head>
      <body className="antialiased">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <TelegramProvider>
            <TonConnectProvider>
              <ToastProvider />
              {children}
            </TonConnectProvider>
          </TelegramProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
