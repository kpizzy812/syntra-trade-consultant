/**
 * Zustand Store для управления состоянием пользователя
 */

'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Subscription } from '@/types/api';

interface User {
  id: number;
  telegram_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  language: 'en' | 'ru';
  is_premium: boolean;
  balance: number;
  subscription?: Subscription;
}

interface UserStore {
  // State
  user: User | null;
  isAuthenticated: boolean;
  initData: string | null;
  isLoading: boolean;

  // Actions
  setUser: (user: User) => void;
  setInitData: (initData: string) => void;
  setLoading: (loading: boolean) => void;
  clearUser: () => void;
  updateUser: (updates: Partial<User>) => void;
}

export const useUserStore = create<UserStore>()(
  persist(
    (set) => ({
      // Initial state
      user: null,
      isAuthenticated: false,
      initData: null,
      isLoading: false,

      // Set user and mark as authenticated
      setUser: (user) =>
        set({
          user,
          isAuthenticated: true,
          isLoading: false,
        }),

      // Store initData for API requests
      setInitData: (initData) =>
        set({ initData }),

      // Set loading state
      setLoading: (loading) =>
        set({ isLoading: loading }),

      // Clear user data (logout)
      clearUser: () =>
        set({
          user: null,
          isAuthenticated: false,
          initData: null,
          isLoading: false,
        }),

      // Update user data partially
      updateUser: (updates) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : null,
        })),
    }),
    {
      name: 'syntra-user-storage',
      storage: createJSONStorage(() => {
        // Используем localStorage только на клиенте
        if (typeof window !== 'undefined') {
          return window.localStorage;
        }
        // Fallback для SSR
        return {
          getItem: () => null,
          setItem: () => {},
          removeItem: () => {},
        };
      }),
    }
  )
);
