/**
 * Coin Detail Page
 * Полноэкранная страница с детальной информацией о монете
 */

'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import DesktopLayout from '@/components/layout/DesktopLayout';
import PriceChart from '@/components/charts/PriceChart';
import { api } from '@/shared/api/client';
import { usePlatform } from '@/lib/platform';
import { vibrate } from '@/shared/telegram/vibration';

type Timeframe = '1' | '7' | '30' | '90';

export default function CoinDetailPage() {
  const params = useParams();
  const router = useRouter();
  const symbol = (params.symbol as string)?.toUpperCase() || '';
  const t = useTranslations('coin');
  const { platformType } = usePlatform();
  const isDesktop = platformType === 'web';

  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [timeframe, setTimeframe] = useState<Timeframe>('7');
  const [coinData, setCoinData] = useState<any>(null);
  const [chartData, setChartData] = useState<any[]>([]);

  // Загрузка данных монеты
  useEffect(() => {
    if (!symbol) return;

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
  }, [symbol]);

  // Загрузка графика
  useEffect(() => {
    if (!symbol) return;

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
  }, [symbol, timeframe]);

  const handleTimeframeChange = (tf: Timeframe) => {
    vibrate('light');
    setTimeframe(tf);
  };

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
    <DesktopLayout>
      <div className={`flex flex-col h-full ${isDesktop ? 'bg-black' : 'bg-black mobile-body'}`}>
        <Header
          title={coinData?.name || symbol}
          showBack={true}
          onBack={() => router.back()}
        />

        <main className={`px-4 pt-4 ${isDesktop ? 'flex-1 overflow-y-auto max-w-[800px] mx-auto w-full pb-8' : 'mobile-scrollable pb-24'}`}>
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-10 h-10 border-3 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              {/* Coin Header */}
              <div className="glass-blue-card rounded-2xl p-4">
                <div className="flex items-center gap-4 mb-4">
                  {coinData?.image && (
                    <img
                      src={coinData.image}
                      alt={symbol}
                      className="w-14 h-14 rounded-full"
                    />
                  )}
                  <div className="flex-1">
                    <h1 className="text-white font-bold text-2xl">{coinData?.name || symbol}</h1>
                    <p className="text-gray-400 text-sm">{symbol}</p>
                  </div>
                  {coinData?.market_cap_rank && (
                    <div className="bg-blue-500/20 px-3 py-1 rounded-full">
                      <span className="text-blue-400 text-sm font-semibold">#{coinData.market_cap_rank}</span>
                    </div>
                  )}
                </div>

                {/* Price */}
                <div className="flex items-end justify-between">
                  <div>
                    <div className="text-3xl font-bold text-white">
                      {formatNumber(coinData?.current_price || 0)}
                    </div>
                    <div className={`text-base font-semibold mt-1 ${
                      (coinData?.price_change_percentage_24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {(coinData?.price_change_percentage_24h || 0) >= 0 ? '+' : ''}
                      {(coinData?.price_change_percentage_24h || 0).toFixed(2)}%
                      <span className="text-gray-500 ml-2 text-sm">24h</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Chart Section */}
              <div className="glass-blue-card rounded-2xl p-4">
                {/* Timeframe Selector */}
                <div className="flex gap-2 mb-4">
                  {(['1', '7', '30', '90'] as Timeframe[]).map((tf) => (
                    <button
                      key={tf}
                      onClick={() => handleTimeframeChange(tf)}
                      className={`flex-1 px-3 py-2 rounded-xl text-sm font-semibold transition-all ${
                        timeframe === tf
                          ? 'bg-blue-600 text-white shadow-lg'
                          : 'bg-gray-800/50 text-gray-400 hover:text-white'
                      }`}
                    >
                      {tf}D
                    </button>
                  ))}
                </div>

                {/* Chart */}
                <div className="h-[200px]">
                  {chartLoading ? (
                    <div className="flex items-center justify-center h-full">
                      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                    </div>
                  ) : chartData.length > 0 ? (
                    <PriceChart
                      data={chartData}
                      isPositive={(coinData?.price_change_percentage_24h || 0) >= 0}
                      height={200}
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                      {t('no_chart_data') || 'No chart data available'}
                    </div>
                  )}
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-3">
                {/* Market Cap */}
                <div className="glass-blue-card rounded-xl p-3">
                  <div className="text-gray-400 text-xs mb-1">{t('market_cap') || 'Market Cap'}</div>
                  <div className="text-white font-semibold text-base">
                    {formatNumber(coinData?.market_cap || 0)}
                  </div>
                </div>

                {/* Volume 24h */}
                <div className="glass-blue-card rounded-xl p-3">
                  <div className="text-gray-400 text-xs mb-1">{t('volume_24h') || 'Volume (24h)'}</div>
                  <div className="text-white font-semibold text-base">
                    {formatNumber(coinData?.total_volume || 0)}
                  </div>
                </div>

                {/* All-Time High */}
                <div className="glass-blue-card rounded-xl p-3">
                  <div className="text-gray-400 text-xs mb-1">{t('ath') || 'All-Time High'}</div>
                  <div className="text-white font-semibold text-base">
                    {formatNumber(coinData?.ath || 0)}
                  </div>
                  <div className="text-red-400 text-xs mt-0.5">
                    {(coinData?.ath_change_percentage || 0).toFixed(1)}%
                  </div>
                </div>

                {/* All-Time Low */}
                <div className="glass-blue-card rounded-xl p-3">
                  <div className="text-gray-400 text-xs mb-1">{t('atl') || 'All-Time Low'}</div>
                  <div className="text-white font-semibold text-base">
                    {formatNumber(coinData?.atl || 0)}
                  </div>
                  <div className="text-green-400 text-xs mt-0.5">
                    +{(coinData?.atl_change_percentage || 0).toFixed(1)}%
                  </div>
                </div>

                {/* Circulating Supply */}
                {coinData?.circulating_supply && (
                  <div className="glass-blue-card rounded-xl p-3">
                    <div className="text-gray-400 text-xs mb-1">{t('circulating_supply') || 'Circulating Supply'}</div>
                    <div className="text-white font-semibold text-base">
                      {formatSupply(coinData.circulating_supply)}
                    </div>
                  </div>
                )}

                {/* Max Supply */}
                {coinData?.max_supply && (
                  <div className="glass-blue-card rounded-xl p-3">
                    <div className="text-gray-400 text-xs mb-1">{t('max_supply') || 'Max Supply'}</div>
                    <div className="text-white font-semibold text-base">
                      {formatSupply(coinData.max_supply)}
                    </div>
                  </div>
                )}
              </div>

              {/* Price Changes */}
              <div className="glass-blue-card rounded-xl p-4">
                <div className="text-gray-400 text-xs mb-3">{t('price_changes') || 'Price Changes'}</div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400 text-sm">24h</span>
                    <span className={`font-semibold text-sm ${
                      (coinData?.price_change_percentage_24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {(coinData?.price_change_percentage_24h || 0) >= 0 ? '+' : ''}
                      {(coinData?.price_change_percentage_24h || 0).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400 text-sm">7d</span>
                    <span className={`font-semibold text-sm ${
                      (coinData?.price_change_percentage_7d || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {(coinData?.price_change_percentage_7d || 0) >= 0 ? '+' : ''}
                      {(coinData?.price_change_percentage_7d || 0).toFixed(2)}%
                    </span>
                  </div>
                  {coinData?.price_change_percentage_30d !== null && coinData?.price_change_percentage_30d !== undefined && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400 text-sm">30d</span>
                      <span className={`font-semibold text-sm ${
                        (coinData?.price_change_percentage_30d || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {(coinData?.price_change_percentage_30d || 0) >= 0 ? '+' : ''}
                        {(coinData?.price_change_percentage_30d || 0).toFixed(2)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Ask AI Button */}
              <button
                onClick={() => {
                  vibrate('medium');
                  router.push(`/chat?prompt=${encodeURIComponent(`Analyze ${symbol} - give me a detailed analysis`)}`);
                }}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 rounded-2xl transition-colors flex items-center justify-center gap-2 active:scale-98"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
                </svg>
                {t('ask_ai') || `Ask AI about ${symbol}`}
              </button>
            </motion.div>
          )}
        </main>

        <TabBar />
      </div>
    </DesktopLayout>
  );
}
