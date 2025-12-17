"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from 'next-intl';
import GlowCursor from "@/components/GlowCursor";
import ScrollToTop from "@/components/ScrollToTop";
import LiveChatExamplesCompact from "@/components/landing/LiveChatExamplesCompact";
import LanguageSwitcher from '@/components/layout/LanguageSwitcher';
import { useCurrentLocale } from '@/shared/hooks/useCurrentLocale';
import { detectPlatform } from "@/lib/platform";
import { checkAndSaveReferralFromURL, getReferralCode } from "@/shared/lib/referral";
import { setLocaleCookie } from "@/shared/lib/locale";
import type { Locale } from "@/i18n";
import "@/app/landing/landing.css";
import { motion } from "framer-motion";
import { useAuthGuard } from "@/shared/hooks/useAuthGuard";
import QuickLoginModal from "@/components/modals/QuickLoginModal";
import { CONTACTS } from "@/config/contacts";

// Продвинутые варианты анимаций
const fadeInUp = {
  hidden: { opacity: 0, y: 30 },
  show: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.6,
    },
  },
};

const fadeIn = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      duration: 0.6,
    },
  },
};

const fadeInScale = {
  hidden: { opacity: 0, scale: 0.95 },
  show: {
    opacity: 1,
    scale: 1,
    transition: {
      duration: 0.7,
    },
  },
};

const slideInLeft = {
  hidden: { opacity: 0, x: -50 },
  show: {
    opacity: 1,
    x: 0,
    transition: {
      duration: 0.6,
    },
  },
};

const slideInRight = {
  hidden: { opacity: 0, x: 50 },
  show: {
    opacity: 1,
    x: 0,
    transition: {
      duration: 0.6,
    },
  },
};

const stagger = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.15,
      delayChildren: 0.1,
    },
  },
};

const staggerFast = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.08,
    },
  },
};

