"use client";

import { shortLinks } from '@/config/short-links';
import { useState } from 'react';

/**
 * Dashboard для просмотра всех коротких ссылок
 * Доступен по адресу: https://yoursite.com/go
 */

export default function ShortLinksPage() {
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);

  const copyToClipboard = (slug: string, baseUrl: string) => {
    const url = `${baseUrl}/go/${slug}`;
    navigator.clipboard.writeText(url);
    setCopiedSlug(slug);
    setTimeout(() => setCopiedSlug(null), 2000);
  };

  // Получаем base URL (работает и на localhost, и на production)
  const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';

  // Группируем ссылки по источникам
  const groupedLinks = shortLinks.reduce((acc, link) => {
    const source = link.utm.source;
    if (!acc[source]) {
      acc[source] = [];
    }
    acc[source].push(link);
    return acc;
  }, {} as Record<string, typeof shortLinks>);

  const sourceEmojis: Record<string, string> = {
    tiktok: '📱',
    instagram: '📸',
    telegram: '💬',
    youtube: '🎥',
    twitter: '🐦',
    email: '📧',
    offline: '🏢',
    promo: '🎯',
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-indigo-900 to-blue-900 text-white p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">🔗 Короткие ссылки Syntra AI</h1>
          <p className="text-white/70">
            Все твои короткие ссылки с UTM tracking в одном месте
          </p>
        </div>

        {/* Инструкция */}
        <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6 mb-8">
          <h2 className="text-xl font-semibold mb-3">📖 Как использовать</h2>
          <ol className="space-y-2 text-sm text-white/80">
            <li>1. Найди нужную короткую ссылку ниже (например, <code className="bg-white/20 px-2 py-1 rounded">/go/tt</code> для TikTok)</li>
            <li>2. Нажми кнопку "Копировать"</li>
            <li>3. Вставь в био/описание соцсети</li>
            <li>4. Готово! Все переходы будут отслеживаться в Google Analytics</li>
          </ol>
        </div>

        {/* Список ссылок по категориям */}
        {Object.entries(groupedLinks).map(([source, links]) => (
          <div key={source} className="mb-8">
            <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
              <span>{sourceEmojis[source] || '🔗'}</span>
              <span className="capitalize">{source}</span>
            </h2>

            <div className="grid md:grid-cols-2 gap-4">
              {links.map((link) => (
                <div
                  key={link.slug}
                  className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-xl p-5 hover:bg-white/15 transition-all"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="font-mono text-lg font-semibold text-blue-300 mb-1">
                        /go/{link.slug}
                      </div>
                      <div className="text-sm text-white/60">{link.description}</div>
                    </div>

                    <button
                      onClick={() => copyToClipboard(link.slug, baseUrl)}
                      className="bg-blue-500 hover:bg-blue-600 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    >
                      {copiedSlug === link.slug ? '✅ Скопировано' : '📋 Копировать'}
                    </button>
                  </div>

                  <div className="space-y-1 text-xs">
                    <div className="flex gap-2">
                      <span className="text-white/50">Полная ссылка:</span>
                      <code className="text-white/80 break-all">
                        {baseUrl}/go/{link.slug}
                      </code>
                    </div>

                    <div className="flex gap-2">
                      <span className="text-white/50">UTM:</span>
                      <code className="text-white/80">
                        source={link.utm.source}, medium={link.utm.medium}, campaign={link.utm.campaign}
                      </code>
                    </div>
                  </div>

                  {/* Кнопка для открытия */}
                  <div className="mt-3 pt-3 border-t border-white/10">
                    <a
                      href={`/go/${link.slug}`}
                      target="_blank"
                      className="text-sm text-blue-300 hover:text-blue-200 underline"
                    >
                      Открыть ссылку →
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* Добавление новых ссылок */}
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-2xl p-6 mt-8">
          <h3 className="text-lg font-semibold mb-2">➕ Хочешь добавить новую ссылку?</h3>
          <p className="text-sm text-white/70 mb-3">
            Отредактируй файл <code className="bg-white/20 px-2 py-1 rounded">frontend/config/short-links.ts</code>
          </p>
          <pre className="bg-black/30 p-4 rounded-lg text-xs overflow-x-auto">
{`{
  slug: 'my-link',           // короткая ссылка
  destination: '/landing',   // куда редиректить
  utm: {
    source: 'tiktok',
    medium: 'video',
    campaign: 'my_campaign',
  },
  description: 'Моя новая ссылка',
}`}
          </pre>
        </div>
      </div>
    </div>
  );
}
