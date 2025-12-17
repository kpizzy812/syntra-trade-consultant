/**
 * Referral Page
 * Отображает реферальную систему с QR кодом, статистикой, тирами и историей
 */

'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api } from '@/shared/api/client';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import DesktopLayout from '@/components/layout/DesktopLayout';
import toast from 'react-hot-toast';
import { generateTelegramReferralLink, generateWebReferralLink, generateMiniAppReferralLink, generateQRCodeURL } from '@/lib/referral';
import { detectPlatform } from '@/lib/platform';
import { useTranslations } from 'next-intl';

interface ReferralStats {
  total_referrals: number;
  active_referrals: number;
  tier: string;
  tier_benefits: {
    monthly_bonus: number;
    discount_percent: number;
    revenue_share_percent: number;
  };
  premium_conversions: number;
  conversion_rate: number;
  leaderboard_rank: number | null;
  next_tier: {
    name: string;
    referrals_needed: number;
  } | null;
}

interface ReferralLink {
  referral_code: string;
  referral_link: string;
  qr_code_url: string;
}

interface ReferralHistoryItem {
  id: number;
  referee_name: string;
  referee_username: string | null;
  status: string;
  is_premium: boolean;
  joined_at: string;
  became_active_at: string | null;
}

// Tier data with benefits
const TIERS = [
  {
    name: 'bronze',
    range: '0-4',
    icon: '🥉',
    color: 'from-orange-700/20 to-orange-900/20',
    borderColor: 'border-orange-500/30',
    benefits: ['benefit1', 'benefit2'],
  },
  {
    name: 'silver',
    range: '5-14',
    icon: '🥈',
    color: 'from-gray-400/20 to-gray-600/20',
    borderColor: 'border-gray-400/30',
    benefits: ['benefit1', 'benefit2', 'benefit3'],
  },
  {
    name: 'gold',
    range: '15-49',
    icon: '🥇',
    color: 'from-yellow-400/20 to-yellow-600/20',
    borderColor: 'border-yellow-500/30',
    benefits: ['benefit1', 'benefit2', 'benefit3'],
  },
  {
    name: 'platinum',
    range: '50+',
    icon: '💎',
    color: 'from-cyan-400/20 to-blue-500/20',
    borderColor: 'border-cyan-400/30',
    benefits: ['benefit1', 'benefit2', 'benefit3'],
  },
];

type LinkType = 'miniapp' | 'web' | 'bot';

