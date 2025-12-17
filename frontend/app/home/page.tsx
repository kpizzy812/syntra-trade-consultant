/**
 * Syntra AI Trading - Home Page
 * Главная страница Telegram Mini App
 */

'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import DesktopLayout from '@/components/layout/DesktopLayout';
import MarketOverviewCard from '@/components/cards/MarketOverviewCard';
import WatchlistSection from '@/components/sections/WatchlistSection';
import TopMoversSection from '@/components/sections/TopMoversSection';
import PointsEarnAnimation from '@/components/points/PointsEarnAnimation';
import { usePlatform } from '@/lib/platform';
import { useUserStore } from '@/shared/store/userStore';
import { api } from '@/shared/api/client';
import { useAuthRefresh } from '@/shared/hooks/useAuthRefresh';

export default function Home() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pointsEarnTrigger, setPointsEarnTrigger] = useState(0);
  const [pointsEarnAmount, setPointsEarnAmount] = useState(0);
  const { user, setUser, setInitData } = useUserStore();
  const { platform, platformType, isReady } = usePlatform();
  const router = useRouter();
  const t = useTranslations('home');

  // Мониторинг сессии и автоматический refresh
  useAuthRefresh();

  const isDesktop = platformType === 'web';

  useEffect(() => {
    // Ждем пока Platform завершит инициализацию
    if (!isReady) return;

    const initApp = async () => {
      // Desktop users тоже могут использовать home page
      // (В будущем добавим веб-авторизацию)

      // Проверяем, что platform инициализирован
      if (!platform) {
        console.error('Platform not initialized');
        setIsLoading(false);
        return;
      }

      // Получаем credentials через platform abstraction
      const credentials = await platform.auth.getCredentials();

      if (credentials?.telegram_initData) {
        setInitData(credentials.telegram_initData);

        // Авторизация на backend
        try {
          const response = await api.auth.telegram(credentials.telegram_initData);
          if (response.success && response.user) {
            setUser(response.user);
          } else {
            setError('Authentication failed');
          }
        } catch (err) {
          console.error('Auth error:', err);
          setError('Failed to connect to server');
        } finally {
          setIsLoading(false);
        }
      } else {
        console.warn('No credentials available');
        setIsLoading(false);
      }
    };

    initApp();
  }, [isReady, platformType, platform, setUser, setInitData, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">{t('loading')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center glass-blue-card rounded-2xl p-6 max-w-md mx-4">
          <div className="text-red-400 text-4xl mb-4">⚠️</div>
          <h2 className="text-white font-bold text-xl mb-2">{t('connection_error')}</h2>
          <p className="text-gray-400 text-sm">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2.5 rounded-full transition-colors"
          >
            {t('retry')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <DesktopLayout>
      <div
        className={`
        flex flex-col h-full
        ${isDesktop ? 'bg-black' : 'bg-black mobile-body'}
      `}
      >
        <Header />

        <main
          className={`
          px-4 pt-4
          ${isDesktop ? 'flex-1 overflow-y-auto max-w-[1400px] mx-auto w-full pb-8' : 'mobile-scrollable pb-24'}
        `}
        >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="space-y-4"
        >
          {/* Welcome Message */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center mb-2"
          >
            <p className="text-gray-400 text-sm">{t('welcome_back')}</p>
            <h1 className="text-2xl font-bold text-white">
              {user?.first_name || 'Trader'}
            </h1>
            {user?.is_premium && (
              <div className="inline-flex items-center gap-1 mt-1 px-3 py-1 bg-gradient-to-r from-yellow-500/20 to-orange-500/20 border border-yellow-500/30 rounded-full">
                <span className="text-yellow-400 text-xs font-bold">⭐ Premium</span>
              </div>
            )}
          </motion.div>

          {/* Market Overview (Fear & Greed + Global Data) */}
          <MarketOverviewCard
            onEarnPoints={(amount) => {
              setPointsEarnAmount(amount);
              setPointsEarnTrigger((prev) => prev + 1);
            }}
          />

          {/* Watchlist */}
          <WatchlistSection />

          {/* Top Movers */}
          <TopMoversSection />

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-blue-card rounded-2xl p-5"
          >
            <h2 className="text-white font-bold text-lg mb-3">{t('quick_actions_title')}</h2>
            <div className="space-y-2">
              <button
                onClick={() => {
                  platform?.ui.haptic?.impact('light');
                  router.push('/chat');
                }}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2 active:scale-98"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
                </svg>
                {t('quick_actions.ask_ai')}
              </button>
              <button
                onClick={() => {
                  platform?.ui.haptic?.impact('light');
                  const prompt = encodeURIComponent(t('quick_actions.full_analytics_prompt'));
                  router.push(`/chat?prompt=${prompt}`);
                }}
                className="w-full bg-gray-800/50 hover:bg-gray-700/50 text-white font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2 active:scale-98"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3 13h2v8H3zm4-6h2v14H7zm4-4h2v18h-2zm4 9h2v9h-2zm4-5h2v14h-2z" />
                </svg>
                {t('quick_actions.full_analytics')}
              </button>
            </div>
          </motion.div>
        </motion.div>
      </main>

      <TabBar />
      </div>

      {/* Points Earn Animation */}
      <PointsEarnAnimation amount={pointsEarnAmount} trigger={pointsEarnTrigger} />
    </DesktopLayout>
  );
}
