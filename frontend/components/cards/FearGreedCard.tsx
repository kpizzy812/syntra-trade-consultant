/**
 * Fear & Greed Index Card Component
 * Отображает индекс страха и жадности с визуальным индикатором
 */

'use client';

import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { api } from '@/shared/api/client';

interface FearGreedData {
  value: number;
  value_classification: string;
  timestamp: string;
}

export default function FearGreedCard() {
  const [data, setData] = useState<FearGreedData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFearGreed = async () => {
      try {
        const response = await api.market.getFearGreedIndex();
        setData({
          value: response.value,
          value_classification: response.value_classification,
          timestamp: response.timestamp,
        });
      } catch (error) {
        console.error('Failed to fetch Fear & Greed Index:', error);
        // Fallback to mock data on error
        setData({
          value: 50,
          value_classification: 'Neutral',
          timestamp: new Date().toISOString(),
        });
      } finally {
        setLoading(false);
      }
    };

    fetchFearGreed();
  }, []);

  if (loading) {
    return (
      <div className="glassmorphism-card rounded-2xl p-6 animate-pulse">
        <div className="h-40 bg-gray-800/30 rounded-xl"></div>
      </div>
    );
  }

  if (!data) return null;

  // Определяем цвет и эмодзи по значению
  const getColor = (value: number) => {
    if (value < 25) return 'text-red-400';
    if (value < 46) return 'text-orange-400';
    if (value < 55) return 'text-yellow-400';
    if (value < 75) return 'text-green-400';
    return 'text-emerald-400';
  };

  const getEmoji = (value: number) => {
    if (value < 25) return '😱';
    if (value < 46) return '😨';
    if (value < 55) return '😐';
    if (value < 75) return '🙂';
    return '🤑';
  };

  const getGradient = (value: number) => {
    if (value < 25) return 'from-red-500/20 to-red-700/20';
    if (value < 46) return 'from-orange-500/20 to-orange-700/20';
    if (value < 55) return 'from-yellow-500/20 to-yellow-700/20';
    if (value < 75) return 'from-green-500/20 to-green-700/20';
    return 'from-emerald-500/20 to-emerald-700/20';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glassmorphism-card rounded-2xl p-6"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-bold text-lg">Fear & Greed Index</h2>
        <span className="text-gray-400 text-xs">Now</span>
      </div>

      <div className={`bg-gradient-to-br ${getGradient(data.value)} rounded-xl p-6 border border-white/10`}>
        <div className="flex items-center justify-between mb-4">
          <div className="text-6xl">{getEmoji(data.value)}</div>
          <div className="text-right">
            <div className={`text-5xl font-bold ${getColor(data.value)}`}>
              {data.value}
            </div>
            <div className="text-gray-400 text-sm mt-1">/ 100</div>
          </div>
        </div>

        <div className="mb-3">
          <div className="w-full h-2 bg-gray-800/50 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${data.value}%` }}
              transition={{ duration: 1, ease: 'easeOut' }}
              className={`h-full bg-gradient-to-r ${
                data.value < 25
                  ? 'from-red-500 to-red-600'
                  : data.value < 46
                  ? 'from-orange-500 to-orange-600'
                  : data.value < 55
                  ? 'from-yellow-500 to-yellow-600'
                  : data.value < 75
                  ? 'from-green-500 to-green-600'
                  : 'from-emerald-500 to-emerald-600'
              }`}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>Extreme Fear</span>
          <span>Neutral</span>
          <span>Extreme Greed</span>
        </div>

        <div className="mt-4 text-center">
          <span className={`font-bold text-lg ${getColor(data.value)}`}>
            {data.value_classification}
          </span>
        </div>

        <div className="mt-3 text-center text-gray-400 text-xs">
          {data.value < 50
            ? 'Good time to buy? Market is fearful 🤔'
            : 'Market is greedy. Be cautious! 🚨'}
        </div>
      </div>
    </motion.div>
  );
}
