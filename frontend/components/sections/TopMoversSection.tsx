/**
 * Top Movers Section Component
 * Отображает топ крипто по изменению за 24 часа (gainers и losers)
 */

'use client';

import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';
import { vibrate } from '@/shared/telegram/vibration';
import { api } from '@/shared/api/client';

interface MoverData {
  symbol: string;
  name: string;
  change_24h: number;
  price: string;
}

export default function TopMoversSection() {
  const [gainers, setGainers] = useState<MoverData[]>([]);
  const [losers, setLosers] = useState<MoverData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTopMovers = async () => {
      try {
        const response = await api.market.getTopMovers();
        setGainers(response.gainers);
        setLosers(response.losers);
      } catch (error) {
        console.error('Failed to fetch top movers:', error);
        // Fallback to mock data on error
        setGainers([
          { symbol: 'XRP', name: 'Ripple', change_24h: 12.5, price: '$0.58' },
          { symbol: 'ADA', name: 'Cardano', change_24h: 8.3, price: '$0.45' },
          { symbol: 'AVAX', name: 'Avalanche', change_24h: 6.7, price: '$35.20' },
        ]);
        setLosers([
          { symbol: 'DOGE', name: 'Dogecoin', change_24h: -8.2, price: '$0.082' },
          { symbol: 'SHIB', name: 'Shiba Inu', change_24h: -6.1, price: '$0.000009' },
          { symbol: 'MATIC', name: 'Polygon', change_24h: -4.5, price: '$0.78' },
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchTopMovers();
  }, []);

  const handleMoverClick = (symbol: string) => {
    vibrate('light');
    // TODO: Navigate to analytics
    console.log('Navigate to:', symbol);
  };

  const MoverCard = ({ mover, index }: { mover: MoverData; index: number }) => {
    const isGainer = mover.change_24h >= 0;

    return (
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.15 + index * 0.05 }}
        onClick={() => handleMoverClick(mover.symbol)}
        className="flex items-center justify-between p-3 bg-gray-800/30 hover:bg-gray-800/50 rounded-xl transition-all cursor-pointer active:scale-98"
      >
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-white font-bold text-sm">{mover.symbol}</span>
            <span className="text-gray-500 text-xs">{mover.name}</span>
          </div>
          <span className="text-gray-400 text-xs">{mover.price}</span>
        </div>
        <div
          className={`font-bold text-sm px-2 py-1 rounded-lg ${
            isGainer
              ? 'text-green-400 bg-green-500/10'
              : 'text-red-400 bg-red-500/10'
          }`}
        >
          {isGainer ? '+' : ''}
          {mover.change_24h.toFixed(1)}%
        </div>
      </motion.div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="glassmorphism-card rounded-2xl p-5"
    >
      <h2 className="text-white font-bold text-lg mb-3">Top Movers (24h)</h2>

      <div className="grid grid-cols-2 gap-3">
        {/* Gainers Column */}
        <div>
          <div className="flex items-center gap-1 mb-2 text-xs text-gray-400">
            <span>🔥</span>
            <span>Gainers</span>
          </div>
          <div className="space-y-2">
            {gainers.map((mover, index) => (
              <MoverCard key={mover.symbol} mover={mover} index={index} />
            ))}
          </div>
        </div>

        {/* Losers Column */}
        <div>
          <div className="flex items-center gap-1 mb-2 text-xs text-gray-400">
            <span>📉</span>
            <span>Losers</span>
          </div>
          <div className="space-y-2">
            {losers.map((mover, index) => (
              <MoverCard key={mover.symbol} mover={mover} index={index} />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 text-center">
        <button className="text-blue-400 text-sm hover:text-blue-300 transition-colors">
          View all market data →
        </button>
      </div>
    </motion.div>
  );
}
