/**
 * Leaderboard Component - $SYNTRA Points Ranking
 * Геймифицированный лидерборд с анимациями и визуальными эффектами
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Image from 'next/image';
import { api } from '@/shared/api/client';
import { useCurrentLocale } from '@/shared/hooks/useCurrentLocale';
import { vibrate, vibrateSelection } from '@/shared/telegram/vibration';

interface LeaderboardEntry {
  rank: number;
  user_id: number;
  username: string | null;
  first_name: string | null;
  photo_url: string | null;
  balance: number;
  level: number;
  level_name: string;
  level_icon: string;
  is_current_user: boolean;
}

interface LeaderboardProps {
  isOpen: boolean;
  onClose: () => void;
}

// Цвета для топ-3 мест
const RANK_COLORS = {
  1: {
    bg: 'from-yellow-500/20 via-amber-500/15 to-orange-500/20',
    border: 'border-yellow-500/40',
    glow: 'shadow-yellow-500/30',
    text: 'text-yellow-400',
    medal: '🥇',
    crown: true,
    avatarRing: 'ring-2 ring-yellow-500/60',
  },
  2: {
    bg: 'from-gray-300/20 via-slate-400/15 to-gray-500/20',
    border: 'border-gray-400/40',
    glow: 'shadow-gray-400/20',
    text: 'text-gray-300',
    medal: '🥈',
    crown: false,
    avatarRing: 'ring-2 ring-gray-400/60',
  },
  3: {
    bg: 'from-amber-700/20 via-orange-700/15 to-amber-800/20',
    border: 'border-amber-600/40',
    glow: 'shadow-amber-600/20',
    text: 'text-amber-500',
    medal: '🥉',
    crown: false,
    avatarRing: 'ring-2 ring-amber-600/60',
  },
};

// Анимация для появления элементов
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, x: -20, scale: 0.95 },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 24,
    },
  },
};

// Анимация для числа баланса
const CountUp = ({ value, duration = 1500 }: { value: number; duration?: number }) => {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    let startTime: number | null = null;
    const startValue = 0;

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);

      // Easing function - ease out cubic
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const currentValue = Math.floor(startValue + (value - startValue) * easeOut);

      setDisplayValue(currentValue);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [value, duration]);

  return <>{displayValue.toLocaleString()}</>;
};

// Пульсирующая анимация для текущего пользователя
const PulseRing = () => (
  <motion.div
    className="absolute inset-0 rounded-2xl border-2 border-blue-500/50"
    initial={{ scale: 1, opacity: 0.5 }}
    animate={{
      scale: [1, 1.02, 1],
      opacity: [0.5, 0.8, 0.5],
    }}
    transition={{
      duration: 2,
      repeat: Infinity,
      ease: 'easeInOut',
    }}
  />
);

// Компонент корона для первого места
const Crown = () => (
  <motion.div
    className="absolute -top-4 left-1/2 -translate-x-1/2"
    initial={{ y: -10, opacity: 0, rotate: -10 }}
    animate={{ y: 0, opacity: 1, rotate: 0 }}
    transition={{ delay: 0.5, type: 'spring', stiffness: 200 }}
  >
    <span className="text-2xl drop-shadow-lg">👑</span>
  </motion.div>
);

// Компонент аватарки с fallback на инициалы
const Avatar = ({
  photoUrl,
  displayName,
  isTop3,
  rankStyle,
  isCurrentUser,
}: {
  photoUrl: string | null;
  displayName: string;
  isTop3: boolean;
  rankStyle: typeof RANK_COLORS[1] | undefined;
  isCurrentUser: boolean;
}) => {
  const [imageError, setImageError] = useState(false);
  const initial = displayName[0]?.toUpperCase() || '?';

  // Классы для аватарки
  const baseClasses = 'w-11 h-11 rounded-full overflow-hidden flex items-center justify-center text-lg font-bold';
  const ringClasses = isTop3 && rankStyle ? rankStyle.avatarRing : isCurrentUser ? 'ring-2 ring-blue-500/60' : '';

  // Если есть фото и нет ошибки загрузки - показываем фото из БД
  if (photoUrl && !imageError) {
    return (
      <div className={`${baseClasses} ${ringClasses}`}>
        <Image
          src={photoUrl}
          alt={displayName}
          width={44}
          height={44}
          className="w-full h-full object-cover"
          onError={() => setImageError(true)}
          unoptimized
        />
      </div>
    );
  }

  // Fallback на инициалы с градиентом
  return (
    <div
      className={`
        ${baseClasses} ${ringClasses}
        ${
          isTop3 && rankStyle
            ? `bg-gradient-to-br ${rankStyle.bg} ${rankStyle.text}`
            : isCurrentUser
            ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white'
            : 'bg-gradient-to-br from-gray-700 to-gray-800 text-gray-300'
        }
      `}
    >
      {initial}
    </div>
  );
};

// Компонент для отображения одного места в лидерборде
const LeaderboardItem = ({
  entry,
  index,
  locale,
}: {
  entry: LeaderboardEntry;
  index: number;
  locale: string;
}) => {
  const isTop3 = entry.rank <= 3;
  const rankStyle = RANK_COLORS[entry.rank as keyof typeof RANK_COLORS];

  // Определяем отображаемое имя (без username для приватности)
  const displayName = entry.first_name || `User #${entry.user_id}`;

  return (
    <motion.div
      variants={itemVariants}
      className={`relative ${entry.is_current_user ? 'z-10' : ''}`}
      whileHover={{ scale: 1.01, x: 4 }}
      whileTap={{ scale: 0.99 }}
      onTap={() => vibrate('light')}
    >
      {/* Пульсация для текущего пользователя */}
      {entry.is_current_user && <PulseRing />}

      <div
        className={`
          relative flex items-center gap-3 p-3 rounded-2xl
          transition-all duration-300
          ${
            isTop3
              ? `bg-gradient-to-r ${rankStyle.bg} border ${rankStyle.border} shadow-lg ${rankStyle.glow}`
              : entry.is_current_user
              ? 'bg-gradient-to-r from-blue-500/15 via-purple-500/10 to-blue-600/15 border border-blue-500/30 shadow-lg shadow-blue-500/10'
              : 'bg-white/5 hover:bg-white/8 border border-white/5'
          }
        `}
      >
        {/* Корона для первого места */}
        {entry.rank === 1 && <Crown />}

        {/* Ранк */}
        <div className="flex-shrink-0 w-10 text-center">
          {isTop3 ? (
            <motion.span
              className="text-2xl"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ delay: index * 0.1 + 0.3, type: 'spring', stiffness: 200 }}
            >
              {rankStyle.medal}
            </motion.span>
          ) : (
            <span className={`text-lg font-bold ${entry.is_current_user ? 'text-blue-400' : 'text-gray-500'}`}>
              #{entry.rank}
            </span>
          )}
        </div>

        {/* Аватарка с уровнем */}
        <div className="relative flex-shrink-0">
          <Avatar
            photoUrl={entry.photo_url}
            displayName={displayName}
            isTop3={isTop3}
            rankStyle={rankStyle}
            isCurrentUser={entry.is_current_user}
          />
          {/* Level badge */}
          <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-black rounded-full flex items-center justify-center border border-white/20">
            <span className="text-xs">{entry.level_icon}</span>
          </div>
        </div>

        {/* Имя */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span
              className={`font-semibold truncate ${
                isTop3 ? rankStyle.text : entry.is_current_user ? 'text-blue-300' : 'text-white'
              }`}
            >
              {displayName}
            </span>
            {entry.is_current_user && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="text-xs bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded font-medium"
              >
                {locale === 'ru' ? 'Вы' : 'You'}
              </motion.span>
            )}
          </div>
        </div>

        {/* Баланс и уровень */}
        <div className="flex-shrink-0 text-right">
          <div className="flex items-center gap-1.5 justify-end">
            <Image
              src="/syntra/$SYNTRA.png"
              alt="$SYNTRA"
              width={16}
              height={16}
              className="object-contain opacity-80"
            />
            <span
              className={`font-bold tabular-nums ${
                isTop3 ? rankStyle.text : entry.is_current_user ? 'text-blue-300' : 'text-white'
              }`}
            >
              <CountUp value={entry.balance} duration={800 + index * 100} />
            </span>
          </div>
          <span className="text-xs text-gray-500">
            {locale === 'ru' ? `Ур. ${entry.level}` : `Lvl ${entry.level}`}
          </span>
        </div>
      </div>
    </motion.div>
  );
};

