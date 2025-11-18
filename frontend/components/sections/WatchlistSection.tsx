/**
 * Watchlist Section Component
 * Отображает избранные монеты пользователя
 */

'use client';

import { motion } from 'framer-motion';
import { useState, useEffect } from 'react';
import { vibrate } from '@/shared/telegram/vibration';
import { api } from '@/shared/api/client';

interface CoinData {
  symbol: string;
  name: string;
  price: string;
  change_24h: number;
  icon?: string;
}

export default function WatchlistSection() {
  const [watchlist, setWatchlist] = useState<CoinData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchWatchlist = async () => {
      try {
        const response = await api.market.getWatchlist();
        setWatchlist(response.watchlist);
      } catch (error) {
        console.error('Failed to fetch watchlist:', error);
        // Fallback to mock data on error
        setWatchlist([
          { symbol: 'BTC', name: 'Bitcoin', price: '$45,230', change_24h: 2.4 },
          { symbol: 'ETH', name: 'Ethereum', price: '$2,890', change_24h: 1.8 },
          { symbol: 'SOL', name: 'Solana', price: '$108.50', change_24h: -0.5 },
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchWatchlist();
  }, []);

  const handleCoinClick = (symbol: string) => {
    vibrate('light');
    // TODO: Navigate to analytics page with selected symbol
    console.log('Navigate to analytics:', symbol);
  };

  const handleAddCoin = () => {
    vibrate('medium');
    // TODO: Open add coin modal
    console.log('Open add coin modal');
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="glassmorphism-card rounded-2xl p-5"
    >
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-white font-bold text-lg flex items-center gap-2">
          <span>⭐</span>
          <span>Your Watchlist</span>
          <span className="text-gray-400 text-sm font-normal">
            ({watchlist.length})
          </span>
        </h2>
        <button
          onClick={handleAddCoin}
          className="w-8 h-8 rounded-full bg-blue-600/20 hover:bg-blue-600/30 transition-colors flex items-center justify-center text-blue-400"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </button>
      </div>

      <div className="space-y-2">
        {watchlist.map((coin, index) => (
          <motion.div
            key={coin.symbol}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 + index * 0.05 }}
            onClick={() => handleCoinClick(coin.symbol)}
            className="flex items-center justify-between p-3 bg-gray-800/30 hover:bg-gray-800/50 rounded-xl transition-all cursor-pointer active:scale-98"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-blue-600/20 flex items-center justify-center">
                <span className="text-blue-400 font-bold text-sm">{coin.symbol}</span>
              </div>
              <div>
                <p className="text-white font-medium text-sm">{coin.name}</p>
                <p className="text-gray-400 text-xs">{coin.symbol}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-white font-bold text-sm">{coin.price}</p>
              <p
                className={`text-xs font-medium ${
                  coin.change_24h >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {coin.change_24h >= 0 ? '+' : ''}
                {coin.change_24h.toFixed(1)}%
              </p>
            </div>
          </motion.div>
        ))}

        {watchlist.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <div className="text-4xl mb-2">📊</div>
            <p className="text-sm">No coins in watchlist</p>
            <button
              onClick={handleAddCoin}
              className="mt-3 text-blue-400 text-sm hover:text-blue-300 transition-colors"
            >
              Add your first coin
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
}