export default function ReferralPage() {
  const t = useTranslations('referral');
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [link, setLink] = useState<ReferralLink | null>(null);
  const [history, setHistory] = useState<ReferralHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [linkType, setLinkType] = useState<LinkType>('miniapp');

  useEffect(() => {
    loadReferralData();
    // Автоопределение типа ссылки на основе платформы
    const detectedPlatform = detectPlatform();
    if (detectedPlatform === 'telegram') {
      setLinkType('miniapp');
    }
  }, []);

  const loadReferralData = async () => {
    try {
      const [statsData, linkData, historyData] = await Promise.all([
        api.referral.getStats(),
        api.referral.getLink(),
        api.referral.getHistory(20),
      ]);

      setStats(statsData);
      setLink(linkData);
      setHistory(historyData.referrals);
    } catch (error) {
      console.error('Failed to load referral data:', error);
      toast.error('Failed to load referral data');
    } finally {
      setLoading(false);
    }
  };

  const getCurrentReferralLink = () => {
    if (!link) return '';

    switch (linkType) {
      case 'miniapp':
        return generateMiniAppReferralLink(link.referral_code);
      case 'bot':
        return generateTelegramReferralLink(link.referral_code);
      case 'web':
      default:
        return generateWebReferralLink({
          code: link.referral_code,
          utm_source: 'referral',
          utm_medium: 'web',
          utm_campaign: 'friend_invite',
        });
    }
  };

  const getLinkTypeLabel = () => {
    switch (linkType) {
      case 'miniapp':
        return t('link_type_miniapp');
      case 'bot':
        return t('link_type_bot');
      case 'web':
        return t('link_type_web');
    }
  };

  const getLinkTypeIcon = () => {
    switch (linkType) {
      case 'miniapp':
        return '📱';
      case 'bot':
        return '🤖';
      case 'web':
        return '🌐';
    }
  };

  const copyLink = () => {
    const currentLink = getCurrentReferralLink();
    if (currentLink) {
      navigator.clipboard.writeText(currentLink);
      toast.success(t('link_copied'));
    }
  };

  const getTierIcon = (tier: string) => {
    const icons: Record<string, string> = {
      bronze: '🥉',
      silver: '🥈',
      gold: '🥇',
      platinum: '💎',
    };
    return icons[tier.toLowerCase()] || '🏆';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <DesktopLayout>
      <div className="bg-black flex flex-col h-full">
        <Header title={t('title')} showBack={false} />

        <main className="flex-1 overflow-y-auto px-4 pt-4 pb-24 lg:max-w-[1200px] lg:mx-auto lg:w-full">
          <div className="max-w-5xl mx-auto space-y-4">

            {/* Compact Header: Tier + Stats in One Card */}
            {stats && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gradient-to-br from-blue-500/10 via-purple-600/5 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-2xl p-4 shadow-lg"
              >
                {/* Tier Badge + Quick Stats */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-3xl">{getTierIcon(stats.tier)}</span>
                    <div>
                      <div className="text-lg font-bold text-white capitalize">{stats.tier}</div>
                      <p className="text-xs text-gray-400">
                        {stats.total_referrals} refs • {stats.active_referrals} active
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-400">{t('conversion')}</div>
                    <div className="text-base font-bold text-blue-400">{stats.conversion_rate}%</div>
                  </div>
                </div>

                {/* Compact Benefits Row */}
                <div className="flex gap-2 mb-3">
                  <div className="flex-1 bg-blue-900/20 rounded-lg p-2 border border-blue-500/10">
                    <div className="text-[10px] text-gray-400 mb-0.5">Bonus</div>
                    <div className="text-sm font-bold text-white">+{stats.tier_benefits.monthly_bonus}</div>
                  </div>
                  <div className="flex-1 bg-blue-900/20 rounded-lg p-2 border border-blue-500/10">
                    <div className="text-[10px] text-gray-400 mb-0.5">Discount</div>
                    <div className="text-sm font-bold text-green-400">{stats.tier_benefits.discount_percent}%</div>
                  </div>
                  <div className="flex-1 bg-blue-900/20 rounded-lg p-2 border border-blue-500/10">
                    <div className="text-[10px] text-gray-400 mb-0.5">Revenue</div>
                    <div className="text-sm font-bold text-purple-400">{stats.tier_benefits.revenue_share_percent}%</div>
                  </div>
                </div>

                {/* Next Tier Progress */}
                {stats.next_tier && (
                  <div>
                    <div className="flex justify-between mb-1.5">
                      <span className="text-xs text-gray-400">
                        {t('next_tier')}: {stats.next_tier.name}
                      </span>
                      <span className="text-xs text-gray-400">
                        {stats.next_tier.referrals_needed} {t('more_needed')}
                      </span>
                    </div>
                    <div className="w-full bg-gray-800 rounded-full h-1.5">
                      <div
                        className="bg-gradient-to-r from-blue-500 to-purple-500 h-1.5 rounded-full transition-all"
                        style={{
                          width: `${Math.min(
                            ((stats.total_referrals % 50) / stats.next_tier.referrals_needed) * 100,
                            100
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* Referral Link Card - Compact */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-gradient-to-br from-blue-500/10 via-blue-600/5 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-2xl p-4 shadow-lg"
            >
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-white font-bold text-base flex items-center gap-2">
                  <span className="text-xl">{getLinkTypeIcon()}</span>
                  {t('your_link')}
                </h2>
              </div>

              {/* Link Type Switcher - Compact */}
              <div className="mb-3">
                <div className="flex gap-2">
                  {(['miniapp', 'web', 'bot'] as LinkType[]).map((type) => (
                    <button
                      key={type}
                      onClick={() => setLinkType(type)}
                      className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                        linkType === type
                          ? 'bg-blue-500 text-white'
                          : 'bg-blue-900/30 text-gray-400 border border-blue-500/10'
                      }`}
                    >
                      {type === 'miniapp' && '📱'}
                      {type === 'web' && '🌐'}
                      {type === 'bot' && '🤖'}
                    </button>
                  ))}
                </div>
                <p className="text-gray-500 text-[10px] mt-1.5">{t(`link_type_${linkType}_desc`)}</p>
              </div>

              {/* QR Code - Smaller & Hidden on Mobile */}
              {link && (
                <div className="mb-3 hidden sm:flex justify-center">
                  <img
                    src={generateQRCodeURL(getCurrentReferralLink(), 150)}
                    alt="QR Code"
                    className="w-32 h-32 rounded-lg bg-white p-1.5"
                  />
                </div>
              )}

              {/* Referral Code - Compact */}
              <div className="mb-2">
                <div className="bg-blue-900/20 rounded-lg px-3 py-2 text-center border border-blue-500/10">
                  <span className="text-white font-mono text-base font-bold">
                    {link?.referral_code}
                  </span>
                </div>
              </div>

              {/* Referral Link - Compact */}
              <div className="flex gap-2 items-center">
                <div className="flex-1 bg-blue-900/20 rounded-lg border border-blue-500/10 px-3 py-2.5">
                  <input
                    type="text"
                    value={getCurrentReferralLink()}
                    readOnly
                    className="w-full text-white text-[10px] font-mono bg-transparent border-0 focus:outline-none"
                  />
                </div>
                <button
                  onClick={copyLink}
                  className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500 text-white text-sm font-medium transition-all active:scale-95"
                >
                  {t('copy')}
                </button>
              </div>
            </motion.div>

            {/* Compact Bonuses Info */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 backdrop-blur-xl border border-green-500/20 rounded-2xl p-4 shadow-lg"
            >
              <h3 className="text-white font-bold text-sm mb-2 flex items-center gap-1.5">
                🎁 {t('bonuses_title')}
              </h3>
              <div className="space-y-2 text-xs">
                <div className="flex items-start gap-2">
                  <span className="text-green-400 mt-0.5">→</span>
                  <div>
                    <span className="text-green-400 font-medium">{t('friend_gets')}: </span>
                    <span className="text-gray-300">{t('friend_bonus')}</span>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-blue-400 mt-0.5">→</span>
                  <div>
                    <span className="text-blue-400 font-medium">{t('you_get')}: </span>
                    <span className="text-gray-300">{t('you_bonus')}</span>
                  </div>
                </div>
                <p className="text-gray-500 text-[10px] italic">{t('activation_note')}</p>
              </div>
            </motion.div>

            {/* All Tiers - Compact Grid */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="space-y-2"
            >
              <h3 className="text-white font-bold text-sm px-1">{t('tiers_title')}</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {TIERS.map((tier) => {
                  const isCurrentTier = stats?.tier.toLowerCase() === tier.name;
                  return (
                    <div
                      key={tier.name}
                      className={`relative bg-gradient-to-br ${tier.color} backdrop-blur-sm rounded-xl p-3 border ${tier.borderColor} ${
                        isCurrentTier ? 'ring-1 ring-white/20' : ''
                      }`}
                    >
                      {isCurrentTier && (
                        <div className="absolute -top-1.5 -right-1.5 bg-blue-500 text-white text-[9px] px-1.5 py-0.5 rounded-full font-bold">
                          YOU
                        </div>
                      )}
                      <div className="flex items-center gap-1.5 mb-2">
                        <span className="text-xl">{tier.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-white font-bold text-xs capitalize truncate">{t(tier.name)}</div>
                          <div className="text-gray-400 text-[9px]">{t(`${tier.name}_range`)}</div>
                        </div>
                      </div>
                      <div className="space-y-0.5">
                        {tier.benefits.map((benefit, idx) => (
                          <div key={idx} className="flex items-start gap-1 text-[10px]">
                            <span className="text-green-400 text-[9px] mt-0.5">✓</span>
                            <span className="text-gray-300 leading-tight">{t(`${tier.name}_${benefit}`)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>

            {/* Revenue Share - Compact */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="bg-gradient-to-br from-yellow-500/10 to-orange-500/10 backdrop-blur-xl border border-yellow-500/20 rounded-2xl p-4 shadow-lg"
            >
              <h3 className="text-white font-bold text-sm mb-2 flex items-center gap-1.5">
                💰 {t('revenue_share_title')}
              </h3>
              <p className="text-gray-300 text-xs mb-2">{t('revenue_share_desc')}</p>
              <div className="bg-yellow-900/20 rounded-lg p-2.5 border border-yellow-500/10">
                <p className="text-yellow-400 text-xs font-medium">{t('revenue_share_example')}</p>
              </div>
            </motion.div>

            {/* Referral History - Compact */}
            {history.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="bg-gradient-to-br from-blue-500/10 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-2xl p-4 shadow-lg"
              >
                <h3 className="text-white font-bold text-sm mb-3">{t('history')}</h3>

                <div className="space-y-2">
                  {history.slice(0, 5).map((ref) => (
                    <div key={ref.id} className="bg-blue-900/20 border border-blue-500/10 rounded-lg p-2.5">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <div className="text-white font-medium text-xs truncate">
                              {ref.referee_name}
                            </div>
                            {ref.is_premium && (
                              <span className="text-[9px] bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded shrink-0">
                                Premium
                              </span>
                            )}
                          </div>
                          {ref.referee_username && (
                            <div className="text-gray-400 text-[10px]">@{ref.referee_username}</div>
                          )}
                        </div>
                        <div
                          className={`px-2 py-0.5 rounded text-[9px] font-medium shrink-0 ml-2 ${
                            ref.status === 'active'
                              ? 'bg-green-500/20 text-green-400'
                              : ref.status === 'pending'
                              ? 'bg-yellow-500/20 text-yellow-400'
                              : 'bg-gray-500/20 text-gray-400'
                          }`}
                        >
                          {ref.status}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {history.length > 5 && (
                  <div className="text-center mt-2">
                    <span className="text-gray-500 text-[10px]">
                      +{history.length - 5} more
                    </span>
                  </div>
                )}
              </motion.div>
            )}
          </div>
        </main>

        <TabBar />
      </div>
    </DesktopLayout>
  );
}
