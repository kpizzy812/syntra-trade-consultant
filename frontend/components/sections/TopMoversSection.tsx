/**
 * Top Movers Section Component
 * Отображает топ крипто по изменению с multi-timeframe support
 */

'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { vibrate } from '@/shared/telegram/vibration';
import { api } from '@/shared/api/client';

interface MoverData {
  symbol: string;
  name: string;
  change: number;
  price: string;
  volume_24h?: string;
  market_cap?: string;
  image?: string;
}

type Timeframe = '1h' | '24h' | '7d';

export default function TopMoversSection() {
  const t = useTranslations('home.market');
  const router = useRouter();
  const [gainers, setGainers] = useState<MoverData[]>([]);
  const [losers, setLosers] = useState<MoverData[]>([]);
  const [timeframe, setTimeframe] = useState<Timeframe>('24h');
  const [showAll, setShowAll] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchTopMovers = async () => {
      setLoading(true);
      try {
        const limit = showAll ? 10 : 3;
        const response = await api.market.getTopMovers(timeframe, limit);
        console.log(`Top Movers API Response (${timeframe}):`, response);

        // Validate response
        if (!response || !response.gainers || !response.losers) {
          throw new Error('Invalid API response structure');
        }

        setGainers(response.gainers);
        setLosers(response.losers);
      } catch (error) {
        console.error('Failed to fetch top movers:', error);
        // Fallback to mock data on error
        setGainers([
          { symbol: 'XRP', name: 'Ripple', change: 12.5, price: '$0.58', image: 'https://assets.coingecko.com/coins/images/44/small/xrp-symbol-white-128.png' },
          { symbol: 'ADA', name: 'Cardano', change: 8.3, price: '$0.45', image: 'https://assets.coingecko.com/coins/images/975/small/cardano.png' },
          { symbol: 'AVAX', name: 'Avalanche', change: 6.7, price: '$35.20', image: 'https://assets.coingecko.com/coins/images/12559/small/Avalanche_Circle_RedWhite_Trans.png' },
        ]);
        setLosers([
          { symbol: 'DOGE', name: 'Dogecoin', change: -8.2, price: '$0.082', image: 'https://assets.coingecko.com/coins/images/5/small/dogecoin.png' },
          { symbol: 'SHIB', name: 'Shiba Inu', change: -6.1, price: '$0.000009', image: 'https://assets.coingecko.com/coins/images/11939/small/shiba.png' },
          { symbol: 'MATIC', name: 'Polygon', change: -4.5, price: '$0.78', image: 'https://assets.coingecko.com/coins/images/4713/small/polygon.png' },
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchTopMovers();
  }, [timeframe, showAll]);

  const handleTimeframeChange = (newTimeframe: Timeframe) => {
    vibrate('light');
    setTimeframe(newTimeframe);
  };

  const handleShowAllToggle = () => {
    vibrate('medium');
    setShowAll(!showAll);
  };

  const handleMoverClick = (symbol: string) => {
    vibrate('light');
    router.push(`/coin/${symbol.toLowerCase()}`);
  };

  // Форматирование цены: для маленьких чисел показываем больше знаков
  const formatPrice = (priceStr: string): string => {
    // Убираем $ и парсим число
    const numStr = priceStr.replace(/[$,]/g, '');
    const num = parseFloat(numStr);

    if (isNaN(num)) return priceStr;

    if (num >= 1) {
      return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (num >= 0.01) {
      return '$' + num.toFixed(4);
    } else if (num >= 0.0001) {
      return '$' + num.toFixed(6);
    } else {
      // Для очень маленьких чисел используем научную нотацию или subscript
      const formatted = num.toExponential(2);
      return '$' + formatted;
    }
  };

  const MoverCard = ({ mover, index }: { mover: MoverData; index: number }) => {
    const isGainer = mover.change >= 0;

    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          delay: 0.15 + index * 0.05,
          type: "spring",
          stiffness: 300,
          damping: 20
        }}
        onClick={() => handleMoverClick(mover.symbol)}
        className="relative group cursor-pointer"
      >
        <div className="bg-gradient-to-br from-gray-800/40 to-gray-900/40 backdrop-blur-sm hover:from-gray-800/60 hover:to-gray-900/60 rounded-2xl p-4 transition-all duration-300 border border-white/5 hover:border-white/10 active:scale-[0.98]">
          {/* Top Section - Logo, Symbol & Name */}
          <div className="flex items-start gap-3 mb-3">
            <div className="w-9 h-9 rounded-full bg-gray-700/50 flex items-center justify-center overflow-hidden flex-shrink-0">
              {mover.image ? (
                <img
                  src={mover.image}
                  alt={mover.symbol}
                  className="w-7 h-7 rounded-full"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                    e.currentTarget.nextElementSibling?.classList.remove('hidden');
                  }}
                />
              ) : null}
              <span className={`text-gray-400 font-bold text-xs ${mover.image ? 'hidden' : ''}`}>
                {mover.symbol.slice(0, 2)}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-white font-bold text-base tracking-tight mb-0.5 truncate">
                {mover.symbol.length > 6 ? mover.symbol.slice(0, 6) + '…' : mover.symbol}
              </h3>
              <p className="text-gray-500 text-[11px] font-medium truncate">
                {mover.name}
              </p>
            </div>
          </div>

          {/* Bottom Section - Price & Change */}
          <div className="flex items-end justify-between gap-2">
            <div className="text-gray-300 font-semibold text-sm truncate">
              {formatPrice(mover.price)}
            </div>
            <div
              className={`font-bold text-xs px-2 py-1 rounded-lg whitespace-nowrap flex-shrink-0 ${
                isGainer
                  ? 'text-green-400 bg-green-500/15'
                  : 'text-red-400 bg-red-500/15'
              }`}
            >
              {isGainer ? '+' : ''}
              {mover.change.toFixed(1)}%
            </div>
          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        delay: 0.2,
        type: "spring",
        stiffness: 200,
        damping: 25
      }}
      className="glass-blue-card rounded-3xl p-5 shadow-2xl"
    >
      {/* Header with Timeframe Switcher */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-white font-bold text-xl tracking-tight">
            🔥 {t('top_movers_title')}
          </h2>

          {/* Timeframe Switcher */}
          <div className="flex gap-1 bg-gray-800/40 rounded-xl p-1">
            {(['1h', '24h', '7d'] as Timeframe[]).map((tf) => (
              <button
                key={tf}
                onClick={() => handleTimeframeChange(tf)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  timeframe === tf
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      )}

      {/* Grid Layout */}
      {!loading && (
        <AnimatePresence mode="wait">
          <motion.div
            key={`${timeframe}-${showAll}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="grid grid-cols-2 gap-4"
          >
            {/* Gainers Column */}
            <div>
              <div className="flex items-center gap-1.5 mb-3 px-1">
                <span className="text-base">🔥</span>
                <span className="text-gray-400 text-xs font-semibold uppercase tracking-wider">{t('gainers')}</span>
              </div>
              <div className="space-y-2.5">
                {gainers.map((mover, index) => (
                  <MoverCard key={mover.symbol} mover={mover} index={index} />
                ))}
              </div>
            </div>

            {/* Losers Column */}
            <div>
              <div className="flex items-center gap-1.5 mb-3 px-1">
                <span className="text-base">📉</span>
                <span className="text-gray-400 text-xs font-semibold uppercase tracking-wider">{t('losers')}</span>
              </div>
              <div className="space-y-2.5">
                {losers.map((mover, index) => (
                  <MoverCard key={mover.symbol} mover={mover} index={index} />
                ))}
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      )}

      {/* Show More / Show Less Button */}
      {!loading && (
        <motion.button
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          onClick={handleShowAllToggle}
          className="w-full mt-4 py-2.5 bg-gray-800/30 hover:bg-gray-800/50 rounded-xl text-sm font-medium text-blue-400 hover:text-blue-300 transition-all active:scale-98"
        >
          {showAll ? `↑ ${t('show_less')}` : `↓ ${t('show_more', { count: showAll ? 3 : 10 })}`}
        </motion.button>
      )}

    </motion.div>
  );
}
