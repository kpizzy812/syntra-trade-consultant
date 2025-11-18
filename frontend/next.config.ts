import type { NextConfig } from "next";
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./i18n.ts');

const nextConfig: NextConfig = {
  // React strict mode
  reactStrictMode: true,

  // Настройки для Telegram Mini App
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN', // Разрешаем iframe от Telegram
          },
          {
            key: 'Content-Security-Policy',
            value: "frame-ancestors 'self' https://web.telegram.org https://telegram.org",
          },
        ],
      },
    ];
  },

  // Оптимизация изображений
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**', // Для crypto icons и других изображений
      },
    ],
  },
};

export default withNextIntl(nextConfig);
