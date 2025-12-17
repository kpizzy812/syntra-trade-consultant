'use client';

import { useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Image from 'next/image';
import { getPreferredLocale } from '@/shared/lib/locale';
import { getReferralInfo, getReferralCode } from '@/shared/lib/referral';

// Animations
const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
    },
  },
};

const stagger = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};

export default function ChooseAuthMethod() {
  const router = useRouter();
  // Lazy initialization - определяем язык один раз при создании компонента
  const [language, setLanguage] = useState<'en' | 'ru'>(() => getPreferredLocale());
  const [referralInfo, setReferralInfo] = useState<{ code: string; message: string } | null>(null);

  // Check for referral code on mount
  useEffect(() => {
    const refInfo = getReferralInfo();
    if (refInfo) {
      setReferralInfo(refInfo);
    }
  }, []);

  // Simple translations
  const t = {
    en: {
      title: 'Sign In to Syntra AI',
      subtitle: 'Choose your preferred method',
      telegramTitle: 'Continue with Telegram',
      telegramDesc: 'Instant access via Telegram Mini App',
      emailTitle: 'Continue with Email',
      emailDesc: 'Secure passwordless login',
      alreadyHave: 'Already have an account?',
      signInEmail: 'Sign in',
      referralJoining: 'Joining via referral code',
      referralBonus: "You'll get bonus requests!",
    },
    ru: {
      title: 'Войти в Syntra AI',
      subtitle: 'Выберите удобный способ',
      telegramTitle: 'Продолжить через Telegram',
      telegramDesc: 'Мгновенный доступ через Telegram Mini App',
      emailTitle: 'Продолжить через Email',
      emailDesc: 'Безопасный вход без пароля',
      alreadyHave: 'Уже есть аккаунт?',
      signInEmail: 'Войти',
      referralJoining: 'Присоединение по реферальной ссылке',
      referralBonus: 'Вы получите бонусные запросы!',
    },
  }[language];

  const handleTelegramAuth = () => {
    // Get referral code from localStorage
    const refCode = getReferralCode();

    // Build Telegram URL with startapp parameter
    let telegramUrl = 'https://t.me/SyntraAI_bot?startapp';

    if (refCode) {
      // Add referral code to startapp parameter
      telegramUrl = `https://t.me/SyntraAI_bot?startapp=ref_${refCode}`;
      console.log('🎁 Opening Telegram with referral code:', refCode);
    } else {
      console.log('📱 Opening Telegram without referral code');
    }

    window.open(telegramUrl, '_blank');
  };

  const handleEmailAuth = () => {
    router.push('/auth/login');
  };

  return (
    <div className="relative min-h-screen bg-[#05030A] text-white overflow-hidden flex items-center justify-center px-4 py-12">
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-20 -left-40 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-20 -right-40 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px]" />
      </div>

      <motion.div
        className="relative z-10 w-full max-w-md"
        variants={stagger}
        initial="hidden"
        animate="show"
      >
        {/* Header */}
        <motion.div className="text-center mb-8" variants={fadeInUp}>
          <div className="inline-flex items-center justify-center gap-3 mb-6">
            <Image
              src="/syntra/logo.png"
              width={48}
              height={48}
              alt="Syntra Logo"
              className="rounded-xl"
            />
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-blue-600 bg-clip-text text-transparent">
              Syntra AI
            </h1>
          </div>
          <h2 className="text-2xl md:text-3xl font-bold text-white mb-2">
            {t.title}
          </h2>
          <p className="text-base text-white/60">
            {t.subtitle}
          </p>
        </motion.div>

        {/* Referral Banner */}
        {referralInfo && (
          <motion.div
            className="mb-6 p-4 rounded-2xl backdrop-blur-xl bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20"
            variants={fadeInUp}
          >
            <div className="flex items-center gap-3">
              <div className="text-2xl">🎁</div>
              <div className="flex-1">
                <p className="text-white/90 font-medium text-sm mb-1">
                  {t.referralJoining}
                </p>
                <p className="text-white/60 text-xs mb-2">
                  {t.referralBonus}
                </p>
                <div className="inline-block bg-blue-500/15 px-3 py-1.5 rounded-lg backdrop-blur-sm">
                  <span className="text-blue-300 font-mono text-sm font-bold">
                    {referralInfo.code}
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Auth Methods - Vertical List */}
        <div className="space-y-4 mb-6">
          {/* Telegram Button */}
          <motion.button
            onClick={handleTelegramAuth}
            className="group relative w-full"
            variants={fadeInUp}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            transition={{ duration: 0.2 }}
          >
            <div className="relative p-5 rounded-2xl backdrop-blur-xl bg-gradient-to-br from-blue-500/12 to-blue-600/8 border border-blue-400/25 hover:border-blue-400/40 transition-all duration-300 overflow-hidden">
              {/* Glow effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

              {/* Content */}
              <div className="relative z-10 flex items-center gap-4">
                {/* Icon */}
                <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    className="text-white"
                  >
                    <path
                      d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"
                      fill="currentColor"
                    />
                  </svg>
                </div>

                {/* Text */}
                <div className="flex-1 text-left">
                  <h3 className="text-white font-semibold text-base mb-0.5">
                    {t.telegramTitle}
                  </h3>
                  <p className="text-white/60 text-sm">
                    {t.telegramDesc}
                  </p>
                </div>

                {/* Arrow */}
                <svg className="w-5 h-5 text-white/40 group-hover:text-white/60 group-hover:translate-x-1 transition-all" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          </motion.button>

          {/* Email Button */}
          <motion.button
            onClick={handleEmailAuth}
            className="group relative w-full"
            variants={fadeInUp}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            transition={{ duration: 0.2 }}
          >
            <div className="relative p-5 rounded-2xl backdrop-blur-xl bg-gradient-to-br from-blue-500/8 to-blue-600/5 border border-blue-400/20 hover:border-blue-400/35 transition-all duration-300 overflow-hidden">
              {/* Glow effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500/15 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

              {/* Content */}
              <div className="relative z-10 flex items-center gap-4">
                {/* Icon */}
                <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-blue-400/80 to-blue-600/80 flex items-center justify-center shadow-lg shadow-blue-500/15">
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    className="text-white"
                  >
                    <path
                      d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"
                      fill="currentColor"
                    />
                  </svg>
                </div>

                {/* Text */}
                <div className="flex-1 text-left">
                  <h3 className="text-white font-semibold text-base mb-0.5">
                    {t.emailTitle}
                  </h3>
                  <p className="text-white/60 text-sm">
                    {t.emailDesc}
                  </p>
                </div>

                {/* Arrow */}
                <svg className="w-5 h-5 text-white/40 group-hover:text-white/60 group-hover:translate-x-1 transition-all" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          </motion.button>
        </div>

        {/* Already have account */}
        <motion.div className="text-center" variants={fadeInUp}>
          <p className="text-white/60 text-sm">
            {t.alreadyHave}{' '}
            <button
              onClick={() => router.push('/auth/login')}
              className="text-blue-400 hover:text-blue-300 font-semibold transition-colors underline underline-offset-2"
            >
              {t.signInEmail} →
            </button>
          </p>
        </motion.div>

        {/* Footer Links */}
        <motion.div className="mt-8 text-center text-xs text-white/40" variants={fadeInUp}>
          <a
            href="https://telegra.ph/Pravila-ispolzovaniya-Syntra-AI-11-23"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white/60 transition-colors"
          >
            Terms
          </a>
          {' • '}
          <a
            href="https://telegra.ph/Politika-konfidencialnosti-Syntra-AI-11-23"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white/60 transition-colors"
          >
            Privacy
          </a>
        </motion.div>
      </motion.div>
    </div>
  );
}
