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

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glassmorphism-card rounded-2xl p-4"
    >
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-white font-semibold text-sm">Fear & Greed Index</h2>
        <span className="text-gray-400 text-xs">Now</span>
      </div>

      {/* Компактный полукруглый индикатор */}
      <div className="relative flex items-center justify-center">
        {/* SVG полукруг */}
        <svg
          width="200"
          height="110"
          viewBox="0 0 200 110"
          className="relative"
        >
          {/* Фоновая дуга */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="rgba(255, 255, 255, 0.1)"
            strokeWidth="12"
            strokeLinecap="round"
          />

          {/* Цветная дуга прогресса */}
          <motion.path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke={`url(#gradient-${data.value})`}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray="251.2"
            initial={{ strokeDashoffset: 251.2 }}
            animate={{ strokeDashoffset: 251.2 - (251.2 * data.value) / 100 }}
            transition={{ duration: 1.5, ease: 'easeOut' }}
          />

          {/* Градиенты для разных значений */}
          <defs>
            <linearGradient id={`gradient-${data.value}`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={data.value < 25 ? '#ef4444' : data.value < 46 ? '#f97316' : data.value < 55 ? '#eab308' : data.value < 75 ? '#22c55e' : '#10b981'} />
              <stop offset="100%" stopColor={data.value < 25 ? '#dc2626' : data.value < 46 ? '#ea580c' : data.value < 55 ? '#ca8a04' : data.value < 75 ? '#16a34a' : '#059669'} />
            </linearGradient>
          </defs>
        </svg>

        {/* Центральное значение */}
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/4 text-center">
          <div className="text-3xl mb-1">{getEmoji(data.value)}</div>
          <div className={`text-3xl font-bold ${getColor(data.value)}`}>
            {data.value}
          </div>
          <div className={`text-xs font-medium mt-1 ${getColor(data.value)}`}>
            {data.value_classification}
          </div>
        </div>
      </div>

      {/* Компактные подписи */}
      <div className="flex items-center justify-between text-[10px] text-gray-500 mt-1 px-2">
        <span>Fear</span>
        <span className="text-gray-600">Neutral</span>
        <span>Greed</span>
      </div>
    </motion.div>
  );
}
