/**
 * ChatSidebar - Multiple Chats Management (ChatGPT-style)
 * Список чатов с возможностью переключения, переименования, удаления
 */

'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '@/shared/api/client';
import toast from 'react-hot-toast';
import { vibrate } from '@/shared/telegram/vibration';

interface Chat {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface ChatSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  activeChatId: number | null;
  onSelectChat: (chatId: number) => void;
  onNewChat: () => void;
}

export default function ChatSidebar({
  isOpen,
  onToggle,
  activeChatId,
  onSelectChat,
  onNewChat,
}: ChatSidebarProps) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [editingChatId, setEditingChatId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');

  // Load chats list
  const loadChats = async () => {
    try {
      setIsLoading(true);
      const response = await api.chats.listChats(50, 0);
      setChats(response.chats || []);
    } catch (error) {
      console.error('Failed to load chats:', error);
      toast.error('Failed to load chats');
    } finally {
      setIsLoading(false);
    }
  };

  // Load chats on mount
  useEffect(() => {
    if (isOpen) {
      loadChats();
    }
  }, [isOpen]);

  // Listen for refreshChatList event (from signals mode when new chat created)
  useEffect(() => {
    const handleRefresh = () => {
      loadChats();
    };
    window.addEventListener('refreshChatList', handleRefresh);
    return () => window.removeEventListener('refreshChatList', handleRefresh);
  }, []);

  // Handle chat selection
  const handleSelectChat = (chatId: number) => {
    vibrate('light');
    onSelectChat(chatId);
  };

  // Handle new chat
  const handleNewChat = async () => {
    vibrate('medium');
    try {
      const newChat = await api.chats.createChat('New Chat');
      setChats([newChat, ...chats]);
      onNewChat();
      onSelectChat(newChat.id);
      toast.success('New chat created');
    } catch (error) {
      console.error('Failed to create chat:', error);
      toast.error('Failed to create chat');
    }
  };

  // Handle delete chat
  const handleDeleteChat = async (chatId: number, event: React.MouseEvent) => {
    event.stopPropagation();
    vibrate('heavy');

    if (!confirm('Delete this chat? This action cannot be undone.')) {
      return;
    }

    try {
      await api.chats.deleteChat(chatId);
      setChats(chats.filter((c) => c.id !== chatId));

      // If deleted chat was active, select another or create new
      if (activeChatId === chatId) {
        const remainingChats = chats.filter((c) => c.id !== chatId);
        if (remainingChats.length > 0) {
          onSelectChat(remainingChats[0].id);
        } else {
          onNewChat();
        }
      }

      toast.success('Chat deleted');
    } catch (error) {
      console.error('Failed to delete chat:', error);
      toast.error('Failed to delete chat');
    }
  };

  // Start editing chat title
  const handleStartEdit = (chat: Chat, event: React.MouseEvent) => {
    event.stopPropagation();
    setEditingChatId(chat.id);
    setEditTitle(chat.title);
  };

  // Save edited title
  const handleSaveEdit = async (chatId: number) => {
    if (!editTitle.trim()) {
      setEditingChatId(null);
      return;
    }

    try {
      await api.chats.renameChat(chatId, editTitle.trim());
      setChats(
        chats.map((c) =>
          c.id === chatId ? { ...c, title: editTitle.trim() } : c
        )
      );
      setEditingChatId(null);
      toast.success('Chat renamed');
    } catch (error) {
      console.error('Failed to rename chat:', error);
      toast.error('Failed to rename chat');
    }
  };

  // Cancel editing
  const handleCancelEdit = () => {
    setEditingChatId(null);
    setEditTitle('');
  };

  // Format date (Today, Yesterday, or date)
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return 'Today';
    }
    if (date.toDateString() === yesterday.toDateString()) {
      return 'Yesterday';
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <>
      {/* Overlay (mobile) */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={{ x: -320 }}
        animate={{ x: isOpen ? 0 : -320 }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className={`
          fixed top-0 left-0 h-full w-80 z-50
          bg-black/95 backdrop-blur-xl border-r border-white/10
          flex flex-col
          lg:relative lg:z-auto
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <h2 className="text-lg font-semibold text-white">Chats</h2>
          <button
            onClick={onToggle}
            className="p-2 rounded-lg hover:bg-white/5 transition-colors lg:hidden"
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
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <motion.button
            onClick={handleNewChat}
            className="
              w-full flex items-center justify-center gap-2 px-4 py-3
              bg-gradient-to-r from-blue-600 to-blue-700
              hover:from-blue-500 hover:to-blue-600
              text-white font-medium rounded-xl
              transition-all duration-200
              border border-blue-500/30
            "
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
            <span>New Chat</span>
          </motion.button>
        </div>

        {/* Chats List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {isLoading ? (
            <div className="text-center py-8">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p className="text-gray-500 text-sm mt-2">Loading chats...</p>
            </div>
          ) : chats.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500 text-sm">No chats yet</p>
              <p className="text-gray-600 text-xs mt-1">
                Click "New Chat" to start
              </p>
            </div>
          ) : (
            chats.map((chat) => {
              const isActive = activeChatId === chat.id;
              const isEditing = editingChatId === chat.id;

              return (
                <motion.div
                  key={chat.id}
                  onClick={() => !isEditing && handleSelectChat(chat.id)}
                  className={`
                    group relative px-3 py-2.5 rounded-lg cursor-pointer
                    transition-all duration-200
                    ${
                      isActive
                        ? 'bg-gradient-to-r from-blue-500/20 to-blue-600/10 border border-blue-500/30'
                        : 'hover:bg-white/5 border border-transparent'
                    }
                  `}
                  whileHover={{ x: 4 }}
                >
                  {isEditing ? (
                    // Edit mode
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            handleSaveEdit(chat.id);
                          } else if (e.key === 'Escape') {
                            handleCancelEdit();
                          }
                        }}
                        className="
                          flex-1 px-2 py-1 bg-white/5 border border-white/10
                          rounded text-sm text-white
                          focus:outline-none focus:border-blue-500/50
                        "
                        autoFocus
                      />
                      <button
                        onClick={() => handleSaveEdit(chat.id)}
                        className="p-1 text-green-400 hover:text-green-300"
                      >
                        ✓
                      </button>
                      <button
                        onClick={handleCancelEdit}
                        className="p-1 text-red-400 hover:text-red-300"
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    <>
                      {/* Chat info */}
                      <div className="flex-1 min-w-0">
                        <h3
                          className={`
                            text-sm font-medium truncate
                            ${isActive ? 'text-blue-400' : 'text-white'}
                          `}
                        >
                          {chat.title}
                        </h3>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-gray-500">
                            {formatDate(chat.updated_at)}
                          </span>
                          {chat.message_count > 0 && (
                            <>
                              <span className="text-gray-600">•</span>
                              <span className="text-xs text-gray-500">
                                {chat.message_count} messages
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Actions (show on hover) */}
                      <div
                        className={`
                          absolute right-2 top-1/2 -translate-y-1/2
                          flex items-center gap-1
                          opacity-0 group-hover:opacity-100 transition-opacity
                        `}
                      >
                        <button
                          onClick={(e) => handleStartEdit(chat, e)}
                          className="p-1.5 rounded hover:bg-white/10 transition-colors"
                          title="Rename"
                        >
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            className="text-gray-400"
                          >
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                          </svg>
                        </button>
                        <button
                          onClick={(e) => handleDeleteChat(chat.id, e)}
                          className="p-1.5 rounded hover:bg-red-500/10 transition-colors"
                          title="Delete"
                        >
                          <svg
                            width="14"
                            height="14"
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
                    </>
                  )}
                </motion.div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span>{chats.length} chats</span>
          </div>
        </div>
      </motion.aside>
    </>
  );
}