// Скелетон для загрузки
const LeaderboardSkeleton = () => (
  <div className="space-y-3">
    {[...Array(10)].map((_, i) => (
      <div
        key={i}
        className="flex items-center gap-3 p-3 rounded-2xl bg-white/5 animate-pulse"
      >
        <div className="w-10 h-6 bg-white/10 rounded" />
        <div className="w-11 h-11 bg-white/10 rounded-full" />
        <div className="flex-1">
          <div className="w-24 h-4 bg-white/10 rounded mb-1" />
          <div className="w-16 h-3 bg-white/5 rounded" />
        </div>
        <div className="text-right">
          <div className="w-16 h-4 bg-white/10 rounded mb-1" />
          <div className="w-10 h-3 bg-white/5 rounded" />
        </div>
      </div>
    ))}
  </div>
);

export default function Leaderboard({ isOpen, onClose }: LeaderboardProps) {
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userRank, setUserRank] = useState<LeaderboardEntry | null>(null);
  const locale = useCurrentLocale();

  const fetchLeaderboard = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.points.getLeaderboard(50);
      setLeaderboard(data);

      // Находим текущего пользователя
      const currentUser = data.find((entry: LeaderboardEntry) => entry.is_current_user);
      setUserRank(currentUser || null);
    } catch (err) {
      console.error('Failed to fetch leaderboard:', err);
      setError(locale === 'ru' ? 'Не удалось загрузить лидерборд' : 'Failed to load leaderboard');
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    if (isOpen) {
      fetchLeaderboard();
      // Блокируем скролл body когда модалка открыта
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [isOpen, fetchLeaderboard]);

  // Определяем позицию пользователя (в топ-10, близко к топу, далеко от топа)
  const getUserPosition = () => {
    if (!userRank) return null;
    if (userRank.rank <= 10) return 'top10';
    if (userRank.rank <= 25) return 'close';
    return 'far';
  };

  const userPosition = getUserPosition();

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => { vibrate('light'); onClose(); }}
          onTouchMove={(e) => e.preventDefault()}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="bg-[#0a0a0f] border border-white/10 rounded-3xl w-full max-w-md max-h-[85vh] overflow-hidden shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="relative p-5 border-b border-white/10 bg-gradient-to-br from-purple-500/10 via-blue-500/5 to-purple-600/10">
              {/* Декоративные элементы */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-purple-500/20 to-transparent rounded-full blur-3xl" />
              <div className="absolute bottom-0 left-0 w-24 h-24 bg-gradient-to-tr from-blue-500/20 to-transparent rounded-full blur-2xl" />

              <div className="relative flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <Image
                      src="/syntra/$SYNTRA.png"
                      alt="$SYNTRA"
                      width={36}
                      height={36}
                      className="object-contain"
                    />
                    <motion.div
                      className="absolute inset-0 rounded-full"
                      animate={{
                        boxShadow: [
                          '0 0 10px rgba(168, 85, 247, 0.3)',
                          '0 0 20px rgba(168, 85, 247, 0.5)',
                          '0 0 10px rgba(168, 85, 247, 0.3)',
                        ],
                      }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">
                      {locale === 'ru' ? 'Лидерборд' : 'Leaderboard'}
                    </h2>
                    <p className="text-xs text-gray-400">
                      {locale === 'ru' ? 'Топ держатели $SYNTRA Points' : 'Top $SYNTRA Points holders'}
                    </p>
                  </div>
                </div>

                {/* Close button */}
                <button
                  onClick={() => { vibrate('light'); onClose(); }}
                  className="p-2 rounded-full bg-white/5 hover:bg-white/10 transition-colors"
                >
                  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

            </div>

            {/* Leaderboard List */}
            <div
              className="p-4 overflow-y-auto flex-1 min-h-0 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent"
              style={{
                WebkitOverflowScrolling: 'touch',
                overscrollBehavior: 'contain',
                touchAction: 'pan-y'
              }}
              onTouchMove={(e) => e.stopPropagation()}
            >
              {loading ? (
                <LeaderboardSkeleton />
              ) : error ? (
                <div className="text-center py-8">
                  <p className="text-red-400 mb-3">{error}</p>
                  <button
                    onClick={() => { vibrate('medium'); fetchLeaderboard(); }}
                    className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition-colors"
                  >
                    {locale === 'ru' ? 'Попробовать снова' : 'Try again'}
                  </button>
                </div>
              ) : leaderboard.length === 0 ? (
                <div className="text-center py-8">
                  <span className="text-4xl mb-3 block">🏆</span>
                  <p className="text-gray-400">
                    {locale === 'ru' ? 'Пока нет участников' : 'No participants yet'}
                  </p>
                </div>
              ) : (
                <motion.div
                  variants={containerVariants}
                  initial="hidden"
                  animate="visible"
                  className="space-y-2"
                >
                  {leaderboard.map((entry, index) => (
                    <LeaderboardItem
                      key={entry.user_id}
                      entry={entry}
                      index={index}
                      locale={locale}
                    />
                  ))}
                </motion.div>
              )}
            </div>

            {/* Footer with user position */}
            <div className="border-t border-white/10 bg-gradient-to-r from-purple-500/5 to-blue-500/5 flex-shrink-0">
              {/* User's position card (если не в топ-10 видимых) */}
              {userRank && userPosition !== 'top10' && (
                <div className="p-3 border-b border-white/5">
                  <div className="p-3 rounded-xl bg-gradient-to-r from-blue-500/15 via-purple-500/10 to-blue-600/15 border border-blue-500/30">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-blue-400">#{userRank.rank}</span>
                        <span className="text-sm text-gray-300">
                          {locale === 'ru' ? 'Ваша позиция' : 'Your position'}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Image
                          src="/syntra/$SYNTRA.png"
                          alt="$SYNTRA"
                          width={14}
                          height={14}
                          className="object-contain"
                        />
                        <span className="font-bold text-blue-300">{userRank.balance.toLocaleString()}</span>
                      </div>
                    </div>
                    {userPosition === 'close' && (
                      <p className="text-xs text-purple-400 mt-1">
                        {locale === 'ru'
                          ? `⚡ До топ-10 осталось ${(leaderboard[9]?.balance || 0) - userRank.balance} pts!`
                          : `⚡ ${(leaderboard[9]?.balance || 0) - userRank.balance} pts to reach top 10!`}
                      </p>
                    )}
                  </div>
                </div>
              )}

              <div className="p-3 flex items-center justify-between text-xs text-gray-500">
                <span>
                  {locale === 'ru'
                    ? `Обновлено в реальном времени`
                    : 'Updated in real-time'}
                </span>
                <button
                  onClick={() => { vibrateSelection(); fetchLeaderboard(); }}
                  disabled={loading}
                  className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50"
                >
                  <svg
                    className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  {locale === 'ru' ? 'Обновить' : 'Refresh'}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
