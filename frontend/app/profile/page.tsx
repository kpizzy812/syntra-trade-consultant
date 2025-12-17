/**
 * Profile Page - COMPACT VERSION
 * Компактный профиль пользователя
 */

'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';
import Image from 'next/image';
import { api } from '@/shared/api/client';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import DesktopLayout from '@/components/layout/DesktopLayout';
import PremiumPurchaseModal from '@/components/modals/PremiumPurchaseModal';
import Leaderboard from '@/components/points/Leaderboard';
import toast from 'react-hot-toast';
import { usePostHog } from '@/components/providers/PostHogProvider';
import { usePlatform } from '@/lib/platform';
import { logoutWebUser, isWebAuth } from '@/shared/utils/auth';
import { useTelegram } from '@/components/providers/TelegramProvider';
import { usePointsStore } from '@/shared/store/pointsStore';
import { useCurrentLocale } from '@/shared/hooks/useCurrentLocale';
import { CONTACTS } from '@/config/contacts';
import { vibrate } from '@/shared/telegram/vibration';

interface ProfileData {
  user: {
    id: number;
    telegram_id: number | null;
    email: string | null;
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
    // Post-trial discount (20% off first subscription after trial ends)
    has_post_trial_discount?: boolean;
    post_trial_discount_percent?: number;
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
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [showLeaderboard, setShowLeaderboard] = useState(false);
  const posthog = usePostHog();
  const { platformType } = usePlatform();
  const { webApp, isMiniApp } = useTelegram();
  const locale = useCurrentLocale();
  const { balance: pointsBalance } = usePointsStore();
  const t = useTranslations('profile');
  const tCommon = useTranslations('common');

  // Получаем аватарку из Telegram WebApp (если доступна)
  const telegramPhotoUrl = isMiniApp ? webApp?.initDataUnsafe?.user?.photo_url : null;

  // Определяем, показывать ли кнопку logout (ТОЛЬКО для web users)
  const isWebUser = platformType === 'web' && isWebAuth();

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const data = await api.profile.getProfile();
      setProfile(data);

      // 📊 Track profile page view
      if (posthog.__loaded) {
        posthog.capture('profile_viewed', {
          tier: data.subscription.tier,
          is_trial: data.subscription.is_trial,
          requests_remaining: data.subscription.requests_remaining,
          platform: 'miniapp',
        });
      }
    } catch (error) {
      console.error('Failed to load profile:', error);
      toast.error(t('failed_load'));
    } finally {
      setLoading(false);
    }
  };

  const handleUpgradeClick = () => {
    // 📊 Track pricing page viewed
    if (posthog.__loaded && profile) {
      posthog.capture('pricing_page_viewed', {
        current_tier: profile.subscription.tier,
        is_trial: profile.subscription.is_trial,
        source: 'profile_upgrade_button',
        platform: 'miniapp',
      });
    }
    setShowPremiumModal(true);
  };

  const handleLanguageChange = async (newLanguage: string) => {
    try {
      await api.profile.updateSettings({ language: newLanguage });
      toast.success(`${t('language_changed')} ${newLanguage.toUpperCase()}`);

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
      toast.error(t('failed_update_language'));
    }
  };

  const handleLogout = () => {
    // Показываем confirmation modal
    setShowLogoutConfirm(true);
  };

  const confirmLogout = () => {
    // Track logout event
    if (posthog.__loaded && profile) {
      posthog.capture('user_logged_out', {
        tier: profile.subscription.tier,
        platform: 'web',
      });
    }

    // Выполняем logout
    logoutWebUser();
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
        <div className="text-white">{t('failed_load')}</div>
      </div>
    );
  }

  return (
    <DesktopLayout>
      <div className="bg-black flex flex-col h-full">
        <Header title={t('title')} showBack={false} />

        <main className="flex-1 overflow-y-auto px-4 pt-4 pb-24 lg:max-w-[1200px] lg:mx-auto lg:w-full">
          <div className="max-w-5xl mx-auto space-y-4">
        {/* User Info Card - GLASS BLUE */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gradient-to-br from-blue-500/10 via-blue-600/5 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-2xl p-4 shadow-lg shadow-blue-500/10"
        >
          <div className="flex items-center gap-3">
            {/* Аватарка: Telegram photo > первая буква имени > эмодзи */}
            {telegramPhotoUrl ? (
              <img
                src={telegramPhotoUrl}
                alt="Avatar"
                className="w-12 h-12 rounded-full object-cover border-2 border-blue-500/30"
              />
            ) : (
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-lg font-bold">
                {profile.user.first_name?.[0]?.toUpperCase() ||
                 profile.user.email?.[0]?.toUpperCase() || '👤'}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-white font-bold text-base truncate">
                  {/* Имя: first_name + last_name > email > username */}
                  {profile.user.first_name
                    ? `${profile.user.first_name}${profile.user.last_name ? ` ${profile.user.last_name}` : ''}`
                    : profile.user.email || profile.user.username || 'User'}
                </h2>
                {profile.user.is_admin && (
                  <span className="bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded text-xs font-medium">
                    Admin
                  </span>
                )}
              </div>
              {/* Подзаголовок: @username или email */}
              {profile.user.username ? (
                <div className="text-gray-400 text-xs">@{profile.user.username}</div>
              ) : profile.user.email && profile.user.first_name ? (
                <div className="text-gray-400 text-xs">{profile.user.email}</div>
              ) : null}
            </div>
          </div>
        </motion.div>

        {/* Plan & Upgrade Card - COMPACT GLASS BLUE */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="bg-gradient-to-br from-blue-500/10 via-purple-600/5 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-2xl p-4 shadow-lg"
        >
          {/* Tier Badge + Quick Stats */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <span className="text-3xl">{getTierIcon(profile.subscription.tier)}</span>
              <div>
                <div className="text-lg font-bold text-white capitalize">{profile.subscription.tier}</div>
                <p className="text-xs text-gray-400">
                  {profile.subscription.daily_limit} {t('daily_requests')}
                </p>
              </div>
            </div>
            {profile.subscription.expires_at && (
              <div className="text-right">
                <div className="text-xs text-gray-400">{t('expires')}</div>
                <div className="text-base font-bold text-blue-400">{getDaysRemaining(profile.subscription.expires_at)}d</div>
              </div>
            )}
          </div>

          {/* Compact Stats Row */}
          <div className="flex gap-2 mb-3">
            <div className="flex-1 bg-blue-900/20 rounded-lg p-2 border border-blue-500/10">
              <div className="text-[10px] text-gray-400 mb-0.5">{t('used')}</div>
              <div className="text-sm font-bold text-white">{profile.subscription.requests_used_today}</div>
            </div>
            <div className="flex-1 bg-blue-900/20 rounded-lg p-2 border border-blue-500/10">
              <div className="text-[10px] text-gray-400 mb-0.5">{t('remaining')}</div>
              <div className="text-sm font-bold text-green-400">{profile.subscription.requests_remaining}</div>
            </div>
            <div className="flex-1 bg-blue-900/20 rounded-lg p-2 border border-blue-500/10">
              <div className="text-[10px] text-gray-400 mb-0.5">{t('limit')}</div>
              <div className="text-sm font-bold text-purple-400">{profile.subscription.daily_limit}</div>
            </div>
          </div>

          {/* Usage Progress */}
          <div className="mb-3">
            <div className="flex justify-between mb-1.5">
              <span className="text-xs text-gray-400">{t('daily_usage')}</span>
              <span className="text-xs text-gray-400">
                {Math.round((profile.subscription.requests_used_today / profile.subscription.daily_limit) * 100)}%
              </span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-1.5">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-1.5 rounded-full transition-all"
                style={{
                  width: `${Math.min(
                    (profile.subscription.requests_used_today / profile.subscription.daily_limit) * 100,
                    100
                  )}%`,
                }}
              />
            </div>
          </div>

          {/* Upgrade Button */}
          {profile.subscription.tier !== 'vip' && (
            <button
              onClick={handleUpgradeClick}
              className="w-full px-5 py-2.5 rounded-lg bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500 text-white text-sm font-medium transition-all active:scale-95"
            >
              ⚡ {t('upgrade_plan')}
            </button>
          )}
        </motion.div>

        {/* $SYNTRA Points Card */}
        {pointsBalance && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.07 }}
            className="bg-gradient-to-br from-purple-500/10 via-purple-600/5 to-blue-700/10 backdrop-blur-xl border border-purple-500/20 rounded-2xl p-4 shadow-lg shadow-purple-500/10"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Image
                  src="/syntra/$SYNTRA.png"
                  alt="$SYNTRA"
                  width={24}
                  height={24}
                  className="object-contain"
                />
                <h3 className="text-white font-bold text-sm">$SYNTRA Points</h3>
              </div>
              <span className="text-lg">{pointsBalance.level_icon}</span>
            </div>

            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-white font-bold text-3xl">
                {pointsBalance.balance.toLocaleString()}
              </span>
              <span className="text-gray-400 text-sm">pts</span>
            </div>

            <div className="flex items-center justify-between text-xs mb-3">
              <span className="text-purple-400/80">
                Level {pointsBalance.level}: {locale === 'ru' ? pointsBalance.level_name_ru : pointsBalance.level_name_en}
              </span>
              <span className="text-blue-400 font-medium">
                {pointsBalance.earning_multiplier}x {locale === 'ru' ? 'множитель' : 'multiplier'}
              </span>
            </div>

            {/* Streak + Leaderboard Row */}
            <div className="flex items-center gap-2">
              {pointsBalance.current_streak > 0 && (
                <div className="flex-1 bg-orange-500/10 border border-orange-500/20 rounded-lg px-2 py-1.5 flex items-center gap-2">
                  <span className="text-base">🔥</span>
                  <span className="text-xs text-orange-300 font-medium">
                    {pointsBalance.current_streak} {locale === 'ru' ? 'дн. серия' : 'day streak'}
                  </span>
                </div>
              )}

              {/* Leaderboard Button */}
              <button
                onClick={() => { vibrate('light'); setShowLeaderboard(true); }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-500/20 to-blue-500/20 hover:from-purple-500/30 hover:to-blue-500/30 border border-purple-500/30 rounded-lg transition-all active:scale-95"
              >
                <span className="text-base">🏆</span>
                <span className="text-xs text-purple-300 font-medium">
                  {locale === 'ru' ? 'Топ' : 'Top'}
                </span>
              </button>
            </div>
          </motion.div>
        )}

        {/* Referral Stats - GLASS BLUE */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-gradient-to-br from-blue-500/10 via-blue-600/5 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-2xl p-4 shadow-lg shadow-blue-500/10"
        >
          <h3 className="text-white font-bold text-sm mb-3">{t('referrals_title')}</h3>

          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="bg-blue-900/20 backdrop-blur-sm rounded-xl p-2 text-center border border-blue-500/10">
              <div className="text-white font-bold text-lg">
                {profile.referral.total_referrals}
              </div>
              <div className="text-blue-400/80 text-xs">{t('total')}</div>
            </div>
            <div className="bg-blue-900/20 backdrop-blur-sm rounded-xl p-2 text-center border border-blue-500/10">
              <div className="text-green-400 font-bold text-lg">
                {profile.referral.active_referrals}
              </div>
              <div className="text-blue-400/80 text-xs">{t('active_short')}</div>
            </div>
            <div className="bg-blue-900/20 backdrop-blur-sm rounded-xl p-2 text-center border border-blue-500/10">
              <div className="text-blue-400 font-bold text-lg">
                +{profile.referral.monthly_bonus}
              </div>
              <div className="text-blue-400/80 text-xs">{t('bonus')}</div>
            </div>
          </div>

          <div className="bg-blue-900/20 backdrop-blur-sm rounded-xl p-2 border border-blue-500/10">
            <div className="flex justify-between text-xs">
              <span className="text-blue-400/80">{t('discount')}</span>
              <span className="text-green-400 font-medium">
                {profile.referral.discount_percent}%
              </span>
            </div>
          </div>
        </motion.div>

        {/* Balance - IF EXISTS */}
        {profile.balance.balance_usd > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="bg-gradient-to-r from-green-600/20 to-emerald-600/20 border border-green-500/30 rounded-xl p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="text-gray-400 text-xs">{t('balance')}</div>
                <div className="text-white font-bold text-2xl">
                  ${profile.balance.balance_usd.toFixed(2)}
                </div>
              </div>
              <button className="bg-green-600 hover:bg-green-700 text-white text-xs font-medium px-4 py-2 rounded-lg transition-colors">
                {t('withdraw')}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="text-xs">
                <span className="text-gray-400">{t('earned')}: </span>
                <span className="text-green-400 font-medium">
                  ${profile.balance.earned_total_usd.toFixed(2)}
                </span>
              </div>
              <div className="text-xs text-right">
                <span className="text-gray-400">{t('withdrawn')}: </span>
                <span className="text-blue-400 font-medium">
                  ${profile.balance.withdrawn_total_usd.toFixed(2)}
                </span>
              </div>
            </div>
          </motion.div>
        )}

        {/* Settings - GLASS BLUE */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-gradient-to-br from-blue-500/10 via-blue-600/5 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-2xl p-4 shadow-lg shadow-blue-500/10"
        >
          <h3 className="text-white font-bold text-sm mb-3">{t('language')}</h3>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => handleLanguageChange('ru')}
              className={`py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
                profile.user.language === 'ru'
                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30'
                  : 'bg-blue-900/20 text-blue-400/80 hover:text-white hover:bg-blue-900/30 border border-blue-500/10'
              }`}
            >
              🇷🇺 {t('russian')}
            </button>
            <button
              onClick={() => handleLanguageChange('en')}
              className={`py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
                profile.user.language === 'en'
                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30'
                  : 'bg-blue-900/20 text-blue-400/80 hover:text-white hover:bg-blue-900/30 border border-blue-500/10'
              }`}
            >
              🇬🇧 {t('english')}
            </button>
          </div>
        </motion.div>

        {/* Support - GLASS BLUE */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.22 }}
          className="bg-gradient-to-br from-blue-500/10 via-blue-600/5 to-blue-700/10 backdrop-blur-xl border border-blue-500/20 rounded-2xl p-4 shadow-lg shadow-blue-500/10"
        >
          <h3 className="text-white font-bold text-sm mb-3">{t('support')}</h3>
          <div className="space-y-2">
            <a
              href={`mailto:${CONTACTS.email}`}
              className="flex items-center gap-3 p-3 bg-blue-900/20 hover:bg-blue-900/30 rounded-xl border border-blue-500/10 transition-all duration-200"
            >
              <span className="text-lg">📧</span>
              <div className="flex-1">
                <div className="text-white text-sm font-medium">{CONTACTS.email}</div>
                <div className="text-blue-400/60 text-xs">{t('email_support')}</div>
              </div>
            </a>
            <a
              href={CONTACTS.telegramUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 p-3 bg-blue-900/20 hover:bg-blue-900/30 rounded-xl border border-blue-500/10 transition-all duration-200"
            >
              <span className="text-lg">💬</span>
              <div className="flex-1">
                <div className="text-white text-sm font-medium">{CONTACTS.telegram}</div>
                <div className="text-blue-400/60 text-xs">{t('telegram_support')}</div>
              </div>
            </a>
          </div>
        </motion.div>

        {/* Sign Out Button - GLASS BLUE (Red variant) */}
        {isWebUser && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="bg-gradient-to-br from-red-500/10 via-red-600/5 to-red-700/10 backdrop-blur-xl border border-red-500/20 rounded-2xl p-4 shadow-lg shadow-red-500/10"
          >
            <button
              onClick={handleLogout}
              className="w-full py-3 bg-red-600/10 hover:bg-red-600/20 text-red-400 rounded-xl text-sm font-medium transition-all duration-200 border border-red-500/30 hover:border-red-500/40 active:scale-95"
            >
              🚪 {t('sign_out')}
            </button>
            <p className="text-red-400/60 text-xs text-center mt-2">
              {t('redirect_note')}
            </p>
          </motion.div>
        )}
        </div>
      </main>

      <TabBar />
      </div>

      {/* Logout Confirmation Modal */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center px-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-[#111] border border-white/10 rounded-2xl p-6 max-w-sm w-full"
          >
            <div className="text-center mb-6">
              <div className="w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🚪</span>
              </div>
              <h3 className="text-white font-bold text-lg mb-2">{t('sign_out_confirm')}</h3>
              <p className="text-gray-400 text-sm">
                {t('sign_out_description')}
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {tCommon('cancel')}
              </button>
              <button
                onClick={confirmLogout}
                className="flex-1 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {t('sign_out')}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      <PremiumPurchaseModal
        isOpen={showPremiumModal}
        onClose={() => setShowPremiumModal(false)}
        onSuccess={() => {
          loadProfile();
          toast.success(tCommon('success'));
        }}
        // Combine referral discount and post-trial discount (max 50%)
        referralDiscount={Math.min(
          50,
          (profile?.referral.discount_percent || 0) +
          (profile?.subscription.post_trial_discount_percent || 0)
        )}
      />

      {/* Leaderboard Modal */}
      <Leaderboard
        isOpen={showLeaderboard}
        onClose={() => setShowLeaderboard(false)}
      />
    </DesktopLayout>
  );
}
