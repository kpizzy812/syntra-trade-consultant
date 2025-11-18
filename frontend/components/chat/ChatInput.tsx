/**
 * Chat Input Component
 * Поле ввода сообщений с suggested prompts
 * Адаптируется под клавиатуру Telegram
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { vibrate } from '@/shared/telegram/vibration';
import { useUserStore } from '@/shared/store/userStore';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
}

const SUGGESTED_PROMPTS = [
  {
    icon: '💡',
    text: 'Analyze BTC price action',
    prompt: 'Analyze current Bitcoin price action and give me trading insights',
  },
  {
    icon: '📊',
    text: 'Fear & Greed insights',
    prompt: 'What does the current Fear & Greed index tell us about the market?',
  },
  {
    icon: '🔍',
    text: 'Top altcoins',
    prompt: 'What are the most promising altcoins right now?',
  },
  {
    icon: '📈',
    text: 'ETH technical analysis',
    prompt: 'Provide technical analysis for Ethereum with key levels',
  },
];

export default function ChatInput({
  onSendMessage,
  isLoading = false,
  disabled = false,
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { user } = useUserStore();

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        120
      )}px`;
    }
  }, [message]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();

    if (!message.trim() || isLoading || disabled) return;

    vibrate('light');
    onSendMessage(message.trim());
    setMessage('');
    setShowSuggestions(false);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleSuggestedPrompt = (prompt: string) => {
    vibrate('light');
    setMessage(prompt);
    setShowSuggestions(false);
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Получаем информацию о лимитах пользователя из subscription
  const requestsUsed = user?.subscription?.requests_used_today || 0;
  const requestsLimit = user?.subscription?.daily_limit || 5;
  const requestsRemaining = user?.subscription?.requests_remaining ?? Math.max(0, requestsLimit - requestsUsed);
  const isLimitReached = requestsRemaining <= 0;

  return (
    <div className="border-t border-gray-800/50 bg-black/50 backdrop-blur-lg">
      {/* Suggested Prompts */}
      <AnimatePresence>
        {showSuggestions && message.length === 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="px-4 pt-3 overflow-hidden"
          >
            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
              {SUGGESTED_PROMPTS.map((suggestion, index) => (
                <motion.button
                  key={suggestion.text}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  onClick={() => handleSuggestedPrompt(suggestion.prompt)}
                  className="flex-shrink-0 px-3 py-2 bg-gray-800/50 hover:bg-gray-800/80 border border-gray-700/50 rounded-full text-xs text-gray-300 transition-all active:scale-95"
                >
                  <span className="mr-1">{suggestion.icon}</span>
                  {suggestion.text}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="p-4">
        <div className="flex items-end gap-2">
          {/* Textarea */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setShowSuggestions(false)}
              placeholder={
                isLimitReached
                  ? 'Daily limit reached. Upgrade to continue...'
                  : 'Ask about crypto markets...'
              }
              disabled={disabled || isLoading || isLimitReached}
              rows={1}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-700/50 rounded-2xl text-white placeholder-gray-500 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                maxHeight: '120px',
                minHeight: '44px',
              }}
            />

            {/* Request Counter */}
            <div className="absolute -top-6 right-0 text-xs text-gray-500">
              {requestsRemaining > 0 ? (
                <span>
                  {requestsRemaining} / {requestsLimit} requests today
                </span>
              ) : (
                <span className="text-orange-400">Limit reached</span>
              )}
            </div>
          </div>

          {/* Send Button */}
          <button
            type="submit"
            disabled={!message.trim() || isLoading || disabled || isLimitReached}
            className="flex-shrink-0 w-11 h-11 rounded-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed flex items-center justify-center transition-all active:scale-95 disabled:active:scale-100"
          >
            {isLoading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
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
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            )}
          </button>
        </div>

        {/* Upgrade Prompt (if limit reached) */}
        {isLimitReached && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 p-3 bg-gradient-to-r from-orange-500/10 to-red-500/10 border border-orange-500/30 rounded-xl"
          >
            <p className="text-xs text-orange-300 mb-2">
              You&apos;ve reached your daily limit ({requestsLimit} requests)
            </p>
            <button className="text-xs text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-full transition-colors">
              Upgrade to Premium →
            </button>
          </motion.div>
        )}

        {/* Hint Text */}
        <p className="text-xs text-gray-600 mt-2 text-center">
          Press Enter to send • Shift+Enter for new line
        </p>
      </form>
    </div>
  );
}