export default function Landing() {
  const t = useTranslations();
  const currentLocale = useCurrentLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [platform] = useState<string>(() => detectPlatform());
  const [showQuickLogin, setShowQuickLogin] = useState(false);

  // Smart Auth Guard - автоматический редирект для залогиненных пользователей
  const { isChecking, isAuthenticated } = useAuthGuard();

  // Определяем платформу, язык и сохраняем referral code из URL
  useEffect(() => {
    checkAndSaveReferralFromURL(); // Save ref code if present in URL

    // Read lang parameter from URL and set cookie for future localization
    const langParam = searchParams.get('lang');
    if (langParam && (langParam === 'en' || langParam === 'ru')) {
      setLocaleCookie(langParam as Locale);
      console.log('🌍 Language set from URL parameter:', langParam);
    }
  }, [searchParams]);

  // Auto-redirect authenticated users to /chat
  useEffect(() => {
    if (!isChecking && isAuthenticated) {
      console.log('✅ User already authenticated, redirecting to /chat');
      router.push('/chat');
    }
  }, [isChecking, isAuthenticated, router]);

  // Smart redirect handler
  const handleGetStarted = () => {
    if (platform === 'telegram') {
      // В Telegram → открыть бот с startapp и реф кодом
      const refCode = getReferralCode();
      let telegramUrl = 'https://t.me/SyntraAI_bot?startapp';

      if (refCode) {
        telegramUrl = `https://t.me/SyntraAI_bot?startapp=ref_${refCode}`;
        console.log('🎁 Opening Telegram with referral code:', refCode);
      }

      window.open(telegramUrl, '_blank');
    } else {
      // На веб → страница выбора метода авторизации (Telegram vs Email)
      router.push('/auth/choose');
    }
  };

  // Плавный скролл по якорям
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLAnchorElement;
      if (target.tagName === "A" && target.hash) {
        const href = target.getAttribute("href");
        if (href?.startsWith("#")) {
          e.preventDefault();
          const element = document.querySelector(href);
          if (element) {
            const yOffset = -80; // Отступ для header
            const y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;
            window.scrollTo({ top: y, behavior: "smooth" });
          }
        }
      }
    };

    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  return (
    <div className="relative min-h-screen bg-[#05030A] text-white overflow-hidden">
      <GlowCursor />
      <ScrollToTop />

      {/* Background blobs + grid */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="blob-1" />
        <div className="blob-2" />
        <div className="blob-3" />
        <div className="neon-grid" />
      </div>

      {/* HEADER */}
      <motion.header
        className="backdrop-blur-xl bg-black/30 border-b border-white/5 sticky top-0 z-40"
        variants={fadeIn}
        initial="hidden"
        animate="show"
      >
        <div className="container-header">
          <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Image
              src="/syntra/logo.png"
              width={32}
              height={32}
              alt="Syntra Logo"
              className="rounded-lg"
            />
            <span className="font-semibold tracking-wide text-sm">Syntra AI</span>
          </div>

          <nav className="hidden md:flex gap-6 text-sm text-white/60">
            <a href="#how" className="hover:text-[#3B82F6] transition duration-200">
              {t('landing.header.nav.how')}
            </a>
            <a href="#features" className="hover:text-[#3B82F6] transition duration-200">
              {t('landing.header.nav.features')}
            </a>
            <a href="#forwho" className="hover:text-[#3B82F6] transition duration-200">
              {t('landing.header.nav.forwho')}
            </a>
            <a href="#referral" className="hover:text-[#3B82F6] transition duration-200">
              {t('landing.header.nav.referral')}
            </a>
            <a href="#faq" className="hover:text-[#3B82F6] transition duration-200">
              {t('landing.header.nav.faq')}
            </a>
          </nav>

          <div className="flex items-center gap-3">
            {/* Language Switcher */}
            <LanguageSwitcher size="md" />

            {/* Social Icons - Telegram Channel + X */}
            <div className="flex items-center gap-2">
              <Link
                href="https://t.me/SyntraTrade"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center w-10 h-10 rounded-lg bg-[#229ED9]/10 hover:bg-[#229ED9]/20 border border-[#229ED9]/30 transition-all duration-200"
                title="Telegram Channel - @SyntraTrade"
              >
                <Image
                  src="/telegram.svg"
                  width={20}
                  height={20}
                  alt="Telegram Channel"
                  className="opacity-90"
                />
              </Link>
              <Link
                href="https://x.com/SyntraTrade"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center w-10 h-10 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-all duration-200"
                title="X (Twitter) - @SyntraTrade"
              >
                <Image
                  src="/x.png"
                  width={20}
                  height={20}
                  alt="X (Twitter)"
                  className="opacity-90"
                />
              </Link>
            </div>

            {/* Open Button */}
            <Link
              href="/auth/choose"
              className="btn btn-primary"
            >
              {t('landing.header.open')}
            </Link>
          </div>
          </div>
        </div>
      </motion.header>

      <main className="relative z-10">
        {/* HERO */}
        <motion.section
          className="hero-container grid md:grid-cols-[1.15fr_1fr] gap-10 items-center"
          variants={stagger}
          initial="hidden"
          animate="show"
        >
          <motion.div variants={slideInLeft}>
            <div className="inline-block px-3 py-1 rounded-full text-[10px] border border-white/20 text-white/60 backdrop-blur-xl mb-4 uppercase tracking-[0.16em]">
              {t('landing.hero.badge')}
            </div>

            <h1 className="text-4xl md:text-6xl font-bold leading-tight mb-5">
              {t('landing.hero.title')}
            </h1>

            <p className="text-white/70 mb-6 text-base md:text-lg">
              {t('landing.hero.subtitle')}
            </p>

            <ul className="space-y-2 text-white/60 mb-7 text-base">
              <li dangerouslySetInnerHTML={{ __html: t.raw('landing.hero.trial_feature') }} />
              <li>• {t('landing.hero.trial_requests')}</li>
              <li>• {t('landing.hero.trial_after')}</li>
            </ul>

            <div className="flex flex-wrap gap-4 items-center">
              {/* Smart CTA - auto-detect platform */}
              <button
                onClick={handleGetStarted}
                className="btn btn-primary"
              >
                {platform === 'telegram' ? t('landing.hero.cta_telegram') : t('landing.hero.cta_web')}
              </button>

              {/* Social Icons - Telegram Channel + X */}
              <div className="flex items-center gap-2">
                <Link
                  href="https://t.me/SyntraTrade"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center w-10 h-10 rounded-lg bg-[#229ED9]/10 hover:bg-[#229ED9]/20 border border-[#229ED9]/30 transition-all duration-200"
                  title="Telegram Channel - @SyntraTrade"
                >
                  <Image
                    src="/telegram.svg"
                    width={20}
                    height={20}
                    alt="Telegram Channel"
                    className="opacity-90"
                  />
                </Link>
                <Link
                  href="https://x.com/SyntraTrade"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center w-10 h-10 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-all duration-200"
                  title="X (Twitter) - @SyntraTrade"
                >
                  <Image
                    src="/x.png"
                    width={20}
                    height={20}
                    alt="X (Twitter)"
                    className="opacity-90"
                  />
                </Link>
              </div>
            </div>

            {/* Quick Login Link for returning users */}
            {platform !== 'telegram' && (
              <p className="text-sm text-white/60 mt-4">
                {t('landing.hero.quick_login')}{' '}
                <button
                  onClick={() => setShowQuickLogin(true)}
                  className="text-cyan-400 hover:text-cyan-300 font-semibold underline underline-offset-2 transition-colors"
                >
                  {t('landing.hero.sign_in')}
                </button>
              </p>
            )}

            <p className="text-sm text-white/40 mt-3 max-w-md">
              {platform === 'telegram'
                ? t('landing.hero.note_telegram')
                : t('landing.hero.note_web')}
            </p>
          </motion.div>

          <motion.div
            className="flex justify-center md:justify-end"
            variants={slideInRight}
          >
            <LiveChatExamplesCompact />
          </motion.div>
        </motion.section>

        {/* PROBLEM */}
        <motion.section
          id="problem"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <div className="grid md:grid-cols-[1.1fr,1.3fr] gap-8 items-start">
            <motion.div variants={fadeInUp}>
              <h2 className="text-2xl md:text-3xl font-semibold mb-3">
                {t('landing.problem.title')}
              </h2>
              <p className="text-sm text-white/70">
                {t('landing.problem.subtitle')}
              </p>
            </motion.div>
            <motion.div className="grid md:grid-cols-3 gap-3" variants={staggerFast}>
              <motion.div variants={fadeInScale} className="card">
                <h3>{t('landing.problem.noise_title')}</h3>
                <p>
                  {t('landing.problem.noise_text')}
                </p>
              </motion.div>
              <motion.div variants={fadeInScale} className="card">
                <h3>{t('landing.problem.emotions_title')}</h3>
                <p>
                  {t('landing.problem.emotions_text')}
                </p>
              </motion.div>
              <motion.div variants={fadeInScale} className="card">
                <h3>{t('landing.problem.structure_title')}</h3>
                <p>
                  {t('landing.problem.structure_text')}
                </p>
              </motion.div>
            </motion.div>
          </div>
        </motion.section>

        {/* SOLUTION */}
        <motion.section
          id="solution"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <div className="grid md:grid-cols-[1.1fr,1.3fr] gap-8 items-start">
            <motion.div variants={slideInLeft}>
              <h2 className="text-2xl md:text-3xl font-semibold mb-3">
                {t('landing.solution.title')}
              </h2>
              <p className="text-sm text-white/70">
                {t('landing.solution.subtitle')}
              </p>
            </motion.div>
            <motion.div className="grid md:grid-cols-3 gap-3" variants={staggerFast}>
              <motion.div variants={fadeInUp} className="card">
                <h3>{t('landing.solution.market_title')}</h3>
                <p>
                  {t('landing.solution.market_text')}
                </p>
              </motion.div>
              <motion.div variants={fadeInUp} className="card">
                <h3>{t('landing.solution.coins_title')}</h3>
                <p>
                  {t('landing.solution.coins_text')}
                </p>
              </motion.div>
              <motion.div variants={fadeInUp} className="card">
                <h3>{t('landing.solution.risks_title')}</h3>
                <p>
                  {t('landing.solution.risks_text')}
                </p>
              </motion.div>
            </motion.div>
          </div>
        </motion.section>

        {/* HOW IT WORKS */}
        <motion.section
          id="how"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <motion.h2
            className="text-2xl md:text-3xl font-semibold mb-3 text-center"
            variants={fadeInUp}
          >
            {t('landing.how.title')}
          </motion.h2>
          <motion.p
            className="text-sm text-white/70 text-center max-w-2xl mx-auto mb-8"
            variants={fadeInUp}
          >
            {t('landing.how.subtitle')}
          </motion.p>
          <div className="grid md:grid-cols-3 gap-4">
            <motion.div className="step-card" variants={fadeInUp}>
              <span className="step-number">1</span>
              <h3>{t('landing.how.step1_title')}</h3>
              <p>{t('landing.how.step1_text')}</p>
            </motion.div>
            <motion.div className="step-card" variants={fadeInUp}>
              <span className="step-number">2</span>
              <h3>{t('landing.how.step2_title')}</h3>
              <p>{t('landing.how.step2_text')}</p>
            </motion.div>
            <motion.div className="step-card" variants={fadeInUp}>
              <span className="step-number">3</span>
              <h3>{t('landing.how.step3_title')}</h3>
              <p>{t('landing.how.step3_text')}</p>
            </motion.div>
          </div>
        </motion.section>

        {/* FOR WHO */}
        <motion.section
          id="forwho"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <motion.h2
            className="text-2xl md:text-3xl font-semibold mb-3 text-center"
            variants={fadeInUp}
          >
            {t('landing.forwho.title')}
          </motion.h2>
          <div className="grid md:grid-cols-3 gap-4 mt-8">
            <motion.div className="card" variants={fadeInUp}>
              <h3>{t('landing.forwho.newbies_title')}</h3>
              <p>
                {t('landing.forwho.newbies_text')}
              </p>
            </motion.div>
            <motion.div className="card" variants={fadeInUp}>
              <h3>{t('landing.forwho.burned_title')}</h3>
              <p>
                {t('landing.forwho.burned_text')}
              </p>
            </motion.div>
            <motion.div className="card" variants={fadeInUp}>
              <h3>{t('landing.forwho.traders_title')}</h3>
              <p>
                {t('landing.forwho.traders_text')}
              </p>
            </motion.div>
          </div>
        </motion.section>

        {/* FEATURES */}
        <motion.section
          id="features"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <motion.h2
            className="text-2xl md:text-3xl font-semibold mb-3 text-center"
            variants={fadeInUp}
          >
            {t('landing.features.title')}
          </motion.h2>
          <motion.p
            className="text-sm text-white/70 text-center max-w-2xl mx-auto mb-8"
            variants={fadeInUp}
          >
            {t('landing.features.subtitle')}
          </motion.p>
          <div className="grid md:grid-cols-3 gap-4">
            <motion.div className="card" variants={fadeInUp}>
              <h3>{t('landing.features.market_title')}</h3>
              <p>
                {t('landing.features.market_text')}
              </p>
            </motion.div>
            <motion.div className="card" variants={fadeInUp}>
              <h3>{t('landing.features.risks_title')}</h3>
              <p>
                {t('landing.features.risks_text')}
              </p>
            </motion.div>
            <motion.div className="card" variants={fadeInUp}>
              <h3>{t('landing.features.friend_title')}</h3>
              <p>{t('landing.features.friend_text')}</p>
            </motion.div>
          </div>
        </motion.section>

        {/* PERSONALITY / VIBE */}
        <motion.section
          id="personality"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <div className="grid md:grid-cols-[1fr,1.2fr] gap-10 items-center">
            <motion.div variants={fadeInUp}>
              <h2 className="text-2xl md:text-3xl font-semibold mb-3">
                {t('landing.personality.title')}
              </h2>
              <p className="text-sm text-white/70 mb-6">
                {t('landing.personality.subtitle')}
              </p>
              <blockquote className="border-l-4 border-cyan-500/50 pl-4 py-2 bg-gray-800/30 rounded-r-lg">
                <p className="text-white/80 italic text-sm mb-2">
                  &ldquo;{t('landing.personality.quote')}&rdquo;
                </p>
                <cite className="text-xs text-white/50 not-italic">{t('landing.personality.quote_author')}</cite>
              </blockquote>
            </motion.div>
            <motion.div className="grid gap-3" variants={staggerFast}>
              <motion.div variants={fadeInScale} className="card">
                <h3>{t('landing.personality.direct_title')}</h3>
                <p className="text-sm">
                  {t('landing.personality.direct_text')}
                </p>
              </motion.div>
              <motion.div variants={fadeInScale} className="card">
                <h3>{t('landing.personality.rational_title')}</h3>
                <p className="text-sm">
                  {t('landing.personality.rational_text')}
                </p>
              </motion.div>
              <motion.div variants={fadeInScale} className="card">
                <h3>{t('landing.personality.irony_title')}</h3>
                <p className="text-sm">
                  {t('landing.personality.irony_text')}
                </p>
              </motion.div>
            </motion.div>
          </div>
        </motion.section>

        {/* PRICING */}
        <motion.section
          id="pricing"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <motion.h2
            className="text-2xl md:text-3xl font-semibold mb-3 text-center"
            variants={fadeInUp}
          >
            {t('landing.pricing.title')}
          </motion.h2>
          <motion.p
            className="text-sm text-white/70 text-center max-w-2xl mx-auto mb-8"
            variants={fadeInUp}
            dangerouslySetInnerHTML={{ __html: t.raw('landing.pricing.subtitle') }}
          />

          <div className="grid md:grid-cols-3 gap-4">
            {/* FREE TIER */}
            <motion.div className="pricing-card" variants={fadeInScale}>
              <h3>{t('landing.pricing.free_title')}</h3>
              <p className="pricing-price">{t('landing.pricing.free_price')}</p>
              <p className="text-xs text-white/50 mb-4">{t('landing.pricing.free_note')}</p>
              <ul className="pricing-list">
                <li>{t('landing.pricing.free_feature1')}</li>
                <li>{t('landing.pricing.free_feature2')}</li>
                <li>{t('landing.pricing.free_feature3')}</li>
                <li>{t('landing.pricing.free_feature4')}</li>
              </ul>
              <Link
                href="https://t.me/SyntraAI_bot"
                target="_blank"
                className="btn btn-ghost btn-full"
              >
                {t('landing.pricing.free_cta')}
              </Link>
            </motion.div>

            {/* BASIC TIER */}
            <motion.div className="pricing-card" variants={fadeInScale}>
              <h3>{t('landing.pricing.basic_title')}</h3>
              <p className="pricing-price">{t('landing.pricing.basic_price')}</p>
              <p className="text-xs text-white/50 mb-4">{t('landing.pricing.basic_note')}</p>
              <ul className="pricing-list">
                <li>{t('landing.pricing.basic_feature1')}</li>
                <li>{t('landing.pricing.basic_feature2')}</li>
                <li>{t('landing.pricing.basic_feature3')}</li>
                <li>{t('landing.pricing.basic_feature4')}</li>
                <li>{t('landing.pricing.basic_feature5')}</li>
              </ul>
              <Link
                href="https://t.me/SyntraAI_bot"
                target="_blank"
                className="btn btn-ghost btn-full"
              >
                {t('landing.pricing.basic_cta')}
              </Link>
            </motion.div>

            {/* PREMIUM TIER */}
            <motion.div className="pricing-card pricing-card-featured" variants={fadeInScale}>
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-gradient-to-r from-blue-600 to-blue-500 rounded-full text-[10px] font-semibold uppercase tracking-wider z-10">
                {t('landing.pricing.premium_badge')}
              </div>
              <h3>{t('landing.pricing.premium_title')}</h3>
              <p className="pricing-price">{t('landing.pricing.premium_price')}</p>
              <p className="text-xs text-white/50 mb-4">{t('landing.pricing.premium_note')}</p>
              <ul className="pricing-list">
                <li>{t('landing.pricing.premium_feature1')}</li>
                <li>{t('landing.pricing.premium_feature2')}</li>
                <li>{t('landing.pricing.premium_feature3')}</li>
                <li>{t('landing.pricing.premium_feature4')}</li>
                <li>{t('landing.pricing.premium_feature5')}</li>
                <li>{t('landing.pricing.premium_feature6')}</li>
              </ul>
              <Link
                href="https://t.me/SyntraAI_bot"
                target="_blank"
                className="btn btn-primary btn-full"
              >
                {t('landing.pricing.premium_cta')}
              </Link>
              <p className="text-xs text-white/40 mt-3 text-center">
                {t('landing.pricing.premium_discount')}
              </p>
            </motion.div>
          </div>
        </motion.section>

        {/* REFERRAL PROGRAM */}
        <motion.section
          id="referral"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <motion.h2
            className="text-2xl md:text-3xl font-semibold mb-3 text-center"
            variants={fadeInUp}
          >
            {t('landing.referral.title')}
          </motion.h2>
          <motion.p
            className="text-sm text-white/70 text-center max-w-2xl mx-auto mb-8"
            variants={fadeInUp}
            dangerouslySetInnerHTML={{ __html: t.raw('landing.referral.subtitle') }}
          />

          <div className="grid md:grid-cols-2 gap-6 mb-8">
            {/* Бонусы при регистрации */}
            <motion.div className="card" variants={fadeInUp}>
              <h3>{t('landing.referral.bonuses_title')}</h3>
              <div className="space-y-3 mt-4">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">👤</span>
                  <div>
                    <p className="font-semibold text-white/90">{t('landing.referral.friend_gets')}</p>
                    <p className="text-sm text-white/70">{t('landing.referral.friend_bonus')}</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <span className="text-2xl">🤝</span>
                  <div>
                    <p className="font-semibold text-white/90">{t('landing.referral.you_get')}</p>
                    <p className="text-sm text-white/70">{t('landing.referral.you_bonus')}</p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Как работает */}
            <motion.div className="card" variants={fadeInUp}>
              <h3>{t('landing.referral.how_title')}</h3>
              <ol className="space-y-2 mt-4 text-sm text-white/70">
                <li className="flex gap-2">
                  <span className="text-white/90 font-semibold">1.</span>
                  <span>{t('landing.referral.how_step1')}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-white/90 font-semibold">2.</span>
                  <span>{t('landing.referral.how_step2')}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-white/90 font-semibold">3.</span>
                  <span>{t('landing.referral.how_step3')}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-white/90 font-semibold">4.</span>
                  <span>{t('landing.referral.how_step4')}</span>
                </li>
              </ol>
            </motion.div>
          </div>

          {/* Tier система */}
          <motion.div variants={fadeInUp}>
            <h3 className="text-xl font-semibold mb-4 text-center">{t('landing.referral.tiers_title')}</h3>
            <div className="grid md:grid-cols-4 gap-3">
              {/* Bronze */}
              <div className="card text-center">
                <div className="text-3xl mb-2">🥉</div>
                <h4 className="font-semibold text-white/90 mb-1">{t('landing.referral.bronze')}</h4>
                <p className="text-xs text-white/60 mb-3">{t('landing.referral.bronze_range')}</p>
                <ul className="text-xs text-white/60 space-y-1">
                  <li>{t('landing.referral.bronze_benefits')}</li>
                </ul>
              </div>

              {/* Silver */}
              <div className="card text-center">
                <div className="text-3xl mb-2">🥈</div>
                <h4 className="font-semibold text-white/90 mb-1">{t('landing.referral.silver')}</h4>
                <p className="text-xs text-white/60 mb-3">{t('landing.referral.silver_range')}</p>
                <ul className="text-xs text-white/60 space-y-1">
                  <li>{t('landing.referral.silver_benefit1')}</li>
                  <li>{t('landing.referral.silver_benefit2')}</li>
                  <li className="text-gray-400 font-semibold">{t('landing.referral.silver_benefit3')}</li>
                </ul>
              </div>

              {/* Gold */}
              <div className="card text-center border-2 border-yellow-500/30">
                <div className="text-3xl mb-2">🥇</div>
                <h4 className="font-semibold text-white/90 mb-1">{t('landing.referral.gold')}</h4>
                <p className="text-xs text-white/60 mb-3">{t('landing.referral.gold_range')}</p>
                <ul className="text-xs text-white/60 space-y-1">
                  <li>{t('landing.referral.gold_benefit1')}</li>
                  <li>{t('landing.referral.gold_benefit2')}</li>
                  <li className="text-yellow-400 font-semibold">{t('landing.referral.gold_benefit3')}</li>
                </ul>
              </div>

              {/* Platinum */}
              <div className="card text-center border-2 border-purple-500/40">
                <div className="text-3xl mb-2">💎</div>
                <h4 className="font-semibold text-white/90 mb-1">{t('landing.referral.platinum')}</h4>
                <p className="text-xs text-white/60 mb-3">{t('landing.referral.platinum_range')}</p>
                <ul className="text-xs text-white/60 space-y-1">
                  <li>{t('landing.referral.platinum_benefit1')}</li>
                  <li>{t('landing.referral.platinum_benefit2')}</li>
                  <li className="text-purple-400 font-semibold">{t('landing.referral.platinum_benefit3')}</li>
                </ul>
              </div>
            </div>
            <p className="text-xs text-white/50 text-center mt-4">
              {t('landing.referral.revenue_note')}
            </p>
          </motion.div>
        </motion.section>

        {/* FAQ */}
        <motion.section
          id="faq"
          className="section-container"
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <motion.h2
            className="text-2xl md:text-3xl font-semibold mb-3 text-center"
            variants={fadeInUp}
          >
            {t('landing.faq.title')}
          </motion.h2>
          <div className="grid md:grid-cols-2 gap-4 mt-8">
            <motion.div className="faq-item" variants={fadeInUp}>
              <h3>{t('landing.faq.q1_title')}</h3>
              <p>
                {t('landing.faq.q1_text')}
              </p>
            </motion.div>
            <motion.div className="faq-item" variants={fadeInUp}>
              <h3>{t('landing.faq.q2_title')}</h3>
              <p>
                {t('landing.faq.q2_text')}
              </p>
            </motion.div>
            <motion.div className="faq-item" variants={fadeInUp}>
              <h3>{t('landing.faq.q3_title')}</h3>
              <p>
                {t('landing.faq.q3_text')}
              </p>
            </motion.div>
            <motion.div className="faq-item" variants={fadeInUp}>
              <h3>{t('landing.faq.q4_title')}</h3>
              <p>{t('landing.faq.q4_text')}</p>
            </motion.div>
            <motion.div className="faq-item" variants={fadeInUp}>
              <h3>{t('landing.faq.q5_title')}</h3>
              <p>
                {t('landing.faq.q5_text')}
              </p>
            </motion.div>
          </div>
        </motion.section>

        {/* FINAL CTA */}
        <motion.section
          className="final-cta-wrapper container"
          style={{ paddingBottom: '56px' }}
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.25 }}
        >
          <motion.div className="final-cta" variants={fadeInUp}>
            <div className="final-cta-content">
              <div>
                <h2>{t('landing.final_cta.title')}</h2>
                <p>
                  {t('landing.final_cta.subtitle')}
                </p>
              </div>
              <div className="final-actions">
                <Link
                  href="https://t.me/SyntraAI_bot"
                  target="_blank"
                  className="btn btn-primary"
                >
                  {t('landing.final_cta.bot_btn')}
                </Link>
                <Link
                  href="https://t.me/SyntraTrade"
                  target="_blank"
                  className="btn btn-ghost"
                >
                  {t('landing.final_cta.channel_btn')}
                </Link>
              </div>
            </div>
          </motion.div>
        </motion.section>
      </main>

      {/* Quick Login Modal */}
      <QuickLoginModal
        isOpen={showQuickLogin}
        onClose={() => setShowQuickLogin(false)}
        language={currentLocale}
      />

      {/* FOOTER */}
      <motion.footer
        className="footer"
        variants={fadeIn}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true }}
      >
        <div className="container">
          <div className="footer-content">
            <div className="footer-logo">
              <Image
                src="/syntra/logo.png"
                width={28}
                height={28}
                alt="Syntra Logo"
                className="rounded-lg"
              />
              <span>Syntra AI</span>
            </div>

            {/* Social Icons */}
            <div className="footer-socials">
              <div className="social-link-wrapper">
                <Link
                  href="https://t.me/SyntraAI_bot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="social-icon"
                  title="Telegram Bot - @SyntraAI_bot"
                >
                  <Image
                    src="/telegram.svg"
                    width={24}
                    height={24}
                    alt="Telegram Bot"
                    className="social-icon-img"
                  />
                </Link>
                <span className="social-label">{t('landing.footer.bot')}</span>
              </div>
              <div className="social-link-wrapper">
                <Link
                  href="https://t.me/SyntraTrade"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="social-icon"
                  title="Telegram Channel - @SyntraTrade"
                >
                  <Image
                    src="/telegram.svg"
                    width={24}
                    height={24}
                    alt="Telegram Channel"
                    className="social-icon-img"
                  />
                </Link>
                <span className="social-label">{t('landing.footer.channel')}</span>
              </div>
              <div className="social-link-wrapper">
                <Link
                  href={CONTACTS.telegramUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="social-icon"
                  title={`Community Manager - ${CONTACTS.telegram}`}
                >
                  <Image
                    src="/telegram.svg"
                    width={24}
                    height={24}
                    alt="Community Manager"
                    className="social-icon-img"
                  />
                </Link>
                <span className="social-label">{t('landing.footer.support')}</span>
              </div>
              <div className="social-link-wrapper">
                <a
                  href={`mailto:${CONTACTS.email}`}
                  className="social-icon"
                  title={CONTACTS.email}
                >
                  <Image
                    src="/email.svg"
                    width={24}
                    height={24}
                    alt="Email"
                    className="social-icon-img"
                  />
                </a>
                <span className="social-label">Email</span>
              </div>
            </div>

            <div className="footer-links">
              <span>
                <Link href="https://telegra.ph/Pravila-ispolzovaniya-Syntra-AI-11-23" target="_blank">
                  {t('landing.footer.terms')}
                </Link>
              </span>
              <span>
                <Link href="https://telegra.ph/Politika-konfidencialnosti-Syntra-AI-11-23" target="_blank">
                  {t('landing.footer.privacy')}
                </Link>
              </span>
            </div>
            <div className="footer-copy">{t('landing.footer.copyright')}</div>
          </div>
        </div>
      </motion.footer>
    </div>
  );
}
