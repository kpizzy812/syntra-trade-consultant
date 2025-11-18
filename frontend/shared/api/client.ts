/**
 * API Client для взаимодействия с backend
 */

'use client';

import axios, { AxiosInstance, AxiosError } from 'axios';
import { useUserStore } from '@/shared/store/userStore';

// API URL из переменных окружения
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Создание axios instance с дефолтными настройками
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_URL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor - добавляем Telegram initData в Authorization header
  client.interceptors.request.use(
    (config) => {
      const initData = useUserStore.getState().initData;
      if (initData && config.headers) {
        config.headers.Authorization = `tma ${initData}`;
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor - обработка ошибок
  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      if (error.response) {
        // Сервер ответил с ошибкой
        console.error('API Error:', error.response.status, error.response.data);

        // 401 - невалидная авторизация
        if (error.response.status === 401) {
          useUserStore.getState().clearUser();
        }
      } else if (error.request) {
        // Запрос был отправлен, но ответа нет
        console.error('Network Error:', error.message);
      } else {
        console.error('Request Error:', error.message);
      }

      return Promise.reject(error);
    }
  );

  return client;
};

// Экспортируем singleton instance
export const apiClient = createApiClient();

// Типизированные методы API
export const api = {
  /**
   * Авторизация через Telegram initData
   */
  auth: {
    telegram: async (initData: string) => {
      const response = await axios.post(
        `${API_URL}/api/auth/telegram`,
        {},
        {
          headers: {
            Authorization: `tma ${initData}`,
          },
        }
      );
      return response.data;
    },
  },

  /**
   * User API
   */
  user: {
    getProfile: async () => {
      const response = await apiClient.get('/api/user/profile');
      return response.data;
    },
    updateProfile: async (data: any) => {
      const response = await apiClient.patch('/api/user/profile', data);
      return response.data;
    },
  },

  /**
   * Analytics API
   */
  analytics: {
    getSymbol: async (symbol: string) => {
      const response = await apiClient.get(`/api/analytics/${symbol}`);
      return response.data;
    },
    getMarketOverview: async () => {
      const response = await apiClient.get('/api/analytics/market');
      return response.data;
    },
  },

  /**
   * Chat API
   */
  chat: {
    sendMessage: async (message: string, context?: string) => {
      const response = await apiClient.post('/api/chat', {
        message,
        context,
      });
      return response.data;
    },
    streamMessage: async (
      message: string,
      onToken: (token: string) => void,
      onError?: (error: string) => void,
      onDone?: () => void
    ) => {
      const initData = useUserStore.getState().initData;
      if (!initData) {
        throw new Error('No init data available');
      }

      const url = `${API_URL}/api/chat/stream`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `tma ${initData}`,
        },
        body: JSON.stringify({ message, context: null }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'token') {
                onToken(data.content);
              } else if (data.type === 'error') {
                onError?.(data.error);
              } else if (data.type === 'done') {
                onDone?.();
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    },
    getHistory: async (limit: number = 50) => {
      const response = await apiClient.get('/api/chat/history', {
        params: { limit },
      });
      return response.data;
    },
    regenerateMessage: async (
      messageId: number,
      onToken: (token: string) => void,
      onError?: (error: string) => void,
      onDone?: () => void
    ) => {
      const initData = useUserStore.getState().initData;
      if (!initData) {
        throw new Error('No init data available');
      }

      const url = `${API_URL}/api/chat/regenerate`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `tma ${initData}`,
        },
        body: JSON.stringify({ message_id: messageId }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP error! status: ${response.status}`
        );
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'token') {
                onToken(data.content);
              } else if (data.type === 'error') {
                onError?.(data.error);
              } else if (data.type === 'done') {
                onDone?.();
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    },
  },

  /**
   * Referral API
   */
  referral: {
    getStats: async () => {
      const response = await apiClient.get('/api/referral/stats');
      return response.data;
    },
    getLink: async () => {
      const response = await apiClient.get('/api/referral/link');
      return response.data;
    },
    getHistory: async (limit: number = 50) => {
      const response = await apiClient.get('/api/referral/history', {
        params: { limit },
      });
      return response.data;
    },
  },

  /**
   * Market API
   */
  market: {
    getFearGreedIndex: async () => {
      const response = await apiClient.get('/api/market/fear-greed');
      return response.data;
    },
    getWatchlist: async () => {
      const response = await apiClient.get('/api/market/watchlist');
      return response.data;
    },
    getTopMovers: async () => {
      const response = await apiClient.get('/api/market/top-movers');
      return response.data;
    },
    addToWatchlist: async (symbol: string) => {
      const response = await apiClient.post('/api/market/watchlist/add', {
        symbol,
      });
      return response.data;
    },
    removeFromWatchlist: async (symbol: string) => {
      const response = await apiClient.delete('/api/market/watchlist/remove', {
        params: { symbol },
      });
      return response.data;
    },
  },

  /**
   * Profile API
   */
  profile: {
    /**
     * Get complete user profile information
     */
    getProfile: async () => {
      const response = await apiClient.get('/api/profile');
      return response.data;
    },

    /**
     * Update user settings (language)
     */
    updateSettings: async (settings: { language?: string }) => {
      const response = await apiClient.patch('/api/profile/settings', settings);
      return response.data;
    },

    /**
     * Get detailed subscription information
     */
    getSubscription: async () => {
      const response = await apiClient.get('/api/profile/subscription');
      return response.data;
    },
  },

  /**
   * Payment API
   */
  payment: {
    /**
     * Create Telegram Stars invoice for subscription
     */
    createStarsInvoice: async (params: {
      tier: string;
      duration_months: number;
    }) => {
      const response = await apiClient.post('/api/payment/stars/create-invoice', params);
      return response.data;
    },

    /**
     * Create TON Connect payment request (TON or USDT)
     */
    createTonPayment: async (params: {
      tier: string;
      duration_months: number;
      currency: 'ton' | 'usdt';
    }) => {
      const response = await apiClient.post('/api/payment/ton/create-payment', params);
      return response.data;
    },

    /**
     * Get payment status (for polling after TON/USDT send)
     *
     * Used to check if blockchain transaction was processed.
     * Call this after sending TON/USDT via TON Connect.
     */
    getPaymentStatus: async (paymentId: number) => {
      const response = await apiClient.get(`/api/payment/status/${paymentId}`);
      return response.data;
    },

    /**
     * Verify payment status
     */
    verifyPayment: async (paymentId: string) => {
      const response = await apiClient.get(`/api/payment/verify/${paymentId}`);
      return response.data;
    },

    /**
     * Get payment history
     */
    getPaymentHistory: async (limit: number = 50) => {
      const response = await apiClient.get('/api/payment/history', {
        params: { limit },
      });
      return response.data;
    },
  },
};

export default apiClient;
