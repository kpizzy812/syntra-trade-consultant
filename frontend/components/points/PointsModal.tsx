/**
 * Points Modal Component
 * Всплывающее окно с описанием $SYNTRA Points
 * Включает намек на будущий токен (но не прямой)
 */

'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslations } from 'next-intl';
import { usePointsStore } from '@/shared/store/pointsStore';
import { useCurrentLocale } from '@/shared/hooks/useCurrentLocale';
import Image from 'next/image';
import { vibrate } from '@/shared/telegram/vibration';

interface PointsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function PointsModal({ isOpen, onClose }: PointsModalProps) {
  const { balance, levels } = usePointsStore();
  const t = useTranslations('points');
  const locale = useCurrentLocale();
  const [mounted, setMounted] = useState(false);

  // Ensure component is mounted (for portal)
  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  // Close on ESC key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEsc);
      document.body.style.overflow = 'hidden'; // Prevent scroll
    }

    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen || !balance || !mounted) return null;

  // Calculate progress to next level
  const progressPercent = balance.next_level_points
    ? ((balance.progress_to_next_level || 0) * 100).toFixed(0)
    : 100;

  const modalContent = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative bg-gradient-to-br from-gray-900 to-black border border-white/10 rounded-2xl max-w-md w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-600/20 to-purple-600/20 border-b border-white/10 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Image
                src="/syntra/$SYNTRA.png"
                alt="$SYNTRA"
                width={40}
                height={40}
                className="object-contain"
              />
              <div>
                <h2 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                  $SYNTRA Points
                </h2>
                <p className="text-xs text-gray-400">
                  {t('your_rewards')}
                </p>
              </div>
            </div>

            <button
              onClick={() => { vibrate('light'); onClose(); }}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Current Balance */}
          <div className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-400">{t('current_balance')}</span>
              <span className="text-lg">
                {balance.level_icon}
              </span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {balance.balance.toLocaleString()}
              <span className="text-sm text-gray-400 ml-2">pts</span>
            </div>
            <div className="text-sm text-gray-400">
              {t('level')} {balance.level}: {locale === 'ru' ? balance.level_name_ru : balance.level_name_en}
            </div>

            {/* Progress Bar */}
            {balance.next_level_points && (
              <div className="mt-4">
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>{t('next_level')}</span>
                  <span>{progressPercent}%</span>
                </div>
                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {balance.next_level_points.toLocaleString()} {t('points_needed')}
                </div>
              </div>
            )}
          </div>

          {/* What are $SYNTRA Points */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="text-lg">💎</span>
              {t('what_are_points')}
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              {t('description')}
            </p>
          </div>

          {/* How to Earn */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="text-lg">⭐</span>
              {t('how_to_earn')}
            </h3>
            <div className="space-y-2 text-sm text-gray-300">
              <div className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>{t('earn_chat_requests')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>{t('earn_daily_login')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>{t('earn_tasks')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>{t('earn_subscriptions')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>{t('earn_referrals')}</span>
              </div>
            </div>
          </div>

          {/* Earning Rates */}
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
              <span className="text-lg">💰</span>
              {t('earning_rates')}
            </h3>
            <div className="space-y-1.5 text-xs text-gray-300">
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span>{t('rate_text_request')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span>{t('rate_suggested_prompt')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span>{t('rate_market_analysis')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span>{t('rate_daily_login')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span>{t('rate_referral_signup')}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span>{t('rate_referral_premium')}</span>
              </div>
            </div>
          </div>

          {/* Streak Info */}
          {balance.current_streak > 0 && (
            <div className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">🔥</span>
                <div>
                  <div className="text-sm font-semibold text-white">
                    {balance.current_streak} {t('day_streak')}
                  </div>
                  <div className="text-xs text-gray-400">
                    {t('longest')}: {balance.longest_streak} {t('days')}
                  </div>
                </div>
              </div>
              <p className="text-xs text-gray-300">
                {t('streak_bonus_info')}
              </p>
            </div>
          )}

          {/* Future Hint (subtle) */}
          <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <span className="text-2xl">🚀</span>
              <div className="flex-1">
                <div className="text-sm font-semibold text-white mb-1">
                  {t('future_value_title')}
                </div>
                <p className="text-xs text-gray-300 leading-relaxed">
                  {t('future_value_hint')}
                </p>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">{t('total_earned')}</div>
              <div className="text-lg font-semibold text-white">
                {balance.lifetime_earned.toLocaleString()}
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-1">{t('multiplier')}</div>
              <div className="text-lg font-semibold text-blue-400">
                {balance.earning_multiplier}x
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
