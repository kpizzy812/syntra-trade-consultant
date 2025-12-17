/**
 * Zustand Store для $SYNTRA Points
 */

'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface PointsBalance {
  balance: number;
  lifetime_earned: number;
  lifetime_spent: number;
  level: number;
  level_name_ru: string;
  level_name_en: string;
  level_icon: string;
  earning_multiplier: number;
  current_streak: number;
  longest_streak: number;
  next_level_points: number | null;
  progress_to_next_level: number;
}

export interface PointsTransaction {
  id: number;
  transaction_type: string;
  amount: number;
  balance_before: number;
  balance_after: number;
  description: string | null;
  created_at: string;
}

export interface PointsLevel {
  level: number;
  name_ru: string;
  name_en: string;
  icon: string;
  points_required: number;
  earning_multiplier: number;
  description_ru: string | null;
  description_en: string | null;
  color: string | null;
}

interface PointsStore {
  // State
  balance: PointsBalance | null;
  transactions: PointsTransaction[];
  levels: PointsLevel[];
  isLoading: boolean;
  error: string | null;

  // Actions
  setBalance: (balance: PointsBalance) => void;
  setTransactions: (transactions: PointsTransaction[]) => void;
  setLevels: (levels: PointsLevel[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearPoints: () => void;

  // Update balance incrementally (for real-time updates)
  updateBalance: (amount: number) => void;
}

export const usePointsStore = create<PointsStore>()(
  persist(
    (set) => ({
      // Initial state
      balance: null,
      transactions: [],
      levels: [],
      isLoading: false,
      error: null,

      // Set balance
      setBalance: (balance) =>
        set({
          balance,
          isLoading: false,
          error: null,
        }),

      // Set transactions
      setTransactions: (transactions) =>
        set({ transactions }),

      // Set levels
      setLevels: (levels) =>
        set({ levels }),

      // Set loading state
      setLoading: (loading) =>
        set({ isLoading: loading }),

      // Set error
      setError: (error) =>
        set({ error, isLoading: false }),

      // Clear all points data
      clearPoints: () =>
        set({
          balance: null,
          transactions: [],
          levels: [],
          isLoading: false,
          error: null,
        }),

      // Update balance incrementally (for optimistic UI updates)
      updateBalance: (amount) =>
        set((state) => {
          if (!state.balance) return state;

          const newBalance = state.balance.balance + amount;
          const newLifetimeEarned = amount > 0
            ? state.balance.lifetime_earned + amount
            : state.balance.lifetime_earned;
          const newLifetimeSpent = amount < 0
            ? state.balance.lifetime_spent + Math.abs(amount)
            : state.balance.lifetime_spent;

          return {
            balance: {
              ...state.balance,
              balance: newBalance,
              lifetime_earned: newLifetimeEarned,
              lifetime_spent: newLifetimeSpent,
            },
          };
        }),
    }),
    {
      name: 'syntra-points-storage',
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
