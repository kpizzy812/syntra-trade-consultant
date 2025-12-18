/**
 * Chat Page - Main AI Chat Interface
 * ChatGPT-style с crypto analytics вайбом
 * SSE Streaming support + Desktop адаптация
 */

'use client';

import { useState, useCallback, useEffect, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import toast from 'react-hot-toast';
import TabBar from '@/components/layout/TabBar';
import DesktopLayout from '@/components/layout/DesktopLayout';
import MessageList, { Message } from '@/components/chat/MessageList';
import ChatInput from '@/components/chat/ChatInput';
import SuggestedPrompts from '@/components/chat/SuggestedPrompts';
import ChatSidebar from '@/components/chat/ChatSidebar';
import PremiumPurchaseModal from '@/components/modals/PremiumPurchaseModal';
import LanguageSwitcher from '@/components/layout/LanguageSwitcher';
import PointsEarnAnimation from '@/components/points/PointsEarnAnimation';
import PointsBalance from '@/components/points/PointsBalance';
import { useUserStore } from '@/shared/store/userStore';
import { usePointsStore } from '@/shared/store/pointsStore';
import { api } from '@/shared/api/client';
import { usePostHog } from '@/components/providers/PostHogProvider';
import { usePlatform } from '@/lib/platform';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { useAuthGuard } from '@/shared/hooks/useAuthGuard';

export default function ChatPage() {
  const t = useTranslations();

  // Initial bot messages with i18n - memoized to prevent unnecessary re-renders
  const getInitialMessages = useCallback((): Message[] => [
    {
      id: 'intro-1',
      role: 'assistant',
      content: t('chat.intro_greeting'),
      timestamp: new Date().toISOString(),
    },
    {
      id: 'intro-2',
      role: 'assistant',
      content: t('chat.intro_capabilities'),
      timestamp: new Date().toISOString(),
    },
  ], [t]);

  // Memoized initial messages for comparison
  const INITIAL_MESSAGES = useMemo(() => getInitialMessages(), [getInitialMessages]);

  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [isLoading, setIsLoading] = useState(false);
  const [showPremiumModal, setShowPremiumModal] = useState(false);
  const [referralDiscount, setReferralDiscount] = useState(0);
  const [signalsMode, setSignalsMode] = useState(false);
  const { user } = useUserStore();
  const { updateBalance, setBalance } = usePointsStore();
  const { platformType } = usePlatform();
  const searchParams = useSearchParams();
  const [initialPromptSent, setInitialPromptSent] = useState(false);
  const posthog = usePostHog();
  const [currentChatId, setCurrentChatId] = useState<number | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const router = useRouter();
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);
  const [pointsEarnTrigger, setPointsEarnTrigger] = useState(0);
  const [pointsEarnAmount, setPointsEarnAmount] = useState(0);

  // Persist active chat ID to localStorage
  const ACTIVE_CHAT_KEY = 'syntra_active_chat_id';

  const isDesktop = platformType === 'web';

  // Smart Auth Guard - редирект на /auth/choose если не залогинен
  const { isChecking, isAuthenticated } = useAuthGuard();

  // Enable keyboard shortcuts на desktop
  useKeyboardShortcuts();

  // Track keyboard visibility для адаптации layout
  useEffect(() => {
    if (typeof window === 'undefined' || !window.visualViewport) {
      return;
    }

    const visualViewport = window.visualViewport;
    const initialHeight = visualViewport.height;

    const handleResize = () => {
      const currentHeight = visualViewport.height;
      const heightDiff = initialHeight - currentHeight;
      setIsKeyboardVisible(heightDiff > 150);
    };

    visualViewport.addEventListener('resize', handleResize);
    visualViewport.addEventListener('scroll', handleResize);

    return () => {
      visualViewport.removeEventListener('resize', handleResize);
      visualViewport.removeEventListener('scroll', handleResize);
    };
  }, []);

  // Open premium modal with referral discount loaded
  const openPremiumModal = useCallback(async () => {
    try {
      const stats = await api.referral.getStats();
      setReferralDiscount(stats.tier_benefits?.discount_percent || 0);
    } catch (e) {
      console.warn('Failed to load referral discount:', e);
      setReferralDiscount(0);
    }
    setShowPremiumModal(true);
  }, []);

  // Redirect unauthenticated web users to auth flow
  useEffect(() => {
    if (!isChecking && !isAuthenticated && platformType === 'web') {
      console.log('❌ User not authenticated, redirecting to /auth/choose');
      router.push('/auth/choose');
    }
  }, [isChecking, isAuthenticated, platformType, router]);

  // Load chat history for specific chat - memoized to prevent race conditions
  const loadChatHistory = useCallback(async (chatId: number) => {
    try {
      setIsLoadingHistory(true);
      const response = await api.chats.getChatMessages(chatId);

      if (response.messages && response.messages.length > 0) {
        // Convert API messages to Message format
        const loadedMessages: Message[] = response.messages.map((msg: {
          id: number;
          role: 'user' | 'assistant';
          content: string;
          timestamp: string;
        }) => ({
          id: `msg-${msg.id}`,
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp,
        }));
        setMessages(loadedMessages);
      } else {
        // Empty chat - show initial messages
        setMessages(getInitialMessages());
      }
    } catch (error) {
      console.error('Failed to load chat history:', error);
      toast.error(t('chat.error_load_history'));
      setMessages(getInitialMessages());
    } finally {
      setIsLoadingHistory(false);
    }
  }, [t, getInitialMessages]);

  // Load chat history when chat_id changes or restore from localStorage
  useEffect(() => {
    const chatIdParam = searchParams.get('chat_id');

    if (chatIdParam) {
      // URL has chat_id - use it and save to localStorage
      const chatId = parseInt(chatIdParam);
      setCurrentChatId(chatId);
      loadChatHistory(chatId);
      // Persist to localStorage for session restoration
      try {
        localStorage.setItem(ACTIVE_CHAT_KEY, chatId.toString());
      } catch (e) {
        console.warn('Failed to save chat ID to localStorage:', e);
      }
    } else {
      // No chat_id in URL - try to restore from localStorage
      try {
        const savedChatId = localStorage.getItem(ACTIVE_CHAT_KEY);
        if (savedChatId) {
          const chatId = parseInt(savedChatId);
          if (!isNaN(chatId) && chatId > 0) {
            // Redirect to chat with restored chat_id
            router.replace(`/chat?chat_id=${chatId}`);
            return;
          }
        }
      } catch (e) {
        console.warn('Failed to read chat ID from localStorage:', e);
      }
      // No saved chat - show initial messages
      setMessages(getInitialMessages());
      setCurrentChatId(null);
    }
  }, [searchParams, loadChatHistory, getInitialMessages, router, ACTIVE_CHAT_KEY]);

  // Send message handler with SSE streaming
  const handleSendMessage = useCallback(
    async (content: string, image?: string, skipPointsAnimation = false) => {
      if ((!content.trim() && !image) || isLoading) return;

      // 🆕 Create new chat if sending first message without chat_id
      let chatIdToUse = currentChatId;
      if (!chatIdToUse) {
        try {
          const newChat = await api.chats.createChat('New Chat');
          chatIdToUse = newChat.id;
          setCurrentChatId(newChat.id);
          // Save to localStorage
          try {
            localStorage.setItem(ACTIVE_CHAT_KEY, newChat.id.toString());
          } catch (e) {
            console.warn('Failed to save chat ID to localStorage:', e);
          }
          // Update URL with chat_id (without page reload)
          router.replace(`/chat?chat_id=${newChat.id}`, { scroll: false });
          console.log(`✅ New chat created before first message: chat_id=${newChat.id}`);
        } catch (error) {
          console.error('Failed to create chat:', error);
          toast.error(t('chat.error_create_chat') || 'Failed to create chat');
          return;
        }
      }

      // Add user message to chat
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: content.trim(),
        image: image,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      // ✨ Trigger points earn animation (+10 for message) - unless skipped
      if (!skipPointsAnimation) {
        const earnedPoints = 10; // Базовая ставка из config/points_config.py
        setPointsEarnAmount(earnedPoints);
        setPointsEarnTrigger((prev) => prev + 1);
        // Note: Real balance will be updated from API after stream completes
      }

      // 📊 Track AI request sent
      if (posthog.__loaded) {
        posthog.capture('ai_request_sent', {
          tier: user?.subscription?.tier || 'free',
          has_image: !!image,
          message_length: content.trim().length,
          platform: 'miniapp',
        });
      }

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

      // 🔮 SIGNALS MODE: Use futures analysis API instead of regular chat
      if (signalsMode) {
        try {
          const tSignals = t;
          const userLang = user?.language || 'ru';

          // Call futures signals API
          const result = await api.futuresSignals.analyze({
            message: content.trim(),
            language: userLang,
          });

          let responseContent = '';

          if (result.success) {
            // Format successful scenario response
            if (result.scenarios && result.scenarios.length > 0) {
              const scenario = result.scenarios[0]; // Primary scenario

              responseContent = `## 📊 ${scenario.direction === 'long' ? '🟢 LONG' : '🔴 SHORT'} ${result.ticker}\n\n`;
              responseContent += `**Timeframe:** ${result.timeframe}\n`;
              responseContent += `**Mode:** ${scenario.mode}\n`;
              responseContent += `**Confidence:** ${Math.round((scenario.confidence || 0.7) * 100)}%\n\n`;

              // Entry Plan
              if (scenario.entry_plan?.orders) {
                responseContent += `### 📍 Entry Plan\n`;
                scenario.entry_plan.orders.forEach((order: { price: number; allocation: number }, i: number) => {
                  responseContent += `- **Entry ${i + 1}:** $${order.price.toLocaleString()} (${order.allocation}%)\n`;
                });
                responseContent += '\n';
              }

              // Stop Loss
              if (scenario.stop_loss) {
                responseContent += `### 🛑 Stop Loss\n`;
                responseContent += `- **Recommended:** $${scenario.stop_loss.recommended?.toLocaleString()}\n`;
                if (scenario.stop_loss.aggressive) {
                  responseContent += `- **Aggressive:** $${scenario.stop_loss.aggressive.toLocaleString()}\n`;
                }
                responseContent += '\n';
              }

              // Take Profit Targets
              if (scenario.targets && scenario.targets.length > 0) {
                responseContent += `### 🎯 Take Profit Targets\n`;
                scenario.targets.forEach((tp: { level: string; price: number; rr: number; allocation: number }) => {
                  responseContent += `- **${tp.level}:** $${tp.price.toLocaleString()} (R:R ${tp.rr}x, ${tp.allocation}%)\n`;
                });
                responseContent += '\n';
              }

              // Leverage
              if (scenario.leverage) {
                responseContent += `### ⚡ Leverage\n`;
                responseContent += `- **Recommended:** ${scenario.leverage.recommended}x\n`;
                responseContent += `- **Max:** ${scenario.leverage.max}x\n\n`;
              }

              // Rationale
              if (scenario.rationale) {
                responseContent += `### 💡 Rationale\n${scenario.rationale}\n`;
              }

            } else if (result.clarifying_questions && result.clarifying_questions.length > 0) {
              // Need clarification
              responseContent = `### 🤔 ${tSignals('signals.clarification_needed')}\n\n`;
              result.clarifying_questions.forEach((q: string) => {
                responseContent += `- ${q}\n`;
              });
            }

            // Show default timeframe message if applicable
            if (result.default_message) {
              responseContent = `> ℹ️ ${result.default_message}\n\n` + responseContent;
            }

          } else {
            // Error response
            responseContent = `❌ ${result.error || tSignals('signals.error')}`;

            // If limit issue, show remaining
            if (result.remaining !== undefined) {
              responseContent += `\n\n📊 ${tSignals('signals.remaining', { count: result.remaining, limit: result.limit || 1 })}`;
            }
          }

          // Update message with response
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aiMessageId
                ? { ...msg, content: responseContent, isStreaming: false }
                : msg
            )
          );

          // 📊 Track signals request
          if (posthog.__loaded) {
            posthog.capture('signals_request_completed', {
              success: result.success,
              ticker: result.ticker,
              tier: user?.subscription?.tier || 'free',
              platform: 'miniapp',
            });
          }

        } catch (error) {
          console.error('Signals API error:', error);
          const errorMessage = (error as { message?: string })?.message || t('signals.error');

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aiMessageId
                ? { ...msg, content: `❌ ${errorMessage}`, isStreaming: false }
                : msg
            )
          );
        } finally {
          setIsLoading(false);
        }
        return; // Exit early for signals mode
      }

      // 💬 REGULAR CHAT MODE
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
                      content: t('chat.error_simple'),
                      isStreaming: false,
                    }
                  : msg
              )
            );
          },
          // On done (with chat_id from backend)
          async (receivedChatId?: number) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMessageId
                  ? { ...msg, isStreaming: false }
                  : msg
              )
            );
            setIsLoading(false);

            // Save chat_id for future messages
            if (receivedChatId && !currentChatId) {
              setCurrentChatId(receivedChatId);
              // Save to localStorage and URL
              try {
                localStorage.setItem(ACTIVE_CHAT_KEY, receivedChatId.toString());
              } catch (e) {
                console.warn('Failed to save chat ID to localStorage:', e);
              }
              // Update URL with chat_id (without page reload)
              router.replace(`/chat?chat_id=${receivedChatId}`, { scroll: false });
              console.log(`✅ Chat created and saved: chat_id=${receivedChatId}`);
            }

            // 💎 Fetch real balance from backend after message completion
            try {
              const balanceData = await api.points.getBalance();
              setBalance(balanceData);
              console.log('💎 Points balance updated from API:', balanceData.balance);
            } catch (error) {
              console.warn('Failed to refresh points balance:', error);
            }
          },
          // Image (if provided)
          image,
          // Chat ID (always use chatIdToUse which is guaranteed to exist now)
          chatIdToUse || undefined
        );
      } catch (error: unknown) {
        console.error('Failed to send message:', error);

        // Type guard for error with custom properties
        const apiError = error as { status?: number; errorCode?: string; message?: string; showUpgrade?: boolean };

        // Check if rate limit error (429)
        if (apiError.status === 429 || apiError.errorCode === 'RATE_LIMIT_EXCEEDED') {
          // Show rate limit message and Premium modal
          const errorMessage = apiError.message || t('chat.rate_limit_reached');

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aiMessageId
                ? {
                    ...msg,
                    content: errorMessage,
                    isStreaming: false,
                  }
                : msg
            )
          );

          // Show Premium modal if user should upgrade
          if (apiError.showUpgrade) {
            toast.error(errorMessage, { duration: 5000 });
            setTimeout(() => openPremiumModal(), 500);
          } else {
            toast.error(errorMessage, { duration: 5000 });
          }
        } else {
          // Generic error
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === aiMessageId
                ? {
                    ...msg,
                    content: t('chat.error_detailed'),
                    isStreaming: false,
                  }
                : msg
            )
          );
        }
        setIsLoading(false);
      }
    },
    [isLoading, posthog, user, currentChatId, t, openPremiumModal, updateBalance, router, setBalance, signalsMode]
  );

  // Auto-send prompt from URL parameter (for "What does it mean?" button)
  useEffect(() => {
    const promptParam = searchParams.get('prompt');
    const pointsParam = searchParams.get('points');

    if (promptParam && !initialPromptSent && !isLoading) {
      try {
        const decodedPrompt = decodeURIComponent(promptParam);
        setInitialPromptSent(true);

        // ✨ Trigger points earn animation with custom amount if provided
        if (pointsParam) {
          const points = parseInt(pointsParam);
          if (!isNaN(points) && points > 0) {
            setPointsEarnAmount(points);
            setPointsEarnTrigger((prev) => prev + 1);
            // Note: Real balance will be updated from API after stream completes
          }
        }

        // Remove prompt and points from URL to prevent re-sending on refresh
        const newUrl = new URL(window.location.href);
        newUrl.searchParams.delete('prompt');
        newUrl.searchParams.delete('points');
        window.history.replaceState({}, '', newUrl.toString());

        // Small delay to ensure UI is ready, then send
        // Skip points animation because we already triggered it above
        setTimeout(() => {
          handleSendMessage(decodedPrompt, undefined, true);
        }, 500);
      } catch (error) {
        console.error('Failed to decode prompt from URL:', error);
        // Fallback: use the raw prompt if decoding fails
        setInitialPromptSent(true);
        const newUrl = new URL(window.location.href);
        newUrl.searchParams.delete('prompt');
        newUrl.searchParams.delete('points');
        window.history.replaceState({}, '', newUrl.toString());

        setTimeout(() => {
          handleSendMessage(promptParam, undefined, true);
        }, 500);
      }
    }
  }, [searchParams, initialPromptSent, isLoading, handleSendMessage, updateBalance]);

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
            toast.error(t('chat.error_regenerate'));
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
        toast.error(t('chat.error_regenerate'));
        setIsLoading(false);
        // Remove placeholder message on error
        setMessages((prev) => prev.slice(0, -1));
      }
    },
    [messages, t]
  );

  return (
    <DesktopLayout>
      {/* ChatGPT-style adaptive container */}
      <div
        className={`
        flex flex-col h-full
        ${isDesktop ? 'bg-black' : 'bg-black mobile-body'}
      `}
      >
        {/* Header с гамбургер-меню для мобильных */}
        <header className="border-b border-white/5 bg-black/80 backdrop-blur-lg px-4 py-1.5">
          <div className="flex items-center justify-between max-w-[520px] mx-auto lg:max-w-full">
            {/* Left: Hamburger + Title */}
            <div className="flex items-center gap-3">
              {/* Hamburger Menu Button (Mobile/Telegram) */}
              {!isDesktop && (
                <button
                  onClick={() => setIsSidebarOpen(true)}
                  className="p-2 -ml-2 rounded-lg hover:bg-white/5 transition-colors"
                  aria-label="Open chats"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-gray-400"
                  >
                    <line x1="3" y1="6" x2="21" y2="6"></line>
                    <line x1="3" y1="12" x2="21" y2="12"></line>
                    <line x1="3" y1="18" x2="21" y2="18"></line>
                  </svg>
                </button>
              )}
              <span className="text-white font-semibold text-sm">AI Chat</span>
            </div>

            {/* Right: Points Balance and Language Switcher */}
            <div className="flex items-center gap-2.5">
              <LanguageSwitcher size="sm" />
              {user && <PointsBalance />}
            </div>
          </div>
        </header>

        {/* ChatSidebar для мобильных/Telegram */}
        {!isDesktop && (
          <ChatSidebar
            isOpen={isSidebarOpen}
            onToggle={() => setIsSidebarOpen(false)}
            activeChatId={currentChatId}
            onSelectChat={(chatId) => {
              router.push(`/chat?chat_id=${chatId}`);
              setIsSidebarOpen(false);
            }}
            onNewChat={() => {
              // Clear saved chat ID when creating new chat
              try {
                localStorage.removeItem(ACTIVE_CHAT_KEY);
              } catch (e) {
                console.warn('Failed to clear chat ID from localStorage:', e);
              }
              router.push('/chat');
              setIsSidebarOpen(false);
            }}
          />
        )}

        {/* Messages Area - Adaptive width */}
        {/* pb динамический: больше когда показаны рекомендации, меньше когда скрыты */}
        <div
          className={`
          flex-1 overflow-hidden overflow-x-hidden transition-[padding] duration-300
          ${isDesktop
            ? 'max-w-[1200px] mx-auto w-full px-4 pb-28'
            : messages.length === INITIAL_MESSAGES.length && !isLoading
              ? 'pb-[140px]'
              : 'pb-[80px]'
          }
        `}
        >
          {isLoadingHistory ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                <p className="text-gray-400 text-sm">{t('chat.loading_chat')}</p>
              </div>
            </div>
          ) : (
            <MessageList
              messages={messages}
              isLoading={isLoading}
              onRegenerateMessage={handleRegenerateMessage}
            />
          )}
        </div>

        {/* Input Section - ChatGPT Style */}
        {/* Отступ снизу адаптируется: с TabBar или без него (когда клавиатура открыта) */}
        <div
          className={`
            fixed bottom-0 left-0 right-0 bg-gradient-to-t from-black via-black to-transparent pt-2
            transition-all duration-300 ease-in-out
          `}
          style={{
            paddingBottom: isDesktop
              ? '0.75rem'
              : isKeyboardVisible
                ? 'max(env(safe-area-inset-bottom), 0.5rem)'
                : 'calc(60px + max(env(safe-area-inset-bottom), 0.5rem))',
          }}
        >
          {/* Suggested Prompts */}
          <SuggestedPrompts
            onSelectPrompt={(prompt) => handleSendMessage(prompt, undefined, false)}
            show={messages.length === INITIAL_MESSAGES.length && !isLoading}
          />

          {/* Requests Counter - компактно между рекомендациями и инпутом */}
          {user?.subscription && (
            <div className="flex items-center justify-center gap-1.5 text-xs mb-1">
              {(user.subscription.requests_remaining ?? 0) > 0 ? (
                <>
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-sm shadow-blue-500/50" />
                  <span className="text-blue-400/80">
                    {user.subscription.requests_remaining} requests left
                  </span>
                </>
              ) : (
                <>
                  <div className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                  <span className="text-orange-400">Limit reached</span>
                </>
              )}
            </div>
          )}

          {/* Chat Input */}
          <ChatInput
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            signalsMode={signalsMode}
            onSignalsModeChange={setSignalsMode}
          />
        </div>

        {/* TabBar - отдельно, фиксированный внизу */}
        <TabBar />
      </div>

      {/* Premium Purchase Modal - shown on rate limit */}
      <PremiumPurchaseModal
        isOpen={showPremiumModal}
        onClose={() => setShowPremiumModal(false)}
        onSuccess={() => setShowPremiumModal(false)}
        referralDiscount={referralDiscount}
      />

      {/* Points Earn Animation */}
      <PointsEarnAnimation amount={pointsEarnAmount} trigger={pointsEarnTrigger} />
    </DesktopLayout>
  );
}
