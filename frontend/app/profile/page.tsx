/**
 * Profile Page
 * Отображает профиль пользователя, подписку, статистику и настройки
 */

'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api } from '@/shared/api/client';
import Header from '@/components/layout/Header';
import PremiumPurchaseModal from '@/components/modals/PremiumPurchaseModal';
import toast from 'react-hot-toast';

interface ProfileData {
  user: {
    id: number;
    telegram_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
    language: string;
    is_admin: boolean;
    created_at: string;
    last_activity: string;
  };
  subscription: {
    tier: string;
    is_active: boolean;
    started_at: string | null;
    expires_at: string | null;
    is_trial: boolean;
    trial_ends_at: string | null;
    auto_renew: boolean;
    daily_limit: number;
    requests_used_today: number;
    requests_remaining: number;
  };
  referral: {
    tier: string;
    total_referrals: number;
    active_referrals: number;
    monthly_bonus: number;
    discount_percent: number;
    revenue_share_percent: number;
  };
  balance: {
    balance_usd: number;
    earned_total_usd: number;
    withdrawn_total_usd: number;
    spent_total_usd: number;
    last_payout_at: string | null;
  };
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showPremiumModal, setShowPremiumModal] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const data = await api.profile.getProfile();
      setProfile(data);
    } catch (error) {
      console.error('Failed to load profile:', error);
      toast.error('Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const handleLanguageChange = async (newLanguage: string) => {
    try {
      await api.profile.updateSettings({ language: newLanguage });
      toast.success(`Language changed to ${newLanguage.toUpperCase()}`);

      // Update local state
      if (profile) {
        setProfile({
          ...profile,
          user: {
            ...profile.user,
            language: newLanguage,
          },
        });
      }
    } catch (error) {
      console.error('Failed to update language:', error);
      toast.error('Failed to update language');
    }
  };

  const getTierColor = (tier: string) => {
    const colors: Record<string, string> = {
      free: 'from-gray-500 to-gray-700',
      basic: 'from-blue-500 to-blue-700',
      premium: 'from-purple-500 to-purple-700',
      vip: 'from-yellow-400 to-yellow-600',
    };
    return colors[tier.toLowerCase()] || 'from-gray-500 to-gray-700';
  };

  const getTierIcon = (tier: string) => {
    const icons: Record<string, string> = {
      free: '🆓',
      basic: '⭐',
      premium: '💎',
      vip: '👑',
    };
    return icons[tier.toLowerCase()] || '🆓';
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  const getDaysRemaining = (expiresAt: string | null) => {
    if (!expiresAt) return null;
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diff = expiry.getTime() - now.getTime();
    return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Failed to load profile</div>
      </div>
    );
  }

  return (
    <div className="bg-black mobile-body">
      <Header title="Profile" showBack={false} />

      <main className="mobile-scrollable px-4 pt-4 pb-24 space-y-4">
        {/* User Info Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glassmorphism-card rounded-2xl p-6"
        >
          <div className="flex items-center gap-4 mb-4">
            {/* Avatar */}
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-2xl">
              {profile.user.first_name?.[0]?.toUpperCase() || '👤'}
            </div>

            {/* User Info */}
            <div className="flex-1">
              <h2 className="text-white font-bold text-lg">
                {profile.user.first_name} {profile.user.last_name}
              </h2>
              {profile.user.username && (
                <div className="text-gray-400 text-sm">@{profile.user.username}</div>
              )}
              <div className="text-gray-500 text-xs mt-1">
                Joined {formatDate(profile.user.created_at)}
              </div>
            </div>
          </div>

          {profile.user.is_admin && (
            <div className="bg-yellow-500/20 text-yellow-400 px-3 py-1 rounded-full text-xs font-medium inline-block">
              Admin
            </div>
          )}
        </motion.div>

        {/* Subscription Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glassmorphism-card rounded-2xl p-6"
        >
          <h2 className="text-white font-bold text-lg mb-4">Subscription</h2>

          {/* Tier Badge */}
          <div className="mb-6">
            <div
              className={`bg-gradient-to-r ${getTierColor(profile.subscription.tier)} rounded-2xl p-4 text-center`}
            >
              <div className="text-4xl mb-2">{getTierIcon(profile.subscription.tier)}</div>
              <div className="text-white font-bold text-xl capitalize">
                {profile.subscription.tier} Plan
              </div>
              {profile.subscription.is_trial && (
                <div className="text-sm text-white/80 mt-1">Trial Period</div>
              )}
            </div>
          </div>

          {/* Subscription Details */}
          <div className="space-y-3 mb-4">
            {profile.subscription.expires_at && (
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Expires</span>
                <span className="text-white font-medium">
                  {formatDate(profile.subscription.expires_at)}
                  {getDaysRemaining(profile.subscription.expires_at) !== null && (
                    <span className="text-gray-400 text-xs ml-2">
                      ({getDaysRemaining(profile.subscription.expires_at)} days)
                    </span>
                  )}
                </span>
              </div>
            )}

            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Auto-renew</span>
              <span className="text-white font-medium">
                {profile.subscription.auto_renew ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>

          {/* Usage Stats */}
          <div className="glassmorphism rounded-xl p-4 mb-4">
            <div className="flex justify-between mb-2">
              <span className="text-gray-400 text-sm">Daily Requests</span>
              <span className="text-white font-medium">
                {profile.subscription.requests_used_today} / {profile.subscription.daily_limit}
              </span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all"
                style={{
                  width: `${Math.min(
                    (profile.subscription.requests_used_today /
                      profile.subscription.daily_limit) *
                      100,
                    100
                  )}%`,
                }}
              />
            </div>
            <div className="text-gray-500 text-xs mt-1">
              {profile.subscription.requests_remaining} requests remaining today
            </div>
          </div>

          {/* Upgrade Button */}
          {profile.subscription.tier !== 'vip' && (
            <button
              onClick={() => setShowPremiumModal(true)}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white py-3 rounded-xl font-medium transition-all"
            >
              Upgrade to Premium
            </button>
          )}
        </motion.div>

        {/* Referral Stats Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glassmorphism-card rounded-2xl p-6"
        >
          <h2 className="text-white font-bold text-lg mb-4">Referral Stats</h2>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="glassmorphism rounded-xl p-4">
              <div className="text-gray-400 text-xs mb-1">Total Referrals</div>
              <div className="text-white font-bold text-2xl">
                {profile.referral.total_referrals}
              </div>
            </div>
            <div className="glassmorphism rounded-xl p-4">
              <div className="text-gray-400 text-xs mb-1">Active</div>
              <div className="text-green-400 font-bold text-2xl">
                {profile.referral.active_referrals}
              </div>
            </div>
          </div>

          <div className="glassmorphism rounded-xl p-4">
            <div className="text-gray-400 text-xs mb-3">Tier Benefits</div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-300 text-sm">Tier</span>
                <span className="text-white font-medium capitalize">{profile.referral.tier}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-300 text-sm">Monthly Bonus</span>
                <span className="text-blue-400 font-medium">
                  +{profile.referral.monthly_bonus} requests
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-300 text-sm">Discount</span>
                <span className="text-green-400 font-medium">
                  {profile.referral.discount_percent}%
                </span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Balance Card (if user has balance) */}
        {profile.balance.balance_usd > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glassmorphism-card rounded-2xl p-6"
          >
            <h2 className="text-white font-bold text-lg mb-4">Referral Balance</h2>

            <div className="bg-gradient-to-r from-green-600 to-emerald-600 rounded-2xl p-6 mb-4">
              <div className="text-white/80 text-sm mb-1">Available Balance</div>
              <div className="text-white font-bold text-3xl">
                ${profile.balance.balance_usd.toFixed(2)}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="glassmorphism rounded-xl p-3">
                <div className="text-gray-400 text-xs mb-1">Total Earned</div>
                <div className="text-green-400 font-bold">
                  ${profile.balance.earned_total_usd.toFixed(2)}
                </div>
              </div>
              <div className="glassmorphism rounded-xl p-3">
                <div className="text-gray-400 text-xs mb-1">Withdrawn</div>
                <div className="text-blue-400 font-bold">
                  ${profile.balance.withdrawn_total_usd.toFixed(2)}
                </div>
              </div>
            </div>

            <button className="w-full bg-green-600 hover:bg-green-700 text-white py-3 rounded-xl font-medium transition-colors">
              Withdraw Balance
            </button>
          </motion.div>
        )}

        {/* Settings Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glassmorphism-card rounded-2xl p-6"
        >
          <h2 className="text-white font-bold text-lg mb-4">Settings</h2>

          <div className="space-y-4">
            {/* Language Selection */}
            <div>
              <label className="text-gray-400 text-sm mb-2 block">Language</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleLanguageChange('ru')}
                  className={`py-3 rounded-xl font-medium transition-colors ${
                    profile.user.language === 'ru'
                      ? 'bg-blue-600 text-white'
                      : 'glassmorphism text-gray-400 hover:text-white'
                  }`}
                >
                  🇷🇺 Russian
                </button>
                <button
                  onClick={() => handleLanguageChange('en')}
                  className={`py-3 rounded-xl font-medium transition-colors ${
                    profile.user.language === 'en'
                      ? 'bg-blue-600 text-white'
                      : 'glassmorphism text-gray-400 hover:text-white'
                  }`}
                >
                  🇬🇧 English
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      </main>

      {/* Premium Purchase Modal with Telegram Stars Integration */}
      <PremiumPurchaseModal
        isOpen={showPremiumModal}
        onClose={() => setShowPremiumModal(false)}
        onSuccess={() => {
          // Reload profile after successful payment
          loadProfile();
          toast.success('Subscription activated successfully!');
        }}
        referralDiscount={profile?.referral.discount_percent || 0}
      />
    </div>
  );
}
