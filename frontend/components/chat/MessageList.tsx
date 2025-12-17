/**
 * Message List Component
 * Список сообщений с auto-scroll к низу
 * Оптимизированный рендеринг
 */

'use client';

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ChatMessage from './ChatMessage';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  image?: string;  // Base64 image data
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

  return (
    <div
      ref={containerRef}
      className="h-full overflow-y-auto overflow-x-hidden px-4 py-4 scroll-smooth -webkit-overflow-scrolling-touch"
      style={{
        paddingBottom: 'calc(8rem + max(env(safe-area-inset-bottom), 0.5rem))',
        scrollBehavior: 'smooth',
        overscrollBehavior: 'contain',
        WebkitOverflowScrolling: 'touch',
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
              image={message.image}
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

      {/* Invisible element для auto-scroll */}
      <div ref={messagesEndRef} className="h-1" />
    </div>
  );
}
