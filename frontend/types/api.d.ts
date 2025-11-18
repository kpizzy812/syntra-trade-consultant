/**
 * API TypeScript Definitions для Syntra Trade Consultant
 */

// ============= User Types =============

export interface User {
  id: number;
  telegram_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  language: 'en' | 'ru';
  is_premium: boolean;
  balance: number;
  created_at: string;
  referral_code?: string;
}

export interface UserProfile extends User {
  total_trades: number;
  win_rate: number;
  total_profit: number;
  subscription?: Subscription;
}

// ============= Subscription Types =============

export interface Subscription {
  id: number;
  user_id: number;
  tier: 'FREE' | 'BASIC' | 'PREMIUM' | 'VIP';
  plan?: 'basic' | 'premium' | 'pro';
  status: 'active' | 'inactive' | 'expired';
  start_date: string;
  end_date: string;
  auto_renew: boolean;
  daily_limit: number;
  requests_used_today: number;
  requests_remaining: number;
}

// ============= Analytics Types =============

export interface AnalyticsData {
  symbol: string;
  price: number;
  change_24h: number;
  change_7d: number;
  volume_24h: number;
  market_cap: number;
  indicators: TechnicalIndicators;
  signals?: TradingSignals;
}

export interface TechnicalIndicators {
  rsi?: number;
  macd?: MACDIndicator;
  bollinger_bands?: BollingerBands;
  moving_averages?: MovingAverages;
  volume_profile?: VolumeProfile;
}

export interface MACDIndicator {
  macd: number;
  signal: number;
  histogram: number;
}

export interface BollingerBands {
  upper: number;
  middle: number;
  lower: number;
}

export interface MovingAverages {
  sma_20: number;
  sma_50: number;
  sma_200: number;
  ema_12: number;
  ema_26: number;
}

export interface VolumeProfile {
  volume_24h: number;
  volume_change: number;
  buy_volume: number;
  sell_volume: number;
}

export interface TradingSignals {
  overall: 'bullish' | 'bearish' | 'neutral';
  strength: number; // 0-100
  recommendation: 'strong_buy' | 'buy' | 'hold' | 'sell' | 'strong_sell';
  confidence: number; // 0-100
}

// ============= Chat Types =============

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  analytics?: AnalyticsData;
  images?: string[];
}

export interface ChatRequest {
  message: string;
  context?: string;
  include_analytics?: boolean;
}

export interface ChatResponse {
  message: string;
  analytics?: AnalyticsData;
  suggestions?: string[];
}

// ============= Market Data Types =============

export interface MarketData {
  symbol: string;
  name: string;
  price: number;
  change_24h: number;
  volume_24h: number;
  market_cap: number;
  rank: number;
  logo_url?: string;
}

export interface PriceHistory {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ============= Referral Types =============

export interface ReferralInfo {
  code: string;
  total_referrals: number;
  active_referrals: number;
  total_earnings: number;
  referrals: ReferralUser[];
}

export interface ReferralUser {
  user_id: number;
  username?: string;
  first_name: string;
  registered_at: string;
  is_premium: boolean;
  earnings: number;
}

// ============= API Response Types =============

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

// ============= Error Types =============

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

// ============= Request Types =============

export interface AuthRequest {
  init_data: string;
}

export interface UpdateProfileRequest {
  language?: 'en' | 'ru';
  notifications_enabled?: boolean;
}
