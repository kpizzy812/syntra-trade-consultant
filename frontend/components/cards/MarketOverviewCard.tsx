/**
 * Enhanced Market Overview Card
 * Comprehensive market metrics: Fear & Greed + Global Market Data
 */

'use client';

import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { api } from '@/shared/api/client';

interface MarketOverviewData {
  fear_greed: {
    value: number;
    value_classification: string;
    emoji: string;
  };
  global: {
    total_market_cap: string;
    market_cap_change_24h?: number;
    total_volume_24h: string;
    btc_dominance?: number;
    eth_dominance?: number;
    active_cryptocurrencies?: number;
  };
  updated_at: string;
}

interface MarketOverviewCardProps {
  onEarnPoints?: (amount: number) => void;
}

export default function MarketOverviewCard({ onEarnPoints }: MarketOverviewCardProps = {}) {
  const t = useTranslations('home.market');
  const router = useRouter();
  const [data, setData] = useState<MarketOverviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMarketOverview = async () => {
      try {
        const response = await api.market.getOverview();
        console.log('Market Overview API Response:', response);

        // Validate response has required data
        if (!response || !response.global) {
          throw new Error('Invalid API response structure');
        }

        setData(response);
      } catch (error) {
        console.error('Failed to fetch market overview:', error);
        // Fallback data
        setData({
          fear_greed: {
            value: 50,
            value_classification: 'Neutral',
            emoji: '😐',
          },
          global: {
            total_market_cap: '$2.1T',
            market_cap_change_24h: 0,
            total_volume_24h: '$120B',
            btc_dominance: 52.3,
            eth_dominance: 18.1,
            active_cryptocurrencies: 12543,
          },
          updated_at: new Date().toISOString(),
        });
      } finally {
        setLoading(false);
      }
    };

    fetchMarketOverview();
  }, []);

  if (loading) {
    return (
      <div className="glass-blue-card rounded-3xl p-5 animate-pulse">
        <div className="h-48 bg-gray-800/30 rounded-xl"></div>
      </div>
    );
  }

  if (!data) return null;

  const { fear_greed, global } = data;

  // Determine Fear & Greed color
  const getFGColor = (value: number) => {
    if (value < 25) return 'text-red-400';
    if (value < 46) return 'text-orange-400';
    if (value < 55) return 'text-yellow-400';
    if (value < 75) return 'text-green-400';
    return 'text-emerald-400';
  };

  const isMarketCapPositive = (global.market_cap_change_24h ?? 0) >= 0;

  // Handler for "What does it mean?" button
  const handleExplainMarket = () => {
    // Build the prompt with actual market data
    const promptTemplate = t('explain_market_prompt');
    const prompt = promptTemplate
      .replace('{fearGreed}', fear_greed.value.toString())
      .replace('{classification}', fear_greed.value_classification)
      .replace('{marketCap}', global.total_market_cap)
      .replace('{change24h}', (global.market_cap_change_24h ?? 0).toFixed(2))
      .replace('{volume}', global.total_volume_24h)
      .replace('{btcDom}', (global.btc_dominance ?? 0).toFixed(1))
      .replace('{ethDom}', (global.eth_dominance ?? 0).toFixed(1));

    // Encode prompt and navigate to chat with points parameter
    const encodedPrompt = encodeURIComponent(prompt);
    router.push(`/chat?prompt=${encodedPrompt}&points=15`);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-blue-card rounded-3xl p-5 shadow-2xl"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-bold text-xl tracking-tight">
          🌍 {t('overview_title')}
        </h2>
        <span className="text-gray-400 text-xs">{t('now')}</span>
      </div>

      {/* Top Section - Fear & Greed + Market Cap */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* Fear & Greed */}
        <motion.div
          whileTap={{ scale: 0.98 }}
          className="bg-gradient-to-br from-gray-800/40 to-gray-900/40 rounded-2xl p-4 cursor-pointer hover:from-gray-800/60 hover:to-gray-900/60 transition-all"
        >
          <div className="text-gray-400 text-xs font-semibold mb-2">
            {t('fear_greed')}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">{fear_greed.emoji}</span>
            <div>
              <div className={`text-2xl font-bold ${getFGColor(fear_greed.value)}`}>
                {fear_greed.value}
              </div>
              <div className={`text-[10px] font-medium ${getFGColor(fear_greed.value)}`}>
                {fear_greed.value_classification}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Market Cap */}
        <motion.div
          whileTap={{ scale: 0.98 }}
          className="bg-gradient-to-br from-gray-800/40 to-gray-900/40 rounded-2xl p-4 cursor-pointer hover:from-gray-800/60 hover:to-gray-900/60 transition-all"
        >
          <div className="text-gray-400 text-xs font-semibold mb-2">
            {t('total_market_cap')}
          </div>
          <div className="text-white text-xl font-bold mb-0.5">
            {global.total_market_cap}
          </div>
          <div
            className={`text-xs font-bold ${
              isMarketCapPositive ? 'text-green-400' : 'text-red-400'
            }`}
          >
            {isMarketCapPositive ? '+' : ''}
            {(global.market_cap_change_24h ?? 0).toFixed(2)}% 24h
          </div>
        </motion.div>
      </div>

      {/* Bottom Section - Metrics Grid */}
      <div className="grid grid-cols-3 gap-2">
        {/* Volume */}
        <div className="bg-gray-800/20 rounded-xl p-3">
          <div className="text-gray-500 text-[10px] font-semibold mb-1">
            {t('volume_24h')}
          </div>
          <div className="text-white text-sm font-bold">
            {global.total_volume_24h}
          </div>
        </div>

        {/* BTC Dominance */}
        <div className="bg-gray-800/20 rounded-xl p-3">
          <div className="text-gray-500 text-[10px] font-semibold mb-1">
            {t('btc_dominance')}
          </div>
          <div className="text-orange-400 text-sm font-bold">
            {(global.btc_dominance ?? 0).toFixed(1)}%
          </div>
        </div>

        {/* ETH Dominance */}
        <div className="bg-gray-800/20 rounded-xl p-3">
          <div className="text-gray-500 text-[10px] font-semibold mb-1">
            {t('eth_dominance')}
          </div>
          <div className="text-blue-400 text-sm font-bold">
            {(global.eth_dominance ?? 0).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Active Cryptos Count */}
      <div className="mt-3 text-center">
        <span className="text-gray-500 text-[10px]">
          {t('active_cryptocurrencies', { count: (global.active_cryptocurrencies ?? 0).toLocaleString() })}
        </span>
      </div>

      {/* "What does it mean?" Button */}
      <motion.button
        whileTap={{ scale: 0.97 }}
        onClick={handleExplainMarket}
        className="mt-4 w-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 hover:from-blue-500/30 hover:to-purple-500/30 text-blue-300 font-semibold py-3 px-4 rounded-xl transition-all duration-200 flex items-center justify-center gap-2 border border-blue-500/20"
      >
        <span className="text-lg">🤔</span>
        <span>{t('what_does_it_mean')}</span>
        {/* Points reward badge */}
        <div className="flex items-center gap-0.5 ml-1 px-1.5 py-0.5 bg-gradient-to-r from-blue-500/30 to-purple-500/30 rounded-full">
          <Image
            src="/syntra/$SYNTRA.png"
            alt="$SYNTRA"
            width={10}
            height={10}
            className="object-contain"
          />
          <span className="text-[10px] font-semibold text-blue-300">
            +15
          </span>
        </div>
      </motion.button>
    </motion.div>
  );
}
