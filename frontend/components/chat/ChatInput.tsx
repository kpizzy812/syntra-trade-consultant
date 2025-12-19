/**
 * Chat Input Component - ChatGPT Style
 * Минималистичный инпут с круглыми кнопками
 * С поддержкой Signals mode для Premium/VIP
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslations } from 'next-intl';
import { vibrate } from '@/shared/telegram/vibration';
import { useUserStore } from '@/shared/store/userStore';
import { usePlatform } from '@/lib/platform';
import { usePostHog } from '@/components/providers/PostHogProvider';
import { useKeyboardVisible } from '@/hooks/useKeyboardVisible';
import Image from 'next/image';
import SignalsGuideModal, { useSignalsGuide } from '@/components/modals/SignalsGuideModal';

interface ChatInputProps {
  onSendMessage: (message: string, image?: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
  signalsMode?: boolean;
  onSignalsModeChange?: (enabled: boolean) => void;
}

export default function ChatInput({
  onSendMessage,
  isLoading = false,
  disabled = false,
  signalsMode = false,
  onSignalsModeChange,
}: ChatInputProps) {
  const t = useTranslations();
  const tSignals = useTranslations('signals');
  const [message, setMessage] = useState('');
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [showGuideModal, setShowGuideModal] = useState(false);
  const [showSignalsTooltip, setShowSignalsTooltip] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { user } = useUserStore();
  const posthog = usePostHog();
  const isKeyboardVisible = useKeyboardVisible();
  const { shouldShowGuide } = useSignalsGuide();
  const { platformType } = usePlatform();

  // On mobile: Enter = new line, send only via button
  // On desktop: Enter = send, Shift+Enter = new line
  const isMobile = platformType === 'telegram' || platformType === 'ios' || platformType === 'android';

  // Check if user has premium/VIP tier (required for signals)
  // tier can be: FREE, BASIC, PREMIUM, VIP (uppercase from backend)
  const userTier = user?.subscription?.tier?.toUpperCase() || 'FREE';
  const canUseSignals = userTier === 'PREMIUM' || userTier === 'VIP';

  // Debug: log user tier info
  console.log('🔍 Signals check:', {
    tier: user?.subscription?.tier,
    userTier,
    canUseSignals,
    subscription: user?.subscription
  });

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

    // Allow sending if there's a message or an image
    if ((!message.trim() && !attachedImage) || isLoading || disabled) return;

    vibrate('light');
    onSendMessage(message.trim() || '', attachedImage || undefined);
    setMessage('');
    setAttachedImage(null);
    setImagePreview(null);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleImageAttach = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('Image size must be less than 10MB');
      return;
    }

    // Convert to base64
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64String = reader.result as string;
      setAttachedImage(base64String);
      setImagePreview(base64String);
      vibrate('light');
    };
    reader.readAsDataURL(file);
  };

  const handleRemoveImage = () => {
    setAttachedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    vibrate('light');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // On mobile: Enter always creates new line, send only via button
    // On desktop: Enter sends, Shift+Enter creates new line
    if (e.key === 'Enter') {
      if (isMobile) {
        // Mobile: Enter = new line (default behavior, don't prevent)
        return;
      } else {
        // Desktop: Enter = send, Shift+Enter = new line
        if (!e.shiftKey) {
          e.preventDefault();
          handleSubmit();
        }
      }
    }
  };

  // Handle paste events (Cmd+V / Ctrl+V) for images
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    // Check for image in clipboard
    for (let i = 0; i < items.length; i++) {
      const item = items[i];

      // Found an image
      if (item.type.startsWith('image/')) {
        e.preventDefault(); // Prevent default paste behavior for images

        const file = item.getAsFile();
        if (!file) continue;

        // Validate file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
          alert('Image size must be less than 10MB');
          return;
        }

        // Convert to base64
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64String = reader.result as string;
          setAttachedImage(base64String);
          setImagePreview(base64String);
          vibrate('light');

          // 📊 Track paste image event
          if (posthog.__loaded && user) {
            posthog.capture('image_pasted', {
              tier: user.subscription?.tier || 'free',
              image_type: file.type,
              image_size: file.size,
              platform: 'miniapp',
            });
          }
        };
        reader.readAsDataURL(file);
        break; // Only handle first image
      }
    }
  };

  // Получаем информацию о лимитах пользователя из subscription
  // FREE tier limit = 1 (see config/limits.py)
  const requestsUsed = user?.subscription?.requests_used_today || 0;
  const requestsLimit = user?.subscription?.daily_limit || 1;
  const requestsRemaining = user?.subscription?.requests_remaining ?? Math.max(0, requestsLimit - requestsUsed);
  const isLimitReached = requestsRemaining <= 0;

  // Calculate points reward (10-50 pts for text, +20-30 for vision)
  const baseReward = 10;
  const visionBonus = attachedImage ? 25 : 0;
  const estimatedReward = baseReward + visionBonus;

  // 📊 Track limit hit (only once when limit is reached)
  useEffect(() => {
    if (isLimitReached && posthog.__loaded && user) {
      posthog.capture('limit_hit', {
        tier: user.subscription?.tier || 'free',
        limit_type: 'text',
        requests_used: requestsUsed,
        requests_limit: requestsLimit,
        platform: 'miniapp',
      });
    }
  }, [isLimitReached, posthog, user, requestsUsed, requestsLimit]);

  // Handle signals toggle click
  const handleSignalsToggle = () => {
    if (!canUseSignals) {
      // Show tooltip for non-premium users
      setShowSignalsTooltip(true);
      vibrate('light');
      setTimeout(() => setShowSignalsTooltip(false), 3000);

      // 📊 Track premium gate hit
      if (posthog.__loaded && user) {
        posthog.capture('signals_premium_gate', {
          tier: userTier,
          platform: 'miniapp',
        });
      }
      return;
    }

    // If turning on and should show guide, show modal first
    if (!signalsMode && shouldShowGuide) {
      setShowGuideModal(true);
      vibrate('light');
      return;
    }

    // Toggle signals mode
    vibrate('light');
    onSignalsModeChange?.(!signalsMode);

    // 📊 Track signals toggle
    if (posthog.__loaded && user) {
      posthog.capture('signals_mode_toggle', {
        enabled: !signalsMode,
        tier: userTier,
        platform: 'miniapp',
      });
    }
  };

  // Handle guide modal confirm
  const handleGuideConfirm = () => {
    setShowGuideModal(false);
    onSignalsModeChange?.(true);

    // 📊 Track signals enabled after guide
    if (posthog.__loaded && user) {
      posthog.capture('signals_enabled_after_guide', {
        tier: userTier,
        platform: 'miniapp',
      });
    }
  };

  const handleUpgradeClick = () => {
    // 📊 Track upgrade button click
    if (posthog.__loaded && user) {
      posthog.capture('upgrade_button_clicked', {
        tier: user.subscription?.tier || 'free',
        source: 'chat_input_limit',
        platform: 'miniapp',
      });
    }
    vibrate('medium');
    window.location.href = '/profile';
  };

  return (
    <div
      className={`
        w-full px-4 pt-0
        transition-all duration-300 ease-in-out
        ${isKeyboardVisible ? 'pb-1' : 'pb-2'}
      `}
    >
      {/* ChatGPT-style Container */}
      <div className="max-w-3xl mx-auto">
        {/* Image Preview */}
        {imagePreview && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mb-3 relative inline-block"
          >
            <img
              src={imagePreview}
              alt="Attached"
              className="h-32 w-32 object-cover rounded-2xl border border-white/10 shadow-lg"
            />
            <button
              type="button"
              onClick={handleRemoveImage}
              className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center transition-all shadow-lg hover:scale-110"
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </motion.div>
        )}

        {/* Main Input Container - Glass Blue Style */}
        <form onSubmit={handleSubmit}>
          <div
            className={`
              relative flex items-center gap-2 px-4 py-2
              bg-gradient-to-br from-blue-500/10 via-blue-600/5 to-blue-700/10
              backdrop-blur-xl
              rounded-[26px]
              border border-blue-500/20
              shadow-lg shadow-blue-500/10
              transition-all duration-200
              ${!isLimitReached && 'hover:border-blue-400/30 hover:shadow-blue-400/20'}
              ${isLimitReached && 'opacity-50 cursor-not-allowed'}
            `}
          >
            {/* Plus Button (Attach) */}
            <button
              type="button"
              onClick={handleImageAttach}
              disabled={disabled || isLoading || isLimitReached}
              className="flex-shrink-0 w-8 h-8 rounded-full hover:bg-blue-500/20 disabled:hover:bg-transparent disabled:cursor-not-allowed disabled:opacity-40 flex items-center justify-center transition-all duration-200 active:scale-95"
              title="Attach image"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-blue-400"
              >
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </button>

            {/* Signals Toggle Button */}
            <div className="relative">
              <button
                type="button"
                onClick={handleSignalsToggle}
                disabled={disabled || isLoading || isLimitReached}
                className={`
                  flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                  transition-all duration-200 active:scale-95
                  disabled:cursor-not-allowed disabled:opacity-40
                  ${signalsMode
                    ? 'bg-gradient-to-br from-purple-500 to-blue-600 shadow-lg shadow-purple-500/30'
                    : 'hover:bg-blue-500/20 disabled:hover:bg-transparent'
                  }
                `}
                title={signalsMode ? tSignals('mode_active') : 'Signals'}
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className={signalsMode ? 'text-white' : 'text-blue-400'}
                >
                  {/* Lightning bolt icon */}
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                </svg>
              </button>

              {/* Signals Tooltip (for non-premium users) */}
              <AnimatePresence>
                {showSignalsTooltip && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.9 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.9 }}
                    className="absolute bottom-full left-0 mb-2 px-3 py-2 bg-gray-900 border border-orange-500/30 rounded-xl shadow-lg whitespace-nowrap z-50"
                  >
                    <p className="text-xs text-orange-300 font-medium">
                      {tSignals('premium_required')}
                    </p>
                    {/* Arrow pointing to button */}
                    <div className="absolute bottom-0 left-4 translate-y-1/2 w-2 h-2 bg-gray-900 border-r border-b border-orange-500/30 rotate-45" />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />

            {/* Textarea */}
            <div className="flex-1 min-h-[40px] flex items-center">
              <textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder={isLimitReached ? t('chat.input_placeholder_limit') : t('chat.input_placeholder')}
                disabled={disabled || isLoading || isLimitReached}
                rows={1}
                className="w-full bg-transparent border-0 text-white placeholder-gray-500 text-[15px] resize-none focus:outline-none disabled:cursor-not-allowed py-2"
                style={{
                  maxHeight: '120px',
                  minHeight: '24px',
                }}
              />
            </div>

            {/* Points Reward Indicator (показывается если есть текст или картинка) */}
            {(message.trim() || attachedImage) && !isLimitReached && !isLoading && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-1 px-2 py-1 bg-gradient-to-r from-blue-500/20 to-purple-500/20 border border-blue-500/30 rounded-full"
              >
                <Image
                  src="/syntra/$SYNTRA.png"
                  alt="$SYNTRA"
                  width={14}
                  height={14}
                  className="object-contain"
                />
                <span className="text-xs font-semibold text-blue-300">
                  +{estimatedReward}
                </span>
              </motion.div>
            )}

            {/* Send Button (Arrow Up) - Glass Blue */}
            <button
              type="submit"
              disabled={(!message.trim() && !attachedImage) || isLoading || disabled || isLimitReached}
              className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500 disabled:from-gray-700 disabled:to-gray-800 disabled:cursor-not-allowed flex items-center justify-center transition-all duration-200 active:scale-95 disabled:opacity-40 shadow-lg shadow-blue-500/30 hover:shadow-blue-400/40"
              title="Send message"
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="white"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              )}
            </button>
          </div>
        </form>

        {/* Upgrade Prompt (if limit reached) */}
        {isLimitReached && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="mt-4 p-4 bg-gradient-to-br from-orange-500/10 to-red-500/10 border border-orange-500/20 rounded-2xl"
          >
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-orange-400">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
              </div>
              <div className="flex-1">
                <p className="text-sm text-white font-medium mb-1">
                  Daily limit reached
                </p>
                <p className="text-xs text-gray-400 mb-3">
                  You&apos;ve used all {requestsLimit} requests today. Upgrade for unlimited access.
                </p>
                <button
                  onClick={handleUpgradeClick}
                  className="text-sm font-medium text-white bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 px-5 py-2 rounded-xl transition-all duration-200 active:scale-95"
                >
                  Upgrade to Premium →
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Signals Mode Indicator */}
        {signalsMode && !isLimitReached && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-2 flex items-center justify-center gap-2"
          >
            <div className="flex items-center gap-1.5 px-3 py-1 bg-gradient-to-r from-purple-500/20 to-blue-500/20 border border-purple-500/30 rounded-full">
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="text-purple-400"
              >
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
              <span className="text-xs font-medium text-purple-300">
                {tSignals('mode_active')}
              </span>
            </div>
          </motion.div>
        )}
      </div>

      {/* Signals Guide Modal */}
      <SignalsGuideModal
        isOpen={showGuideModal}
        onClose={() => setShowGuideModal(false)}
        onConfirm={handleGuideConfirm}
      />
    </div>
  );
}
