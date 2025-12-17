/**
 * Suggested Prompts Component - ChatGPT Style
 * Круглые чипсы с быстрыми вопросами под инпутом
 */

'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useTranslations } from 'next-intl';
import { vibrate } from '@/shared/telegram/vibration';
import Image from 'next/image';

interface SuggestedPromptsProps {
  onSelectPrompt: (prompt: string) => void;
  show: boolean;
}

export default function SuggestedPrompts({
  onSelectPrompt,
  show,
}: SuggestedPromptsProps) {
  const t = useTranslations();

  const SUGGESTED_PROMPTS = [
    {
      icon: '₿',
      title: t('chat.suggested_prompts.analyze_btc'),
      prompt: t('chat.prompts.analyze_btc'),
    },
    {
      icon: '😨',
      title: t('chat.suggested_prompts.fear_greed'),
      prompt: t('chat.prompts.fear_greed'),
    },
    {
      icon: '🚀',
      title: t('chat.suggested_prompts.top_altcoins'),
      prompt: t('chat.prompts.top_altcoins'),
    },
    {
      icon: '⟠',
      title: t('chat.suggested_prompts.eth_analysis'),
      prompt: t('chat.prompts.eth_analysis'),
    },
  ];

  const handlePromptClick = (prompt: string) => {
    vibrate('light');
    onSelectPrompt(prompt);
  };

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          transition={{ duration: 0.2 }}
          className="w-full px-4 mb-1.5"
        >
          {/* ChatGPT-style chips - centered */}
          <div className="max-w-3xl mx-auto">
            <div className="flex flex-wrap gap-1.5 justify-center">
              {SUGGESTED_PROMPTS.map((suggestion, index) => (
                <motion.button
                  key={suggestion.title}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{
                    delay: index * 0.05,
                    duration: 0.2,
                  }}
                  onClick={() => handlePromptClick(suggestion.prompt)}
                  className="
                    flex items-center gap-1.5
                    px-2.5 py-1
                    bg-gradient-to-br from-blue-500/10 via-blue-600/5 to-blue-700/10
                    backdrop-blur-xl
                    hover:from-blue-500/15 hover:via-blue-600/10 hover:to-blue-700/15
                    border border-blue-500/20
                    hover:border-blue-400/30
                    rounded-full
                    text-xs text-white/90
                    shadow-lg shadow-blue-500/10
                    hover:shadow-blue-400/20
                    transition-all duration-200
                    active:scale-95
                  "
                >
                  <span className="text-sm">{suggestion.icon}</span>
                  <span className="whitespace-nowrap font-medium">{suggestion.title}</span>
                  {/* Points reward badge */}
                  <div className="flex items-center gap-0.5 px-1 py-0.5 bg-gradient-to-r from-blue-500/30 to-purple-500/30 rounded-full">
                    <Image
                      src="/syntra/$SYNTRA.png"
                      alt="$SYNTRA"
                      width={8}
                      height={8}
                      className="object-contain"
                    />
                    <span className="text-[9px] font-semibold text-blue-300">
                      +10
                    </span>
                  </div>
                </motion.button>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
