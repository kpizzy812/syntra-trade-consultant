/**
 * Chat Page - Main AI Chat Interface
 * Apple/OpenAI/Anthropic level design
 * SSE Streaming support
 */

'use client';

import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import MessageList, { Message } from '@/components/chat/MessageList';
import ChatInput from '@/components/chat/ChatInput';
import { useUserStore } from '@/shared/store/userStore';
import { api } from '@/shared/api/client';

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { user } = useUserStore();

  // Send message handler with SSE streaming
  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      // Add user message to chat
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: content.trim(),
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      // Create streaming AI message
      const aiMessageId = `assistant-${Date.now()}`;
      const aiMessage: Message = {
        id: aiMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        isStreaming: true,
      };

      setMessages((prev) => [...prev, aiMessage]);

      try {
        // Stream response from backend
        await api.chat.streamMessage(
          content.trim(),
          // On token received
          (token: string) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, content: msg.content + token }
                  : msg
              )
            );
          },
          // On error
          (error: string) => {
            console.error('Streaming error:', error);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? {
                      ...msg,
                      content:
                        'Sorry, I encountered an error. Please try again.',
                      isStreaming: false,
                    }
                  : msg
              )
            );
          },
          // On done
          () => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, isStreaming: false }
                  : msg
              )
            );
            setIsLoading(false);
          }
        );
      } catch (error) {
        console.error('Failed to send message:', error);

        // Update AI message with error
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === aiMessageId
              ? {
                  ...msg,
                  content:
                    'Sorry, I encountered an error. Please try again or contact support if the issue persists.',
                  isStreaming: false,
                }
              : msg
          )
        );
        setIsLoading(false);
      }
    },
    [isLoading]
  );

  // Simulate AI response (будет заменено на SSE streaming)
  const simulateAIResponse = async (userMessage: string) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const aiMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: generateMockResponse(userMessage),
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, aiMessage]);
        resolve(aiMessage);
      }, 1500);
    });
  };

  // Regenerate message handler
  const handleRegenerateMessage = useCallback(
    async (messageId: string) => {
      const messageIndex = messages.findIndex((m) => m.id === messageId);
      if (messageIndex === -1) return;

      // Remove messages from this point forward
      setMessages((prev) => prev.slice(0, messageIndex));
      setIsLoading(true);

      // Create a placeholder message for the new response
      const placeholderMessage: Message = {
        id: `temp-${Date.now()}`,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, placeholderMessage]);

      try {
        let fullResponse = '';

        // Stream the regenerated response
        await api.chat.regenerateMessage(
          parseInt(messageId),
          (token) => {
            // Append token to response
            fullResponse += token;
            setMessages((prev) => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              if (lastMessage.role === 'assistant') {
                lastMessage.content = fullResponse;
              }
              return newMessages;
            });
          },
          (error) => {
            console.error('Regenerate error:', error);
            toast.error(`Failed to regenerate: ${error}`);
          },
          () => {
            // Regeneration complete
            setIsLoading(false);
            // Update message ID with server-generated ID (if needed)
            setMessages((prev) => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              if (lastMessage.id.startsWith('temp-')) {
                lastMessage.id = `msg-${Date.now()}`;
              }
              return newMessages;
            });
          }
        );
      } catch (error) {
        console.error('Failed to regenerate:', error);
        toast.error('Failed to regenerate message');
        setIsLoading(false);
        // Remove placeholder message on error
        setMessages((prev) => prev.slice(0, -1));
      }
    },
    [messages]
  );

  return (
    <div className="min-h-screen bg-black flex flex-col mobile-body">
      <Header title="AI Chat" showBack={false} />

      {/* Chat Container */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Messages Area */}
        <MessageList
          messages={messages}
          isLoading={isLoading}
          onRegenerateMessage={handleRegenerateMessage}
        />

        {/* Input Area */}
        <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
      </div>

      <TabBar />
    </div>
  );
}

// Mock response generator (будет заменено на SSE streaming)
function generateMockResponse(userMessage: string): string {
  const lowerMessage = userMessage.toLowerCase();

  if (lowerMessage.includes('btc') || lowerMessage.includes('bitcoin')) {
    return `# Bitcoin Analysis

Based on current market conditions:

## Technical Overview
- **Price Action**: BTC is showing strong momentum with bullish structure
- **Support Levels**: $42,000 - $43,500
- **Resistance**: $48,000 - $50,000

## Key Indicators
\`\`\`
RSI: 62 (Neutral-Bullish)
MACD: Bullish crossover
Volume: Above average
\`\`\`

## Trading Recommendation
Consider **accumulation** on dips to support levels. Set stop-loss below $42,000 for risk management.

*This is AI-generated analysis. Always do your own research.*`;
  }

  if (lowerMessage.includes('eth') || lowerMessage.includes('ethereum')) {
    return `# Ethereum Technical Analysis

## Current Market Structure
- ETH is consolidating after recent rally
- Key support at **$2,800**
- Resistance at **$3,200**

## Technical Indicators
| Indicator | Value | Signal |
|-----------|-------|--------|
| RSI (14) | 58 | Neutral |
| MACD | Bullish | Buy |
| MA(50) | $2,750 | Support |

Looking strong for a continuation pattern. Watch for breakout above $3,200.`;
  }

  if (lowerMessage.includes('fear') || lowerMessage.includes('greed')) {
    return `# Fear & Greed Index Analysis

The current market sentiment shows **Fear (25/100)**.

## What this means:
- Investors are worried about market conditions
- Potentially good buying opportunity (contrarian signal)
- Market may be oversold

## Historical Context:
During extreme fear periods, Bitcoin has historically shown strong recoveries within 2-4 weeks.

**Strategy**: Consider DCA (Dollar Cost Averaging) into quality projects during fear periods.`;
  }

  if (lowerMessage.includes('altcoin') || lowerMessage.includes('alt')) {
    return `# Top Altcoins to Watch

## 1. **Solana (SOL)** 🚀
- Strong ecosystem growth
- High transaction throughput
- Target: $120-$150

## 2. **Avalanche (AVAX)** ❄️
- DeFi adoption increasing
- Low fees, fast finality
- Target: $40-$50

## 3. **Polygon (MATIC)** 🔷
- Ethereum scaling solution
- Enterprise partnerships
- Target: $1.20-$1.50

*Always manage risk and only invest what you can afford to lose.*`;
  }

  // Default response
  return `I understand you're asking about: "${userMessage}"

I'm Syntra AI, your crypto trading assistant. I can help you with:

- 📊 **Market Analysis**: BTC, ETH, and altcoin analysis
- 📈 **Technical Indicators**: RSI, MACD, support/resistance
- 💡 **Trading Strategies**: Entry/exit points, risk management
- 🎯 **Portfolio Advice**: Diversification and allocation

Ask me anything about crypto markets, and I'll provide detailed insights!`;
}
