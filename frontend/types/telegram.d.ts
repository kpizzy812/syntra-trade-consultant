/**
 * Telegram WebApp TypeScript Definitions
 * Based on official Telegram Mini Apps API 2025
 */

/**
 * Invoice payment status
 * - paid: Transaction completed successfully
 * - cancelled: User closed invoice without paying
 * - failed: Payment attempt unsuccessful
 * - pending: Payment still processing
 */
export type InvoiceStatus = 'paid' | 'cancelled' | 'failed' | 'pending';

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: WebAppInitData;
  version: string;
  platform: string;
  colorScheme: 'light' | 'dark';
  themeParams: ThemeParams;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  headerColor: string;
  backgroundColor: string;
  isClosingConfirmationEnabled: boolean;
  isFullscreen: boolean;

  // Methods
  ready(): void;
  expand(): void;
  close(): void;
  enableClosingConfirmation(): void;
  disableClosingConfirmation(): void;
  disableVerticalSwipes(): void;
  requestFullscreen(): void;
  exitFullscreen(): void;
  setHeaderColor(color: string): void;
  setBackgroundColor(color: string): void;

  /**
   * Open invoice for payment
   * @param url Invoice URL (from createInvoiceLink)
   * @param callback Optional callback receiving payment status: "paid" | "cancelled" | "failed" | "pending"
   */
  openInvoice(url: string, callback?: (status: InvoiceStatus) => void): void;

  /**
   * Open a Telegram link (t.me/...) within Telegram
   * Use for opening bot links, channel links, etc.
   * @param url Telegram URL (must start with https://t.me/)
   */
  openTelegramLink(url: string): void;

  /**
   * Open an external URL
   * @param url External URL to open
   * @param options Optional settings (try_instant_view)
   */
  openLink(url: string, options?: { try_instant_view?: boolean }): void;

  /**
   * Request permission for the bot to send messages to the user
   * Shows a native popup asking for user consent
   * @param callback Optional callback called when popup closes. First argument is boolean indicating if user granted access.
   *
   * Available since: Bot API 6.9+
   *
   * Example:
   * ```ts
   * WebApp.requestWriteAccess((granted) => {
   *   if (granted) {
   *     console.log('User granted write access');
   *   } else {
   *     console.log('User denied write access');
   *   }
   * });
   * ```
   */
  requestWriteAccess(callback?: (granted: boolean) => void): void;

  // Events
  onEvent(eventType: string, callback: () => void): void;
  offEvent(eventType: string, callback: () => void): void;

  // Components
  MainButton: MainButton;
  BackButton: BackButton;
  HapticFeedback: HapticFeedback;
  CloudStorage: CloudStorage;
}

export interface WebAppInitData {
  query_id?: string;
  user?: WebAppUser;
  receiver?: WebAppUser;
  chat?: WebAppChat;
  chat_type?: string;
  chat_instance?: string;
  start_param?: string;
  can_send_after?: number;
  auth_date: number;
  hash: string;
}

export interface WebAppUser {
  id: number;
  is_bot?: boolean;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
  added_to_attachment_menu?: boolean;
  allows_write_to_pm?: boolean;
  photo_url?: string;
}

export interface WebAppChat {
  id: number;
  type: 'group' | 'supergroup' | 'channel';
  title: string;
  username?: string;
  photo_url?: string;
}

export interface MainButton {
  text: string;
  color: string;
  textColor: string;
  isVisible: boolean;
  isActive: boolean;
  isProgressVisible: boolean;

  setText(text: string): MainButton;
  onClick(callback: () => void): MainButton;
  offClick(callback: () => void): MainButton;
  show(): MainButton;
  hide(): MainButton;
  enable(): MainButton;
  disable(): MainButton;
  showProgress(leaveActive?: boolean): MainButton;
  hideProgress(): MainButton;
  setParams(params: MainButtonParams): MainButton;
}

export interface MainButtonParams {
  text?: string;
  color?: string;
  text_color?: string;
  is_active?: boolean;
  is_visible?: boolean;
  has_shine_effect?: boolean;
}

export interface BackButton {
  isVisible: boolean;
  onClick(callback: () => void): BackButton;
  offClick(callback: () => void): BackButton;
  show(): BackButton;
  hide(): BackButton;
}

export interface HapticFeedback {
  impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void;
  notificationOccurred(type: 'error' | 'success' | 'warning'): void;
  selectionChanged(): void;
}

export interface CloudStorage {
  setItem(key: string, value: string, callback?: (error: string | null, success: boolean) => void): void;
  getItem(key: string, callback: (error: string | null, value: string | null) => void): void;
  getItems(keys: string[], callback: (error: string | null, values: Record<string, string>) => void): void;
  removeItem(key: string, callback?: (error: string | null, success: boolean) => void): void;
  removeItems(keys: string[], callback?: (error: string | null, success: boolean) => void): void;
  getKeys(callback: (error: string | null, keys: string[]) => void): void;
}

export interface ThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
  header_bg_color?: string;
  accent_text_color?: string;
  section_bg_color?: string;
  section_header_text_color?: string;
  subtitle_text_color?: string;
  destructive_text_color?: string;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

export {};
