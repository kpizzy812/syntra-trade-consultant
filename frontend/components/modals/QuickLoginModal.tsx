/**
 * Quick Login Modal
 * Быстрый вход для returning users прямо с лендинга
 */

'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface QuickLoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  language?: 'en' | 'ru';
}

export default function QuickLoginModal({ isOpen, onClose, language = 'en' }: QuickLoginModalProps) {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const t = {
    en: {
      title: 'Quick Sign In',
      subtitle: 'Enter your email to receive a magic link',
      emailPlaceholder: 'your@email.com',
      sendButton: 'Send Magic Link',
      sending: 'Sending...',
      successTitle: 'Check your email!',
      successMessage: 'We sent a magic link to',
      successInstructions: 'Open the email and click the link to sign in',
      close: 'Close',
      tryAnother: 'Try another email',
    },
    ru: {
      title: 'Быстрый вход',
      subtitle: 'Введите email для получения ссылки',
      emailPlaceholder: 'your@email.com',
      sendButton: 'Отправить Magic Link',
      sending: 'Отправляем...',
      successTitle: 'Проверьте почту!',
      successMessage: 'Мы отправили magic link на',
      successInstructions: 'Откройте письмо и кликните на ссылку для входа',
      close: 'Закрыть',
      tryAnother: 'Попробовать другой email',
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
        body: JSON.stringify({ email, language }),
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

  const handleClose = () => {
    setSent(false);
    setEmail('');
    setError('');
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
          />

          {/* Modal */}
          <div className="fixed inset-0 flex items-center justify-center z-50 px-4">
            <motion.div
              className="relative w-full max-w-md bg-gradient-to-br from-gray-900 to-gray-800 rounded-3xl border border-gray-700/50 shadow-2xl overflow-hidden"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ duration: 0.3 }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Glow effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 blur-3xl" />

              {/* Content */}
              <div className="relative z-10 p-8">
                {/* Close button */}
                <button
                  onClick={handleClose}
                  className="absolute top-4 right-4 w-8 h-8 rounded-full bg-gray-800/50 hover:bg-gray-700/50 flex items-center justify-center transition-colors"
                >
                  <span className="text-gray-400 text-xl">×</span>
                </button>

                {!sent ? (
                  <>
                    {/* Logo & Title */}
                    <div className="text-center mb-6">
                      <div className="w-12 h-12 bg-gradient-to-br from-cyan-400 to-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-cyan-500/20">
                        <span className="text-2xl">🤖</span>
                      </div>
                      <h2 className="text-2xl font-bold text-white mb-2">
                        {t.title}
                      </h2>
                      <p className="text-gray-400 text-sm">
                        {t.subtitle}
                      </p>
                    </div>

                    {/* Form */}
                    <form onSubmit={handleSubmit} className="space-y-4">
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder={t.emailPlaceholder}
                        required
                        className="w-full px-4 py-3 bg-gray-800/50 border border-gray-700/50 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
                      />

                      {error && (
                        <div className="bg-red-900/20 border border-red-500/50 text-red-400 px-4 py-3 rounded-xl text-sm">
                          {error}
                        </div>
                      )}

                      <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 text-white font-medium rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {loading ? (
                          <span className="flex items-center justify-center gap-2">
                            <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            {t.sending}
                          </span>
                        ) : (
                          t.sendButton
                        )}
                      </button>
                    </form>
                  </>
                ) : (
                  <>
                    {/* Success State */}
                    <div className="text-center">
                      {/* Success Icon */}
                      <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>

                      <h2 className="text-2xl font-bold text-white mb-2">
                        {t.successTitle}
                      </h2>
                      <p className="text-gray-400 text-sm mb-2">
                        {t.successMessage}
                      </p>
                      <p className="text-cyan-400 font-semibold mb-4">
                        {email}
                      </p>

                      <div className="bg-gray-800/50 p-4 rounded-xl mb-6">
                        <p className="text-sm text-gray-300">
                          📧 {t.successInstructions}
                        </p>
                      </div>

                      <div className="flex gap-3">
                        <button
                          onClick={() => {
                            setSent(false);
                            setEmail('');
                          }}
                          className="flex-1 px-4 py-2 border border-gray-600 text-gray-300 rounded-xl hover:bg-gray-700/50 transition-colors"
                        >
                          {t.tryAnother}
                        </button>
                        <button
                          onClick={handleClose}
                          className="flex-1 px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-medium rounded-xl hover:from-cyan-600 hover:to-blue-600 transition-all"
                        >
                          {t.close}
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
