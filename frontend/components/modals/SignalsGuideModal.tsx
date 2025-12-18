/**
 * Signals Guide Modal
 * Показывается при первом включении режима Signals
 * С чекбоксом "Больше не показывать"
 */

'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslations } from 'next-intl';

interface SignalsGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

const DONT_SHOW_KEY = 'signals_guide_dont_show';

export default function SignalsGuideModal({
  isOpen,
  onClose,
  onConfirm,
}: SignalsGuideModalProps) {
  const t = useTranslations('signals');
  const [dontShowAgain, setDontShowAgain] = useState(false);

  // Check localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(DONT_SHOW_KEY);
      if (stored === 'true') {
        setDontShowAgain(true);
      }
    }
  }, []);

  const handleConfirm = () => {
    // Save preference if checked
    if (dontShowAgain && typeof window !== 'undefined') {
      localStorage.setItem(DONT_SHOW_KEY, 'true');
    }
    onConfirm();
  };

  const handleClose = () => {
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50"
            onClick={handleClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed left-4 right-4 top-1/2 -translate-y-1/2 z-50 max-w-md mx-auto"
          >
            <div className="bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800 rounded-3xl border border-blue-500/20 shadow-2xl shadow-blue-500/10 overflow-hidden">
              {/* Header */}
              <div className="px-6 py-5 bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-b border-white/5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="white"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                    </svg>
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white">
                      {t('guide_title')}
                    </h2>
                    <p className="text-xs text-gray-400">
                      {t('guide_subtitle')}
                    </p>
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="px-6 py-5 space-y-4">
                {/* What is Signals */}
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <span className="text-blue-400">01</span>
                    {t('what_is_title')}
                  </h3>
                  <p className="text-sm text-gray-400 leading-relaxed">
                    {t('what_is_description')}
                  </p>
                </div>

                {/* What you get */}
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <span className="text-blue-400">02</span>
                    {t('what_you_get_title')}
                  </h3>
                  <ul className="space-y-1.5">
                    <li className="flex items-center gap-2 text-sm text-gray-400">
                      <span className="text-green-400">•</span>
                      {t('feature_entry')}
                    </li>
                    <li className="flex items-center gap-2 text-sm text-gray-400">
                      <span className="text-red-400">•</span>
                      {t('feature_stoploss')}
                    </li>
                    <li className="flex items-center gap-2 text-sm text-gray-400">
                      <span className="text-blue-400">•</span>
                      {t('feature_targets')}
                    </li>
                    <li className="flex items-center gap-2 text-sm text-gray-400">
                      <span className="text-purple-400">•</span>
                      {t('feature_leverage')}
                    </li>
                  </ul>
                </div>

                {/* How to use */}
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <span className="text-blue-400">03</span>
                    {t('how_to_use_title')}
                  </h3>
                  <div className="bg-white/5 rounded-xl p-3 space-y-1">
                    <code className="text-xs text-blue-300 block">BTC 4h</code>
                    <code className="text-xs text-blue-300 block">ETH 1d conservative</code>
                    <code className="text-xs text-blue-300 block">signal for SOL</code>
                  </div>
                </div>

                {/* Disclaimer */}
                <div className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-3">
                  <p className="text-xs text-orange-300/80 leading-relaxed">
                    {t('disclaimer')}
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="px-6 py-4 bg-black/20 border-t border-white/5">
                {/* Don't show again checkbox */}
                <label className="flex items-center gap-2 mb-4 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={dontShowAgain}
                    onChange={(e) => setDontShowAgain(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                  />
                  <span className="text-xs text-gray-400 group-hover:text-gray-300 transition-colors">
                    {t('dont_show_again')}
                  </span>
                </label>

                {/* Buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={handleClose}
                    className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-all"
                  >
                    {t('cancel')}
                  </button>
                  <button
                    onClick={handleConfirm}
                    className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 rounded-xl transition-all shadow-lg shadow-blue-500/20"
                  >
                    {t('enable_signals')}
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

/**
 * Hook to check if guide should be shown
 */
export function useSignalsGuide() {
  const [shouldShowGuide, setShouldShowGuide] = useState(true);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const dontShow = localStorage.getItem(DONT_SHOW_KEY);
      setShouldShowGuide(dontShow !== 'true');
    }
  }, []);

  return {
    shouldShowGuide,
    resetGuide: () => {
      if (typeof window !== 'undefined') {
        localStorage.removeItem(DONT_SHOW_KEY);
        setShouldShowGuide(true);
      }
    },
  };
}
