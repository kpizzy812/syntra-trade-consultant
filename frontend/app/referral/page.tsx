/**
 * Referral Page
 * Отображает реферальную систему с QR кодом, статистикой и историей
 */

'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api } from '@/shared/api/client';
import Header from '@/components/layout/Header';
import toast from 'react-hot-toast';

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

export default function ReferralPage() {
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [link, setLink] = useState<ReferralLink | null>(null);
  const [history, setHistory] = useState<ReferralHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadReferralData();
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

  const copyLink = () => {
    if (link) {
      navigator.clipboard.writeText(link.referral_link);
      toast.success('Referral link copied!');
    }
  };

  const getTierColor = (tier: string) => {
    const colors: Record<string, string> = {
      bronze: 'from-orange-700 to-orange-900',
      silver: 'from-gray-400 to-gray-600',
      gold: 'from-yellow-400 to-yellow-600',
      platinum: 'from-cyan-400 to-blue-500',
    };
    return colors[tier.toLowerCase()] || 'from-gray-500 to-gray-700';
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
    <div className="min-h-screen bg-black mobile-body">
      <Header title="Referral Program" showBack={false} />

      <main className="px-4 pt-4 pb-24 space-y-4">
        {/* Referral Link Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glassmorphism-card rounded-2xl p-6"
        >
          <h2 className="text-white font-bold text-lg mb-4">Your Referral Link</h2>

          {/* QR Code */}
          {link && (
            <div className="mb-4 flex justify-center">
              <img
                src={link.qr_code_url}
                alt="QR Code"
                className="w-48 h-48 rounded-xl bg-white p-2"
              />
            </div>
          )}

          {/* Referral Code */}
          <div className="mb-3">
            <label className="text-gray-400 text-xs mb-1 block">Referral Code</label>
            <div className="glassmorphism rounded-xl px-4 py-3 text-center">
              <span className="text-white font-mono text-lg font-bold">
                {link?.referral_code}
              </span>
            </div>
          </div>

          {/* Referral Link */}
          <div className="mb-4">
            <label className="text-gray-400 text-xs mb-1 block">Referral Link</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={link?.referral_link || ''}
                readOnly
                className="flex-1 glassmorphism rounded-xl px-4 py-3 text-white text-sm font-mono bg-transparent border-0 focus:outline-none"
              />
              <button
                onClick={copyLink}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-medium transition-colors"
              >
                Copy
              </button>
            </div>
          </div>

          <p className="text-gray-400 text-xs text-center">
            Share your link and earn rewards when friends join!
          </p>
        </motion.div>

        {/* Stats Overview */}
        {stats && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glassmorphism-card rounded-2xl p-6"
          >
            <h2 className="text-white font-bold text-lg mb-4">Your Stats</h2>

            {/* Tier Badge */}
            <div className="mb-6">
              <div
                className={`bg-gradient-to-r ${getTierColor(stats.tier)} rounded-2xl p-4 text-center`}
              >
                <div className="text-4xl mb-2">{getTierIcon(stats.tier)}</div>
                <div className="text-white font-bold text-xl capitalize">{stats.tier} Tier</div>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-3 mb-6">
              <div className="glassmorphism rounded-xl p-4">
                <div className="text-gray-400 text-xs mb-1">Total Referrals</div>
                <div className="text-white font-bold text-2xl">{stats.total_referrals}</div>
              </div>
              <div className="glassmorphism rounded-xl p-4">
                <div className="text-gray-400 text-xs mb-1">Active</div>
                <div className="text-green-400 font-bold text-2xl">{stats.active_referrals}</div>
              </div>
              <div className="glassmorphism rounded-xl p-4">
                <div className="text-gray-400 text-xs mb-1">Premium Conversions</div>
                <div className="text-yellow-400 font-bold text-2xl">
                  {stats.premium_conversions}
                </div>
              </div>
              <div className="glassmorphism rounded-xl p-4">
                <div className="text-gray-400 text-xs mb-1">Conversion Rate</div>
                <div className="text-blue-400 font-bold text-2xl">
                  {stats.conversion_rate}%
                </div>
              </div>
            </div>

            {/* Tier Benefits */}
            <div className="glassmorphism rounded-xl p-4 mb-4">
              <div className="text-gray-400 text-xs mb-3">Tier Benefits</div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-300 text-sm">Monthly Bonus</span>
                  <span className="text-white font-medium">
                    +{stats.tier_benefits.monthly_bonus} requests
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300 text-sm">Subscription Discount</span>
                  <span className="text-green-400 font-medium">
                    {stats.tier_benefits.discount_percent}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300 text-sm">Revenue Share</span>
                  <span className="text-blue-400 font-medium">
                    {stats.tier_benefits.revenue_share_percent}%
                  </span>
                </div>
              </div>
            </div>

            {/* Next Tier Progress */}
            {stats.next_tier && (
              <div className="glassmorphism rounded-xl p-4">
                <div className="flex justify-between mb-2">
                  <span className="text-gray-400 text-xs">
                    Next Tier: {stats.next_tier.name}
                  </span>
                  <span className="text-gray-400 text-xs">
                    {stats.next_tier.referrals_needed} more needed
                  </span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all"
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

        {/* Referral History */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glassmorphism-card rounded-2xl p-6"
        >
          <h2 className="text-white font-bold text-lg mb-4">Referral History</h2>

          {history.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-gray-400 text-sm mb-2">No referrals yet</div>
              <div className="text-gray-500 text-xs">
                Share your link to start earning rewards!
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {history.map((ref) => (
                <div key={ref.id} className="glassmorphism rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="text-white font-medium">
                        {ref.referee_name}
                        {ref.is_premium && (
                          <span className="ml-2 text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">
                            Premium
                          </span>
                        )}
                      </div>
                      {ref.referee_username && (
                        <div className="text-gray-400 text-xs">@{ref.referee_username}</div>
                      )}
                    </div>
                    <div
                      className={`px-2 py-1 rounded text-xs font-medium ${
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
                  <div className="text-gray-400 text-xs">
                    Joined:{' '}
                    {ref.joined_at
                      ? new Date(ref.joined_at).toLocaleDateString()
                      : 'Unknown'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
}
