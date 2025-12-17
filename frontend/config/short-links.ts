/**
 * Конфигурация коротких ссылок для соцсетей
 *
 * Вместо длинных UTM-ссылок используй короткие:
 * ❌ https://site.com/landing?utm_source=tiktok&utm_medium=bio&utm_campaign=main
 * ✅ https://site.com/go/tt
 */

export interface ShortLink {
  slug: string;           // Короткая ссылка (например: "tt", "ig", "tg")
  destination: string;    // Куда редиректить
  utm: {
    source: string;       // utm_source
    medium: string;       // utm_medium
    campaign: string;     // utm_campaign
    content?: string;     // utm_content (опционально)
    term?: string;        // utm_term (опционально)
  };
  description: string;    // Описание для справки
}

/**
 * 🎯 ГОТОВЫЕ КОРОТКИЕ ССЫЛКИ ДЛЯ СОЦСЕТЕЙ
 *
 * Используй их прямо в био/описаниях!
 */
export const shortLinks: ShortLink[] = [
  // ========================================
  // 📱 TikTok
  // ========================================
  {
    slug: 'tt',
    destination: '/landing',
    utm: {
      source: 'tiktok',
      medium: 'bio',
      campaign: 'main',
    },
    description: 'TikTok - ссылка в био',
  },
  {
    slug: 'tt-v',
    destination: '/landing',
    utm: {
      source: 'tiktok',
      medium: 'video',
      campaign: 'december_2024',
    },
    description: 'TikTok - видео (декабрь 2024)',
  },
  {
    slug: 'tt-ad',
    destination: '/landing',
    utm: {
      source: 'tiktok',
      medium: 'paid_ad',
      campaign: 'december_ads',
    },
    description: 'TikTok - платная реклама',
  },

  // ========================================
  // 📸 Instagram
  // ========================================
  {
    slug: 'ig',
    destination: '/landing',
    utm: {
      source: 'instagram',
      medium: 'bio',
      campaign: 'main',
    },
    description: 'Instagram - ссылка в био',
  },
  {
    slug: 'ig-r',
    destination: '/landing',
    utm: {
      source: 'instagram',
      medium: 'reels',
      campaign: 'december_2024',
    },
    description: 'Instagram - Reels (декабрь 2024)',
  },
  {
    slug: 'ig-s',
    destination: '/landing',
    utm: {
      source: 'instagram',
      medium: 'story',
      campaign: 'daily_stories',
    },
    description: 'Instagram - Stories',
  },
  {
    slug: 'ig-p',
    destination: '/landing',
    utm: {
      source: 'instagram',
      medium: 'post',
      campaign: 'december_2024',
    },
    description: 'Instagram - посты',
  },

  // ========================================
  // 💬 Telegram
  // ========================================
  {
    slug: 'tg',
    destination: '/landing',
    utm: {
      source: 'telegram',
      medium: 'channel',
      campaign: 'syntrade',
    },
    description: 'Telegram - канал @SyntraTrade',
  },
  {
    slug: 'tg-pin',
    destination: '/landing',
    utm: {
      source: 'telegram',
      medium: 'pinned',
      campaign: 'syntrade',
    },
    description: 'Telegram - закрепленное сообщение',
  },
  {
    slug: 'tg-bot',
    destination: '/landing',
    utm: {
      source: 'telegram',
      medium: 'bot',
      campaign: 'syntrabot',
    },
    description: 'Telegram - бот @SyntraAI_bot',
  },

  // ========================================
  // 🎥 YouTube
  // ========================================
  {
    slug: 'yt',
    destination: '/landing',
    utm: {
      source: 'youtube',
      medium: 'description',
      campaign: 'december_2024',
    },
    description: 'YouTube - описание видео',
  },
  {
    slug: 'yt-c',
    destination: '/landing',
    utm: {
      source: 'youtube',
      medium: 'comment',
      campaign: 'december_2024',
    },
    description: 'YouTube - закрепленный комментарий',
  },

  // ========================================
  // 🐦 Twitter/X
  // ========================================
  {
    slug: 'tw',
    destination: '/landing',
    utm: {
      source: 'twitter',
      medium: 'bio',
      campaign: 'main',
    },
    description: 'Twitter - ссылка в био',
  },
  {
    slug: 'tw-t',
    destination: '/landing',
    utm: {
      source: 'twitter',
      medium: 'tweet',
      campaign: 'december_2024',
    },
    description: 'Twitter - твит',
  },

  // ========================================
  // 📧 Email & Other
  // ========================================
  {
    slug: 'email',
    destination: '/landing',
    utm: {
      source: 'email',
      medium: 'newsletter',
      campaign: 'weekly_digest',
    },
    description: 'Email рассылка',
  },
  {
    slug: 'qr',
    destination: '/landing',
    utm: {
      source: 'offline',
      medium: 'qr_code',
      campaign: 'events',
    },
    description: 'QR-код для офлайн мероприятий',
  },

  // ========================================
  // 🎯 Специальные кампании
  // ========================================
  {
    slug: 'free',
    destination: '/landing',
    utm: {
      source: 'promo',
      medium: 'landing',
      campaign: 'free_trial',
    },
    description: 'Промо - бесплатный trial',
  },
];

/**
 * Получить ссылку по slug
 */
export function getShortLink(slug: string): ShortLink | undefined {
  return shortLinks.find(link => link.slug === slug);
}

/**
 * Построить полный URL с UTM параметрами
 */
export function buildFullUrl(link: ShortLink, baseUrl: string): string {
  const url = new URL(link.destination, baseUrl);

  url.searchParams.set('utm_source', link.utm.source);
  url.searchParams.set('utm_medium', link.utm.medium);
  url.searchParams.set('utm_campaign', link.utm.campaign);

  if (link.utm.content) {
    url.searchParams.set('utm_content', link.utm.content);
  }

  if (link.utm.term) {
    url.searchParams.set('utm_term', link.utm.term);
  }

  return url.toString();
}
