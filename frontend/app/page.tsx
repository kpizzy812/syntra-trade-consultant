/**
 * Syntra AI Trading - Home Page
 * Главная страница Telegram Mini App
 */

'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import FearGreedCard from '@/components/cards/FearGreedCard';
import WatchlistSection from '@/components/sections/WatchlistSection';
import TopMoversSection from '@/components/sections/TopMoversSection';
import { useTelegram } from '@/components/providers/TelegramProvider';
import { useUserStore } from '@/shared/store/userStore';
import { api } from '@/shared/api/client';
import { useAuthRefresh } from '@/shared/hooks/useAuthRefresh';

export default function Home() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user, setUser, setInitData } = useUserStore();
  const { isReady, isMiniApp, webApp } = useTelegram();

  // Мониторинг сессии и автоматический refresh
  useAuthRefresh();

  useEffect(() => {
    // Ждем пока TelegramProvider завершит инициализацию
    if (!isReady) return;

    const initApp = async () => {
      if (isMiniApp && webApp?.initDataUnsafe) {
        // Получаем initData из Telegram WebApp
        const initDataRaw = webApp.initData;

        if (initDataRaw) {
          setInitData(initDataRaw);

          // Авторизация на backend
          try {
            const response = await api.auth.telegram(initDataRaw);
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
          console.warn('No initData available from Telegram');
          setIsLoading(false);
        }
      } else {
        // Для тестирования без Telegram (в браузере)
        console.warn('Running without Telegram WebApp');
        setIsLoading(false);
      }
    };

    initApp();
  }, [isReady, isMiniApp, webApp, setUser, setInitData]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">Loading Syntra...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center glassmorphism-card rounded-2xl p-6 max-w-md mx-4">
          <div className="text-red-400 text-4xl mb-4">⚠️</div>
          <h2 className="text-white font-bold text-xl mb-2">Connection Error</h2>
          <p className="text-gray-400 text-sm">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2.5 rounded-full transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black mobile-body">
      <Header />

      <main className="px-4 pt-4 pb-24">
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
            <p className="text-gray-400 text-sm">Welcome back,</p>
            <h1 className="text-2xl font-bold text-white">
              {user?.first_name || 'Trader'}
            </h1>
            {user?.is_premium && (
              <div className="inline-flex items-center gap-1 mt-1 px-3 py-1 bg-gradient-to-r from-yellow-500/20 to-orange-500/20 border border-yellow-500/30 rounded-full">
                <span className="text-yellow-400 text-xs font-bold">⭐ Premium</span>
              </div>
            )}
          </motion.div>

          {/* Fear & Greed Index */}
          <FearGreedCard />

          {/* Watchlist */}
          <WatchlistSection />

          {/* Top Movers */}
          <TopMoversSection />

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glassmorphism-card rounded-2xl p-5"
          >
            <h2 className="text-white font-bold text-lg mb-3">Quick Actions</h2>
            <div className="space-y-2">
              <button className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2 active:scale-98">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
                </svg>
                Ask AI about market
              </button>
              <button className="w-full bg-gray-800/50 hover:bg-gray-700/50 text-white font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2 active:scale-98">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3 13h2v8H3zm4-6h2v14H7zm4-4h2v18h-2zm4 9h2v9h-2zm4-5h2v14h-2z" />
                </svg>
                View full analytics
              </button>
            </div>
          </motion.div>
        </motion.div>
      </main>

      <TabBar />
    </div>
  );
}
