'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import Image from 'next/image';
import { getPreferredLocale } from '@/shared/lib/locale';
import { getReferralInfo } from '@/shared/lib/referral';

// Animations - те же самые что и на странице выбора
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

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [language, setLanguage] = useState<'en' | 'ru'>('en');
  const [referralInfo, setReferralInfo] = useState<{ code: string; message: string } | null>(null);

  useEffect(() => {
    const detectedLang = getPreferredLocale();
    setLanguage(detectedLang);
    console.log('🌍 Detected language for magic link:', detectedLang);

    const refInfo = getReferralInfo();
    setReferralInfo(refInfo);
    if (refInfo) {
      console.log('🎁 Referral code detected:', refInfo.code);
    }
  }, []);

  const t = {
    en: {
      title: 'Sign In with Email',
      subtitle: 'Enter your email to receive a magic link',
      emailLabel: 'Email address',
      emailPlaceholder: 'your@email.com',
      sendButton: 'Send magic link',
      sending: 'Sending...',
      successTitle: 'Check your email',
      successMessage: 'We sent a magic link to',
      successInstructions: 'Open the email and click the link to sign in',
      successExpiry: 'The link is valid for 15 minutes and can only be used once',
      spamWarning: 'Email didn\'t arrive? Check your Spam or Promotions folder',
      tryAnother: 'Try another email',
      noPassword: 'No password? No problem!',
      securityNote: 'We\'ll send you a secure login link via email',
      backToChoose: '← Back',
      referralJoining: 'Joining via referral code',
      referralBonus: "You'll get bonus requests!",
    },
    ru: {
      title: 'Вход через Email',
      subtitle: 'Введите email и получите ссылку для входа',
      emailLabel: 'Email адрес',
      emailPlaceholder: 'your@email.com',
      sendButton: 'Отправить magic link',
      sending: 'Отправляем...',
      successTitle: 'Проверьте почту',
      successMessage: 'Мы отправили magic link на',
      successInstructions: 'Откройте письмо и кликните на ссылку для входа',
      successExpiry: 'Ссылка действительна 15 минут и может быть использована только один раз',
      spamWarning: 'Письмо не пришло? Проверьте папку "Спам" или "Промоакции"',
      tryAnother: 'Попробовать другой email',
      noPassword: 'Нет пароля? Не беда!',
      securityNote: 'Мы отправим вам безопасную ссылку для входа на email',
      backToChoose: '← Назад',
      referralJoining: 'Присоединение по реферальной ссылке',
      referralBonus: 'Вы получите бонусные запросы!',
    },
  }[language];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/auth/magic/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          language,
          referral_code: referralInfo?.code || null,
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setSent(true);
      } else {
        setError(data.detail || data.message || 'Failed to send magic link');
      }
    } catch (err) {
      setError('Network error. Please try again.');
      console.error('Magic link request error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Success state - используем тот же стиль
  if (sent) {
    return (
      <div className="relative min-h-screen bg-[#05030A] text-white overflow-hidden flex items-center justify-center px-4 py-12">
        {/* Background effects - такие же */}
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
          </motion.div>

          {/* Success Card */}
          <motion.div
            className="p-6 rounded-2xl backdrop-blur-xl bg-gradient-to-br from-blue-500/12 to-blue-600/8 border border-blue-400/25"
            variants={fadeInUp}
          >
            {/* Success Icon */}
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-green-400/20 to-green-600/20 border border-green-400/30 flex items-center justify-center">
                <svg className="w-8 h-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
            </div>

            <h2 className="text-2xl font-bold text-white text-center mb-3">
              {t.successTitle}
            </h2>

            <p className="text-white/60 text-center mb-2">
              {t.successMessage}
            </p>
            <p className="text-blue-400 font-semibold text-center mb-6">
              {email}
            </p>

            {/* Instructions */}
            <div className="bg-blue-500/5 border border-blue-400/10 p-4 rounded-xl mb-4">
              <div className="flex items-start gap-3">
                <div className="text-2xl">📧</div>
                <div className="flex-1">
                  <p className="text-white/80 text-sm mb-2">
                    {t.successInstructions}
                  </p>
                  <p className="text-white/50 text-xs">
                    {t.successExpiry}
                  </p>
                </div>
              </div>
            </div>

            {/* Spam warning */}
            <p className="text-white/40 text-xs text-center mb-6">
              {t.spamWarning}
            </p>

            {/* Try another button */}
            <button
              onClick={() => {
                setSent(false);
                setEmail('');
              }}
              className="w-full py-3 px-4 rounded-xl border border-blue-400/30 text-white/80 hover:bg-blue-500/10 hover:border-blue-400/40 transition-all duration-300"
            >
              {t.tryAnother}
            </button>
          </motion.div>

          {/* Back button */}
          <motion.div className="text-center mt-6" variants={fadeInUp}>
            <button
              onClick={() => router.push('/auth/choose')}
              className="text-white/60 hover:text-white/80 text-sm transition-colors"
            >
              {t.backToChoose}
            </button>
          </motion.div>
        </motion.div>
      </div>
    );
  }

  // Login form - используем тот же стиль
  return (
    <div className="relative min-h-screen bg-[#05030A] text-white overflow-hidden flex items-center justify-center px-4 py-12">
      {/* Background effects - такие же */}
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

        {/* Form Card */}
        <motion.div variants={fadeInUp}>
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-white/80 mb-2">
                {t.emailLabel}
              </label>
              <div className="relative">
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl backdrop-blur-xl bg-gradient-to-br from-blue-500/8 to-blue-600/5 border border-blue-400/20 text-white placeholder-white/40 focus:outline-none focus:border-blue-400/40 focus:ring-2 focus:ring-blue-400/20 transition-all"
                  placeholder={t.emailPlaceholder}
                />
                <div className="absolute right-4 top-1/2 -translate-y-1/2 text-white/30">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"
                      fill="currentColor"
                    />
                  </svg>
                </div>
              </div>
            </div>

            {/* Error message */}
            {error && (
              <motion.div
                className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                {error}
              </motion.div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-semibold shadow-lg shadow-blue-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {t.sending}
                </span>
              ) : (
                t.sendButton
              )}
            </button>

            {/* Info text */}
            <div className="text-center pt-2">
              <p className="text-white/60 text-sm mb-1">
                {t.noPassword}
              </p>
              <p className="text-white/40 text-xs">
                {t.securityNote}
              </p>
            </div>
          </form>
        </motion.div>

        {/* Back button */}
        <motion.div className="text-center mt-6" variants={fadeInUp}>
          <button
            onClick={() => router.push('/auth/choose')}
            className="text-white/60 hover:text-white/80 text-sm transition-colors inline-flex items-center gap-1"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            {t.backToChoose}
          </button>
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
