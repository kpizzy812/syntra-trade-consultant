/**
 * Desktop Sidebar - ChatGPT-style interface
 * Collapsible sidebar with icon-only and expanded modes
 * Mobile: Overlay mode with slide animation
 */

'use client';

import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslations } from 'next-intl';
import { useUserStore } from '@/shared/store/userStore';
import { usePlatform } from '@/lib/platform';
import { api } from '@/shared/api/client';
import toast from 'react-hot-toast';
import Icon from '@/components/Icon';
import { CONTACTS } from '@/config/contacts';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

interface Chat {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface NavItem {
  key: string;
  icon: string;
  path?: string;
  onClick?: () => void;
}

export default function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const t = useTranslations();
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useUserStore();
  const { platform, platformType } = usePlatform();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const isDesktop = platformType === 'web';
  const [chats, setChats] = useState<Chat[]>([]);
  const [showAllChats, setShowAllChats] = useState(false);
  const [isLoadingChats, setIsLoadingChats] = useState(false);

  // Navigation items with translations
  const mainNavItems: NavItem[] = [
    { key: 'home', icon: 'grid', path: '/home' },
    { key: 'tasks', icon: 'check', path: '/tasks' },
    { key: 'referral', icon: 'user', path: '/referral' },
    { key: 'profile', icon: 'settings', path: '/profile' },
  ];

  // Load recent chats
  const loadRecentChats = async () => {
    try {
      setIsLoadingChats(true);
      const response = await api.chats.listChats(showAllChats ? 50 : 3, 0);
      setChats(response.chats || []);
    } catch (error) {
      console.error('Failed to load chats:', error);
    } finally {
      setIsLoadingChats(false);
    }
  };

  // Load chats when pathname is /chat
  useEffect(() => {
    if (pathname === '/chat') {
      loadRecentChats();
    }
  }, [pathname, showAllChats]);

  const handleNavigation = (path: string) => {
    platform?.ui.haptic?.impact('light');
    router.push(path);
    // Close sidebar on mobile after navigation
    if (onClose) onClose();
  };

  const handleNewChat = async () => {
    platform?.ui.haptic?.impact('medium');
    try {
      const newChat = await api.chats.createChat(t('sidebar.new_chat'));
      setChats([newChat, ...chats]);
      router.push(`/chat?chat_id=${newChat.id}`);
      toast.success(t('sidebar.new_chat_created'));
    } catch (error) {
      console.error('Failed to create chat:', error);
      toast.error(t('sidebar.failed_create'));
    }
  };

  const handleSelectChat = (chatId: number) => {
    platform?.ui.haptic?.impact('light');
    router.push(`/chat?chat_id=${chatId}`);
  };

