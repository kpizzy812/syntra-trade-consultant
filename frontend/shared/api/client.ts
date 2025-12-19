/**
 * API Client для взаимодействия с backend
 * Updated to use Platform Abstraction Layer
 */

'use client';

import axios, { AxiosInstance, AxiosError } from 'axios';
import { useUserStore } from '@/shared/store/userStore';
import { getPlatformCredentials } from '@/lib/platform/apiHelper';

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

  // Request interceptor - добавляем platform-specific авторизацию
  client.interceptors.request.use(
    async (config) => {
      // Try Platform credentials first (новый подход)
      const credentials = await getPlatformCredentials();

      if (credentials && config.headers) {
        // Telegram
        if (credentials.telegram_initData) {
          config.headers.Authorization = `tma ${credentials.telegram_initData}`;
        }
        // Web (NextAuth JWT token)
        else if (credentials.auth_token) {
          config.headers.Authorization = `Bearer ${credentials.auth_token}`;
        }
      }
      // Fallback to direct localStorage check for web auth (CRITICAL FIX)
      else if (typeof window !== 'undefined') {
        // Check for JWT token in localStorage (magic link auth)
        const authToken = localStorage.getItem('auth_token');
        if (authToken && config.headers) {
          config.headers.Authorization = `Bearer ${authToken}`;
        }
        // Check for Telegram initData (legacy)
        else {
          const initData = useUserStore.getState().initData;
          if (initData && config.headers) {
            config.headers.Authorization = `tma ${initData}`;
          }
        }
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
   * Авторизация через Telegram initData и Magic Link
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

    /**
     * Request magic link for email
     */
    requestMagicLink: async (email: string, language: string = 'en') => {
      const response = await axios.post(
        `${API_URL}/api/auth/magic/request`,
        { email, language }
      );
      return response.data;
    },

    /**
     * Verify magic link token
     */
    verifyMagicLink: async (token: string) => {
      const response = await axios.get(
        `${API_URL}/api/auth/magic/verify`,
        { params: { token } }
      );
      return response.data;
    },

    /**
     * Check if email exists
     */
    checkEmail: async (email: string) => {
      const response = await axios.get(
        `${API_URL}/api/auth/magic/check-email`,
        { params: { email } }
      );
      return response.data;
    },

    /**
     * Validate JWT token by attempting to get user profile
     * Returns user data if token is valid, throws error if invalid
     */
    validateToken: async () => {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No auth token found');
      }

      const response = await axios.get(
        `${API_URL}/api/user/profile`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
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
    sendMessage: async (message: string, context?: string, chatId?: number) => {
      const response = await apiClient.post('/api/chat', {
        message,
        context,
        chat_id: chatId,
      });
      return response.data;
    },
    streamMessage: async (
      message: string,
      onToken: (token: string) => void,
      onError?: (error: string) => void,
      onDone?: (chatId?: number) => void,
      image?: string,
      chatId?: number
    ) => {
      // Get platform-specific credentials
      const credentials = await getPlatformCredentials();

      // Determine authorization header
      let authHeader = '';
      if (credentials?.telegram_initData) {
        authHeader = `tma ${credentials.telegram_initData}`;
      } else if (credentials?.auth_token) {
        authHeader = `Bearer ${credentials.auth_token}`;
      } else if (typeof window !== 'undefined') {
        // Fallback: check localStorage
        const authToken = localStorage.getItem('auth_token');
        if (authToken) {
          authHeader = `Bearer ${authToken}`;
        } else {
          // Legacy: check Telegram initData in store
          const initData = useUserStore.getState().initData;
          if (initData) {
            authHeader = `tma ${initData}`;
          }
        }
      }

      if (!authHeader) {
        throw new Error('No authentication credentials available');
      }

      const url = `${API_URL}/api/chat/stream`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authHeader,
        },
        body: JSON.stringify({ message, context: null, image, chat_id: chatId }),
      });

      if (!response.ok) {
        // Parse error response for rate limit info
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(
          errorData.message || `HTTP error! status: ${response.status}`
        ) as Error & {
          status?: number;
          errorCode?: string;
          showUpgrade?: boolean;
          resetHours?: number;
        };
        error.status = response.status;
        error.errorCode = errorData.error_code;
        error.showUpgrade = errorData.show_upgrade;
        error.resetHours = errorData.reset_hours;
        throw error;
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
                // Pass chat_id from backend to frontend
                onDone?.(data.chat_id);
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
      // Get platform-specific credentials
      const credentials = await getPlatformCredentials();

      // Determine authorization header
      let authHeader = '';
      if (credentials?.telegram_initData) {
        authHeader = `tma ${credentials.telegram_initData}`;
      } else if (credentials?.auth_token) {
        authHeader = `Bearer ${credentials.auth_token}`;
      } else if (typeof window !== 'undefined') {
        // Fallback: check localStorage
        const authToken = localStorage.getItem('auth_token');
        if (authToken) {
          authHeader = `Bearer ${authToken}`;
        } else {
          // Legacy: check Telegram initData in store
          const initData = useUserStore.getState().initData;
          if (initData) {
            authHeader = `tma ${initData}`;
          }
        }
      }

      if (!authHeader) {
        throw new Error('No authentication credentials available');
      }

      const url = `${API_URL}/api/chat/regenerate`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authHeader,
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
    /**
     * Get comprehensive market overview (Fear & Greed + Global Market Data)
     */
    getOverview: async () => {
      const response = await apiClient.get('/api/market/overview');
      return response.data;
    },

    /**
     * Get Fear & Greed Index only
     */
    getFearGreedIndex: async () => {
      const response = await apiClient.get('/api/market/fear-greed');
      return response.data;
    },

    /**
     * Get watchlist with current prices
     */
    getWatchlist: async () => {
      const response = await apiClient.get('/api/market/watchlist');
      return response.data;
    },

    /**
     * Get top gainers and losers by timeframe
     * @param timeframe - "1h", "24h", or "7d"
     * @param limit - Number of gainers/losers (default: 3, max: 20)
     */
    getTopMovers: async (timeframe: '1h' | '24h' | '7d' = '24h', limit: number = 3) => {
      const response = await apiClient.get('/api/market/top-movers', {
        params: { timeframe, limit },
      });
      return response.data;
    },

    /**
     * Add coin to watchlist
     */
    addToWatchlist: async (coinId: string, symbol: string, name: string) => {
      const response = await apiClient.post('/api/market/watchlist/add', {
        coin_id: coinId,
        symbol,
        name,
      });
      return response.data;
    },

    /**
     * Remove coin from watchlist
     */
    removeFromWatchlist: async (coinId: string) => {
      const response = await apiClient.delete('/api/market/watchlist/remove', {
        params: { coin_id: coinId },
      });
      return response.data;
    },

    /**
     * Get detailed coin information by symbol
     * @param symbol - Cryptocurrency symbol (e.g., "BTC", "ETH")
     */
    getCoinDetails: async (symbol: string) => {
      const response = await apiClient.get(`/api/market/coin/${symbol}`);
      return response.data;
    },

    /**
     * Get historical price chart data for a coin
     * @param symbol - Cryptocurrency symbol (e.g., "BTC", "ETH")
     * @param days - Number of days of data (1, 7, 30, 90, 365)
     */
    getCoinChart: async (symbol: string, days: number = 7) => {
      const response = await apiClient.get(`/api/market/chart/${symbol}`, {
        params: { days },
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

  /**
   * CryptoPay API (CryptoBot payments)
   */
  cryptoPay: {
    /**
     * Get supported cryptocurrencies
     */
    getAssets: async () => {
      const response = await apiClient.get('/api/cryptopay/assets');
      return response.data;
    },

    /**
     * Create CryptoBot invoice for subscription payment
     */
    createInvoice: async (params: {
      tier: string;
      duration_months: number;
      asset: string;  // USDT, TON, BTC, ETH, etc.
    }) => {
      const response = await apiClient.post('/api/cryptopay/invoice', params);
      return response.data;
    },

    /**
     * Check invoice status (for polling)
     */
    getInvoiceStatus: async (invoiceId: number) => {
      const response = await apiClient.get(`/api/cryptopay/invoice/${invoiceId}`);
      return response.data;
    },

    /**
     * Cancel unpaid invoice
     */
    cancelInvoice: async (invoiceId: number) => {
      const response = await apiClient.delete(`/api/cryptopay/invoice/${invoiceId}`);
      return response.data;
    },

    /**
     * Get user's CryptoBot invoices history
     */
    getInvoices: async (status?: string, limit: number = 50) => {
      const response = await apiClient.get('/api/cryptopay/invoices', {
        params: { status, limit },
      });
      return response.data;
    },
  },

  /**
   * NOWPayments API (300+ cryptocurrencies)
   */
  nowPayments: {
    /**
     * Create NOWPayments invoice for subscription payment
     * User can choose from 300+ cryptocurrencies on payment page
     */
    createInvoice: async (params: {
      tier: string;
      duration_months: number;
      pay_currency?: string;  // Optional: pre-select currency (btc, eth, usdt, etc.)
    }) => {
      const response = await apiClient.post('/api/payment/nowpayments/create-invoice', params);
      return response.data;
    },

    /**
     * Check payment status (through main payment API)
     */
    getPaymentStatus: async (paymentId: number) => {
      const response = await apiClient.get(`/api/payment/status/${paymentId}`);
      return response.data;
    },
  },

  /**
   * Config API (Public endpoints)
   */
  config: {
    /**
     * Get current pricing configuration
     */
    getPricing: async () => {
      const response = await axios.get(`${API_URL}/api/config/pricing`);
      return response.data;
    },

    /**
     * Get available features
     */
    getFeatures: async () => {
      const response = await axios.get(`${API_URL}/api/config/features`);
      return response.data;
    },
  },

  /**
   * Chats API (Multiple chats management like ChatGPT)
   */
  chats: {
    /**
     * Get list of user's chats (sorted by last update)
     */
    listChats: async (limit: number = 50, offset: number = 0) => {
      const response = await apiClient.get('/api/chats', {
        params: { limit, offset },
      });
      return response.data;
    },

    /**
     * Create a new chat
     */
    createChat: async (title: string = 'New Chat') => {
      const response = await apiClient.post('/api/chats', { title });
      return response.data;
    },

    /**
     * Get specific chat by ID
     */
    getChat: async (chatId: number) => {
      const response = await apiClient.get(`/api/chats/${chatId}`);
      return response.data;
    },

    /**
     * Get messages from specific chat
     */
    getChatMessages: async (chatId: number, limit?: number) => {
      const response = await apiClient.get(`/api/chats/${chatId}/messages`, {
        params: limit ? { limit } : {},
      });
      return response.data;
    },

    /**
     * Rename chat
     */
    renameChat: async (chatId: number, title: string) => {
      const response = await apiClient.put(`/api/chats/${chatId}/title`, { title });
      return response.data;
    },

    /**
     * Delete chat
     */
    deleteChat: async (chatId: number) => {
      const response = await apiClient.delete(`/api/chats/${chatId}`);
      return response.data;
    },

    /**
     * Get or create default chat (most recent or new one)
     */
    getDefaultChat: async () => {
      const response = await apiClient.get('/api/chats/default/active');
      return response.data;
    },
  },

  /**
   * $SYNTRA Points API
   */
  points: {
    /**
     * Get user's points balance and level
     */
    getBalance: async () => {
      const response = await apiClient.get('/api/points/balance');
      return response.data;
    },

    /**
     * Get transaction history
     */
    getHistory: async (limit: number = 50, offset: number = 0) => {
      const response = await apiClient.get('/api/points/history', {
        params: { limit, offset },
      });
      return response.data;
    },

    /**
     * Get leaderboard (top users by points balance)
     */
    getLeaderboard: async (limit: number = 50) => {
      const response = await apiClient.get('/api/points/leaderboard', {
        params: { limit },
      });
      return response.data;
    },

    /**
     * Get all available levels
     */
    getLevels: async () => {
      const response = await apiClient.get('/api/points/levels');
      return response.data;
    },

    /**
     * Get detailed earning statistics
     */
    getStats: async () => {
      const response = await apiClient.get('/api/points/stats');
      return response.data;
    },
  },

  /**
   * Futures Signals API (Premium/VIP only)
   */
  futuresSignals: {
    /**
     * Analyze request and generate trading scenarios
     * Returns scenarios if sufficient data, or clarifying questions if not
     */
    analyze: async (params: {
      message: string;
      ticker?: string;
      timeframe?: string;
      mode?: 'conservative' | 'standard' | 'high_risk' | 'meme';
      language?: string;
      chat_id?: number;
    }) => {
      const response = await apiClient.post('/api/futures-signals/analyze', params);
      return response.data;
    },

    /**
     * Get current user's futures signals limits
     */
    getLimits: async () => {
      const response = await apiClient.get('/api/futures-signals/limits');
      return response.data;
    },

    /**
     * Validate request without generating (preview mode)
     * Does NOT check or decrement limits
     */
    validate: async (params: {
      message: string;
      language?: string;
    }) => {
      const response = await apiClient.post('/api/futures-signals/validate', params);
      return response.data;
    },
  },

  /**
   * Social Tasks API (Earn points by completing tasks)
   */
  tasks: {
    /**
     * Get available tasks for user
     */
    getAvailable: async (includeCompleted: boolean = false) => {
      const response = await apiClient.get('/api/tasks/available', {
        params: { include_completed: includeCompleted },
      });
      return response.data;
    },

    /**
     * Start a task
     */
    startTask: async (taskId: number) => {
      const response = await apiClient.post(`/api/tasks/${taskId}/start`);
      return response.data;
    },

    /**
     * Verify task completion
     */
    verifyTask: async (taskId: number) => {
      const response = await apiClient.post(`/api/tasks/${taskId}/verify`);
      return response.data;
    },

    /**
     * Submit screenshot for manual verification (Twitter tasks)
     */
    submitScreenshot: async (taskId: number, imageBase64: string) => {
      const response = await apiClient.post(`/api/tasks/${taskId}/screenshot`, {
        image_base64: imageBase64,
      });
      return response.data;
    },

    /**
     * Get task completion history
     */
    getHistory: async (limit: number = 50) => {
      const response = await apiClient.get('/api/tasks/history', {
        params: { limit },
      });
      return response.data;
    },
  },
};

export default apiClient;
