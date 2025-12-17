/**
 * CoinDetailModal Component
 * Модальное окно с подробной статистикой монеты и интерактивным графиком
 */

'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { api } from '@/shared/api/client';
import PriceChart from '@/components/charts/PriceChart';

interface CoinDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  symbol: string;
}

type Timeframe = '1' | '7' | '30' | '90';

export default function CoinDetailModal({ isOpen, onClose, symbol }: CoinDetailModalProps) {
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [timeframe, setTimeframe] = useState<Timeframe>('7');
  const [coinData, setCoinData] = useState<any>(null);
  const [chartData, setChartData] = useState<any[]>([]);
  const contentRef = useRef<HTMLDivElement>(null);

  // Прокрутка наверх при открытии модального окна
  useEffect(() => {
    if (isOpen && contentRef.current) {
      contentRef.current.scrollTop = 0;
    }
  }, [isOpen]);

  // Загрузка данных монеты
  useEffect(() => {
    if (!isOpen || !symbol) return;

    const fetchCoinData = async () => {
      setLoading(true);
      try {
        const data = await api.market.getCoinDetails(symbol);
        setCoinData(data);
      } catch (error) {
        console.error('Failed to fetch coin details:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCoinData();
  }, [isOpen, symbol]);

  // Загрузка графика
  useEffect(() => {
    if (!isOpen || !symbol) return;

    const fetchChartData = async () => {
      setChartLoading(true);
      try {
        const data = await api.market.getCoinChart(symbol, parseInt(timeframe));
        setChartData(data.prices || []);
      } catch (error) {
        console.error('Failed to fetch chart data:', error);
        setChartData([]);
      } finally {
        setChartLoading(false);
      }
    };

    fetchChartData();
  }, [isOpen, symbol, timeframe]);

  if (!isOpen) return null;

  const formatNumber = (num: number, decimals: number = 2) => {
    if (num >= 1_000_000_000) {
      return `$${(num / 1_000_000_000).toFixed(decimals)}B`;
    } else if (num >= 1_000_000) {
      return `$${(num / 1_000_000).toFixed(decimals)}M`;
    } else if (num >= 1000) {
      return `$${num.toLocaleString('en-US', { maximumFractionDigits: decimals })}`;
    } else if (num >= 1) {
      return `$${num.toFixed(decimals)}`;
    } else {
      return `$${num.toFixed(6)}`;
    }
  };

  const formatSupply = (num: number) => {
    if (num >= 1_000_000_000) {
      return `${(num / 1_000_000_000).toFixed(2)}B`;
    } else if (num >= 1_000_000) {
      return `${(num / 1_000_000).toFixed(2)}M`;
    } else {
      return num.toLocaleString('en-US');
    }
  };

  return (
    <div
      className="fixed inset-0 bg-[#0a0f1a] flex flex-col z-[9999]"
      style={{
        paddingTop: 'calc(env(safe-area-inset-top, 0px) + 56px)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
      onClick={onClose}
    >
      {/* Spacer для хедера */}
      <div className="shrink-0" style={{ height: '16px' }} />

      {/* Модальное окно занимает оставшееся пространство */}
      <motion.div
        initial={{ opacity: 0, y: 100 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 100 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="flex-1 rounded-t-3xl w-full flex flex-col overflow-hidden border-t border-x border-blue-500/30"
        style={{
          background: '#0f172a',
          boxShadow: '0 -4px 30px rgba(0, 0, 0, 0.8)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/5 shrink-0">
          <div className="flex items-center gap-3">
            {coinData?.image && (
              <img
                src={coinData.image}
                alt={symbol}
                className="w-10 h-10 rounded-full"
              />
            )}
            <div>
              <h2 className="text-white font-bold text-lg">{coinData?.name || symbol}</h2>
              <p className="text-gray-400 text-sm">{symbol.toUpperCase()}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-2"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div
          ref={contentRef}
          className="flex-1 overflow-y-auto overscroll-contain p-4 pb-6"
          style={{ WebkitOverflowScrolling: 'touch' }}
        >
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Price Section */}
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-3">
                <div className="text-2xl font-bold text-white mb-1">
                  {formatNumber(coinData?.current_price || 0)}
                </div>
                <div className={`text-sm font-medium ${
                  (coinData?.price_change_percentage_24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {(coinData?.price_change_percentage_24h || 0) >= 0 ? '+' : ''}
                  {(coinData?.price_change_percentage_24h || 0).toFixed(2)}%
                  <span className="text-gray-400 ml-2">24h</span>
                </div>
              </div>

              {/* Timeframe Selector */}
              <div className="flex gap-2 bg-blue-500/10 border border-blue-500/20 rounded-xl p-1">
                {(['1', '7', '30', '90'] as Timeframe[]).map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      timeframe === tf
                        ? 'bg-blue-600 text-white shadow-lg'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {tf}D
                  </button>
                ))}
              </div>

              {/* Chart */}
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2">
                {chartLoading ? (
                  <div className="flex items-center justify-center h-[160px]">
                    <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                ) : chartData.length > 0 ? (
                  <PriceChart
                    data={chartData}
                    isPositive={(coinData?.price_change_percentage_24h || 0) >= 0}
                    height={160}
                  />
                ) : (
                  <div className="flex items-center justify-center h-[160px] text-gray-400 text-sm">
                    No chart data available
                  </div>
                )}
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-2">
                {/* Market Cap */}
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2.5">
                  <div className="text-gray-400 text-[10px] mb-0.5">Market Cap</div>
                  <div className="text-white font-semibold text-sm">
                    {formatNumber(coinData?.market_cap || 0)}
                  </div>
                  <div className="text-gray-500 text-[10px] mt-0.5">
                    Rank #{coinData?.market_cap_rank || 'N/A'}
                  </div>
                </div>

                {/* Volume 24h */}
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2.5">
                  <div className="text-gray-400 text-[10px] mb-0.5">Volume (24h)</div>
                  <div className="text-white font-semibold text-sm">
                    {formatNumber(coinData?.total_volume || 0)}
                  </div>
                </div>

                {/* All-Time High */}
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2.5">
                  <div className="text-gray-400 text-[10px] mb-0.5">All-Time High</div>
                  <div className="text-white font-semibold text-sm">
                    {formatNumber(coinData?.ath || 0)}
                  </div>
                  <div className="text-red-400 text-[10px] mt-0.5">
                    {(coinData?.ath_change_percentage || 0).toFixed(1)}%
                  </div>
                </div>

                {/* All-Time Low */}
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2.5">
                  <div className="text-gray-400 text-[10px] mb-0.5">All-Time Low</div>
                  <div className="text-white font-semibold text-sm">
                    {formatNumber(coinData?.atl || 0)}
                  </div>
                  <div className="text-green-400 text-[10px] mt-0.5">
                    +{(coinData?.atl_change_percentage || 0).toFixed(1)}%
                  </div>
                </div>

                {/* Circulating Supply */}
                {coinData?.circulating_supply && (
                  <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2.5">
                    <div className="text-gray-400 text-[10px] mb-0.5">Circulating Supply</div>
                    <div className="text-white font-semibold text-sm">
                      {formatSupply(coinData.circulating_supply)}
                    </div>
                  </div>
                )}

                {/* Max Supply */}
                {coinData?.max_supply && (
                  <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2.5">
                    <div className="text-gray-400 text-[10px] mb-0.5">Max Supply</div>
                    <div className="text-white font-semibold text-sm">
                      {formatSupply(coinData.max_supply)}
                    </div>
                  </div>
                )}
              </div>

              {/* Price Changes */}
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2.5">
                <div className="text-gray-400 text-[10px] mb-1.5">Price Changes</div>
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400 text-xs">7 Days</span>
                    <span className={`font-semibold text-xs ${
                      (coinData?.price_change_percentage_7d || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {(coinData?.price_change_percentage_7d || 0) >= 0 ? '+' : ''}
                      {(coinData?.price_change_percentage_7d || 0).toFixed(2)}%
                    </span>
                  </div>
                  {coinData?.price_change_percentage_30d !== null && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400 text-xs">30 Days</span>
                      <span className={`font-semibold text-xs ${
                        (coinData?.price_change_percentage_30d || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {(coinData?.price_change_percentage_30d || 0) >= 0 ? '+' : ''}
                        {(coinData?.price_change_percentage_30d || 0).toFixed(2)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