  const handleDeleteChat = async (chatId: number, event: React.MouseEvent) => {
    event.stopPropagation();
    platform?.ui.haptic?.impact('heavy');

    if (!confirm(t('sidebar.delete_confirm'))) return;

    try {
      await api.chats.deleteChat(chatId);
      setChats(chats.filter((c) => c.id !== chatId));
      toast.success(t('sidebar.chat_deleted'));
    } catch (error) {
      console.error('Failed to delete chat:', error);
      toast.error(t('sidebar.failed_delete'));
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return t('sidebar.today');
    if (date.toDateString() === yesterday.toDateString()) return t('sidebar.yesterday');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Extract email username (before @)
  const getEmailUsername = () => {
    const email = user?.username || '';
    return email.split('@')[0] || email;
  };

  return (
    <aside
      className={`
        flex flex-col border-r border-white/5 bg-black/95 backdrop-blur-xl
        transition-all duration-300 ease-in-out
        ${isCollapsed ? 'w-[72px]' : 'w-[280px]'}

        // Desktop: always visible
        lg:relative lg:translate-x-0

        // Mobile: overlay mode
        fixed top-0 left-0 bottom-0 z-50 lg:z-auto
        ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}
    >
      {/* === HEADER: Logo + Toggle + Close (mobile) === */}
      <div className="flex items-center justify-between p-4 border-b border-white/5 min-h-[64px]">
        {!isCollapsed ? (
          <>
            {/* Logo + Title */}
            <div className="flex items-center gap-3 flex-1">
              <div className="relative">
                <Image
                  src="/syntra/logo.png"
                  width={32}
                  height={32}
                  alt="Syntra Logo"
                  className="rounded-lg"
                />
                <div className="absolute inset-0 rounded-lg bg-blue-500/20 blur-md -z-10" />
              </div>
              <div>
                <h1 className="text-sm font-bold text-white">Syntra AI</h1>
                <p className="text-[9px] text-gray-500 uppercase tracking-wider">
                  Crypto Analytics
                </p>
              </div>
            </div>

            {/* Close Button (Mobile) or Collapse (Desktop) */}
            <div className="flex items-center gap-2">
              {/* Mobile: Close button */}
              {onClose && (
                <motion.button
                  onClick={onClose}
                  className="lg:hidden p-2 rounded-lg hover:bg-white/5 transition-colors"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  title={t('sidebar.close')}
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
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </motion.button>
              )}

              {/* Desktop: Collapse button */}
              <motion.button
                onClick={() => setIsCollapsed(true)}
                className="hidden lg:block p-2 rounded-lg hover:bg-white/5 transition-colors"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                title={t('sidebar.collapse')}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-gray-400"
                >
                  <path d="M15 18l-6-6 6-6" />
                </svg>
              </motion.button>
            </div>
          </>
        ) : (
          /* Collapsed: Just logo */
          <div className="relative mx-auto">
            <Image
              src="/syntra/logo.png"
              width={32}
              height={32}
              alt="Syntra Logo"
              className="rounded-lg"
            />
            <div className="absolute inset-0 rounded-lg bg-blue-500/20 blur-md -z-10" />
          </div>
        )}
      </div>

      {/* === MAIN CONTENT === */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!isCollapsed ? (
          /* EXPANDED MODE */
          <>
            {/* New Chat Button */}
            <div className="p-3 border-b border-white/5">
              <motion.button
                onClick={handleNewChat}
                className="
                  w-full flex items-center justify-center gap-2 px-4 py-3
                  bg-gradient-to-r from-blue-600 to-blue-700
                  hover:from-blue-500 hover:to-blue-600
                  text-white text-sm font-medium rounded-xl
                  transition-all duration-200
                  border border-blue-500/20
                "
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <Icon name="plus" size={18} className="brightness-0 invert opacity-90" />
                <span>{t('sidebar.new_chat')}</span>
              </motion.button>
            </div>

            {/* Navigation Items */}
            <div className="px-3 py-4 space-y-1">
              {mainNavItems.map((item) => {
                const isActive = pathname === item.path;
                return (
                  <motion.button
                    key={item.key}
                    onClick={() => item.path && handleNavigation(item.path)}
                    className={`
                      group w-full flex items-center gap-3 px-3 py-2.5 rounded-xl
                      text-sm font-medium transition-all duration-200
                      ${
                        isActive
                          ? 'bg-white/10 text-white'
                          : 'text-gray-400 hover:text-white hover:bg-white/5'
                      }
                    `}
                    whileHover={{ x: 2 }}
                  >
                    <Icon
                      name={item.icon}
                      size={20}
                      className={`${isActive ? 'opacity-100 brightness-110' : 'opacity-80 group-hover:opacity-100'} [filter:invert(0.6)_sepia(1)_saturate(3)_hue-rotate(190deg)_brightness(1.1)]`}
                    />
                    <span>{t(`sidebar.nav.${item.key}`)}</span>
                  </motion.button>
                );
              })}
            </div>

            {/* Chats Section */}
            {pathname === '/chat' && (
              <div className="flex-1 overflow-y-auto px-3 py-2 border-t border-white/5">
                <div className="flex items-center gap-2 px-3 py-2 mb-2">
                  <Icon name="message" size={16} className="text-blue-400 [filter:invert(0.6)_sepia(1)_saturate(3)_hue-rotate(190deg)_brightness(1.1)]" />
                  <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    {t('sidebar.your_chats')}
                  </h3>
                </div>
                {isLoadingChats ? (
                  <div className="text-center py-4">
                    <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                  </div>
                ) : chats.length === 0 ? (
                  <div className="text-center py-4">
                    <p className="text-xs text-gray-500">{t('sidebar.no_chats')}</p>
                  </div>
                ) : (
                  <>
                    <div className="space-y-1">
                      {chats.map((chat) => (
                        <motion.button
                          key={chat.id}
                          onClick={() => handleSelectChat(chat.id)}
                          className="
                            group relative w-full text-left px-3 py-2 rounded-lg
                            hover:bg-white/5 transition-all duration-200
                          "
                          whileHover={{ x: 2 }}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm text-white truncate">
                                {chat.title}
                              </h4>
                              <p className="text-xs text-gray-500">
                                {formatDate(chat.updated_at)}
                              </p>
                            </div>
                            <button
                              onClick={(e) => handleDeleteChat(chat.id, e)}
                              className="
                                opacity-0 group-hover:opacity-100
                                p-1 rounded hover:bg-red-500/10 transition-all
                              "
                            >
                              <svg
                                width="12"
                                height="12"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                className="text-red-400"
                              >
                                <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                              </svg>
                            </button>
                          </div>
                        </motion.button>
                      ))}
                    </div>
                    {!showAllChats && chats.length >= 3 && (
                      <button
                        onClick={() => setShowAllChats(true)}
                        className="
                          w-full px-3 py-2 text-xs text-gray-500 hover:text-gray-400
                          hover:bg-white/5 rounded-lg transition-all mt-2
                        "
                      >
                        {t('sidebar.show_all_chats')}
                      </button>
                    )}
                  </>
                )}
              </div>
            )}
          </>
        ) : (
          /* COLLAPSED MODE - Icon only */
          <div className="flex-1 flex flex-col items-center py-4 space-y-2">
            {/* Expand Button */}
            <motion.button
              onClick={() => setIsCollapsed(false)}
              className="p-3 rounded-xl hover:bg-white/5 transition-colors"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              title={t('sidebar.expand')}
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
                <path d="M9 18l6-6-6-6" />
              </svg>
            </motion.button>

            {/* New Chat Icon */}
            <motion.button
              onClick={handleNewChat}
              className="p-3 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              title={t('sidebar.new_chat')}
            >
              <Icon name="plus" size={20} className="brightness-0 invert opacity-90" />
            </motion.button>

            <div className="w-full border-t border-white/5 my-2" />

            {/* Navigation Icons */}
            {mainNavItems.map((item) => {
              const isActive = pathname === item.path;
              return (
                <motion.button
                  key={item.key}
                  onClick={() => item.path && handleNavigation(item.path)}
                  className={`
                    p-3 rounded-xl transition-colors
                    ${
                      isActive
                        ? 'bg-white/10 text-white'
                        : 'text-gray-400 hover:text-white hover:bg-white/5'
                    }
                  `}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  title={t(`sidebar.nav.${item.key}`)}
                >
                  <Icon
                    name={item.icon}
                    size={20}
                    className={`${isActive ? 'opacity-100' : 'opacity-80'} [filter:invert(0.6)_sepia(1)_saturate(3)_hue-rotate(190deg)_brightness(1.1)]`}
                  />
                </motion.button>
              );
            })}
          </div>
        )}

        {/* Support Links (Expanded only) */}
        {!isCollapsed && (
          <div className="px-3 py-2 border-t border-white/5 mt-auto">
            <div className="flex items-center gap-2 px-3 py-2 mb-1">
              <span className="text-blue-400 text-xs">💬</span>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                {t('sidebar.support')}
              </h3>
            </div>
            <a
              href={CONTACTS.telegramUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-all"
            >
              <span>💬</span>
              <span>{CONTACTS.telegram}</span>
            </a>
            <a
              href={`mailto:${CONTACTS.email}`}
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-all"
            >
              <span>📧</span>
              <span className="truncate">{CONTACTS.email}</span>
            </a>
          </div>
        )}
      </div>

      {/* === USER PROFILE (Bottom) === */}
      {user && (
        <div className="p-3 border-t border-white/5">
          {!isCollapsed ? (
            /* Expanded: Full profile */
            <motion.button
              onClick={() => handleNavigation('/profile')}
              className="
                w-full flex items-center gap-3 p-3 rounded-xl
                hover:bg-white/5 transition-all duration-200
                border border-transparent hover:border-white/10
              "
              whileHover={{ scale: 1.02 }}
            >
              {/* Avatar */}
              <div className="relative w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0">
                <span className="text-white text-sm font-bold">
                  {getEmailUsername()[0]?.toUpperCase() || 'U'}
                </span>
              </div>

              {/* User Info */}
              <div className="flex-1 text-left min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {getEmailUsername()}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                      user.subscription?.tier === 'PREMIUM' ||
                      user.subscription?.tier === 'VIP'
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-blue-500/20 text-blue-400'
                    }`}
                  >
                    {user.subscription?.tier || 'FREE'}
                  </span>
                  <span className="text-[10px] text-gray-500">
                    {user.subscription?.requests_used_today || 0}/
                    {user.subscription?.daily_limit || 1}
                  </span>
                </div>
              </div>

              {/* Settings Icon */}
              <Icon name="settings" size={16} className="text-gray-500 flex-shrink-0 [filter:invert(0.6)_sepia(1)_saturate(3)_hue-rotate(190deg)_brightness(1.1)]" />
            </motion.button>
          ) : (
            /* Collapsed: Avatar only */
            <motion.button
              onClick={() => handleNavigation('/profile')}
              className="
                w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600
                flex items-center justify-center mx-auto
                hover:ring-2 hover:ring-blue-500/50 transition-all
              "
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              title={getEmailUsername()}
            >
              <span className="text-white text-sm font-bold">
                {getEmailUsername()[0]?.toUpperCase() || 'U'}
              </span>
            </motion.button>
          )}
        </div>
      )}
    </aside>
  );
}
