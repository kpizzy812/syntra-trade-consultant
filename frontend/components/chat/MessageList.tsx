/**
 * Message List Component
 * Список сообщений с auto-scroll к низу
 * Оптимизированный рендеринг
 */

'use client';

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ChatMessage from './ChatMessage';
import TypingIndicator from './TypingIndicator';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
}

interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
  onRegenerateMessage?: (messageId: string) => void;
}

export default function MessageList({
  messages,
  isLoading = false,
  onRegenerateMessage,
}: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll к низу при новых сообщениях
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages, isLoading]);

  // Если нет сообщений - показываем welcome screen
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center max-w-md"
        >
          {/* AI Icon */}
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="2"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>

          {/* Welcome Text */}
          <h2 className="text-2xl font-bold text-white mb-3">
            Syntra AI Assistant
          </h2>
          <p className="text-gray-400 text-sm mb-8">
            Your personal crypto trading advisor powered by AI.
            <br />
            Ask me anything about crypto markets, technical analysis, or trading strategies.
          </p>

          {/* Suggested Prompts */}
          <div className="space-y-2">
            <p className="text-xs text-gray-500 mb-3">Try asking:</p>
            <div className="grid gap-2">
              {[
                '💡 Analyze BTC price action',
                '📊 Show me Fear & Greed insights',
                '🔍 What are the top altcoins?',
                '📈 Technical analysis for ETH',
              ].map((prompt, index) => (
                <motion.button
                  key={prompt}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="text-left px-4 py-3 bg-gray-800/30 hover:bg-gray-800/50 border border-gray-700/30 hover:border-gray-600/50 rounded-xl text-sm text-gray-300 transition-all active:scale-98"
                >
                  {prompt}
                </motion.button>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto px-4 py-4 scroll-smooth"
      style={{
        scrollBehavior: 'smooth',
        overscrollBehavior: 'contain',
      }}
    >
      <AnimatePresence initial={false}>
        {messages.map((message, index) => (
          <motion.div
            key={message.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
          >
            <ChatMessage
              role={message.role}
              content={message.content}
              timestamp={message.timestamp}
              isStreaming={message.isStreaming}
              onRegenerate={
                message.role === 'assistant' && onRegenerateMessage
                  ? () => onRegenerateMessage(message.id)
                  : undefined
              }
            />
          </motion.div>
        ))}
      </AnimatePresence>

      {/* Typing Indicator */}
      {isLoading && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
        >
          <TypingIndicator />
        </motion.div>
      )}

      {/* Invisible element для auto-scroll */}
      <div ref={messagesEndRef} className="h-1" />
    </div>
  );
}
