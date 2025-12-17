/**
 * Premium Purchase Modal
 * Multi-step payment flow: Payment Method → Plan Selection → Confirmation
 */

'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TonConnectButton } from '@tonconnect/ui-react';
import { useTonPayment } from '@/shared/hooks/useTonPayment';
import { usePlatform } from '@/lib/platform';
import { useTranslations } from 'next-intl';
import toast from 'react-hot-toast';
import { usePostHog } from '@/components/providers/PostHogProvider';
import { useUserStore } from '@/shared/store/userStore';
import { vibrate, vibrateNotification, vibrateSelection } from '@/shared/telegram/vibration';

interface PremiumPurchaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void; // Callback when payment is successful
  referralDiscount?: number; // Discount percentage from referral tier
}

type PaymentProvider = 'telegram_stars' | 'ton_connect' | 'crypto_bot' | 'nowpayments';
type SubscriptionTier = 'basic' | 'premium' | 'vip';
type Duration = 1 | 3 | 12;


// Pricing configuration (features loaded from i18n)
const PLAN_PRICING = {
  basic: { monthly: 9.99, quarterly: 25.47, yearly: 89.91 },
  premium: { monthly: 24.99, quarterly: 63.72, yearly: 224.91 },
  vip: { monthly: 49.99, quarterly: 127.47, yearly: 449.91 },
};

// $SYNTRA Points bonuses for subscriptions (synced with points_config.py)
const SUBSCRIPTION_POINTS_BONUS: Record<SubscriptionTier, Record<Duration, number>> = {
  basic: { 1: 100, 3: 400, 12: 2000 },
  premium: { 1: 500, 3: 2000, 12: 10000 },
  vip: { 1: 1500, 3: 6000, 12: 30000 },
};

const PLAN_ICONS: Record<SubscriptionTier, string> = {
  basic: '⭐',
  premium: '💎',
  vip: '👑',
};

// Feature keys for each tier (order matters for display)
const TIER_FEATURE_KEYS: Record<SubscriptionTier, string[]> = {
  basic: ['limits', 'thinking', 'indicators', 'levels'],
  premium: ['limits', 'includes', 'onchain', 'macro', 'trial'],
  vip: ['limits', 'includes', 'reasoning', 'priority', 'support'],
};

export default function PremiumPurchaseModal({
  isOpen,
  onClose,
  onSuccess,
  referralDiscount = 0,
}: PremiumPurchaseModalProps) {
  // i18n translations
  const t = useTranslations();

  // Platform hook
  const { platform, platformType } = usePlatform();
  const posthog = usePostHog();
  const { user } = useUserStore();

  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);
  const [paymentProvider, setPaymentProvider] = useState<PaymentProvider | null>(null);
  const [selectedTier, setSelectedTier] = useState<SubscriptionTier | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<Duration>(1);
  const [selectedCurrency, setSelectedCurrency] = useState<'ton' | 'usdt'>('usdt');
  const [paymentData, setPaymentData] = useState<{
    payment_id: number;
    deposit_address: string;
    memo: string;
    amount_ton: number;
    amount_usdt: number;
    expires_at: string;
  } | null>(null);
  const [isSendingPayment, setIsSendingPayment] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [pollingAttempts, setPollingAttempts] = useState(0);

  // CryptoBot specific state
  const [cryptoBotAsset, setCryptoBotAsset] = useState<string>('USDT');
  const [cryptoBotInvoice, setCryptoBotInvoice] = useState<{
    invoice_id: number;
    bot_invoice_url: string;
    mini_app_invoice_url?: string;
    amount_crypto: number;
    asset: string;
    status: string;
  } | null>(null);
  const [isCreatingInvoice, setIsCreatingInvoice] = useState(false);
  const [isCryptoBotPolling, setIsCryptoBotPolling] = useState(false);

  // NOWPayments specific state
  const [isCreatingNOWInvoice, setIsCreatingNOWInvoice] = useState(false);
  const [isNOWPolling, setIsNOWPolling] = useState(false);
  const [nowPaymentId, setNowPaymentId] = useState<number | null>(null);

  // CryptoBot supported assets with icons
  const CRYPTO_ASSETS = [
    { id: 'USDT', name: 'Tether', icon: '/icons/crypto/USDT.png' },
    { id: 'TON', name: 'Toncoin', icon: '/icons/crypto/TON.png' },
    { id: 'BTC', name: 'Bitcoin', icon: '/icons/crypto/BTC.png' },
    { id: 'ETH', name: 'Ethereum', icon: '/icons/crypto/ETH.png' },
    { id: 'LTC', name: 'Litecoin', icon: '/icons/crypto/LTC.png' },
    { id: 'BNB', name: 'BNB', icon: '/icons/crypto/BNB.png' },
    { id: 'TRX', name: 'TRON', icon: '/icons/crypto/TRX.png' },
    { id: 'USDC', name: 'USD Coin', icon: '/icons/crypto/USDC.png' },
  ];

  // TON Connect hook
  const {
    sendTonPayment,
    sendUsdtPayment,
    isConnected: isTonConnected,
    wallet,
  } = useTonPayment();

  // Reset state when modal closes
  const handleClose = () => {
    setStep(1);
    setPaymentProvider(null);
    setSelectedTier(null);
    setSelectedDuration(1);
    setCryptoBotAsset('USDT');
    setCryptoBotInvoice(null);
    setIsCreatingInvoice(false);
    setIsCryptoBotPolling(false);
    setIsCreatingNOWInvoice(false);
    setIsNOWPolling(false);
    setNowPaymentId(null);
    onClose();
  };

  // Calculate price with discount
  const calculatePrice = (basePrice: number): number => {
    const discountAmount = basePrice * (referralDiscount / 100);
    return basePrice - discountAmount;
  };

  // Get selected plan pricing
  const selectedPricing = selectedTier ? PLAN_PRICING[selectedTier] : null;

  // Get base price WITHOUT duration discount (monthly * months)
  const getOriginalPrice = (): number => {
    if (!selectedPricing) return 0;
    return selectedPricing.monthly * selectedDuration;
  };

  // Get price WITH duration discount applied
  const getPriceWithDurationDiscount = (): number => {
    if (!selectedPricing) return 0;
    if (selectedDuration === 1) return selectedPricing.monthly;
    if (selectedDuration === 3) return selectedPricing.quarterly;
    return selectedPricing.yearly;
  };

  // Apply referral discount to already discounted price
  const finalPrice = calculatePrice(getPriceWithDurationDiscount());

  // Convert USD to Telegram Stars (rate: 1 Star ≈ $0.013, ~76.9 Stars per $1)
  const usdToStars = (usd: number): number => {
    const USD_TO_STAR = 76.9; // From backend telegram_stars_service.py
    return Math.round(usd * USD_TO_STAR);
  };

  // Get discount percentage based on duration
  const getDurationDiscount = (): number => {
    if (selectedDuration === 3) return 15;
    if (selectedDuration === 12) return 25;
    return 0;
  };

  // Handle payment
  const handlePayment = async () => {
    if (!paymentProvider || !selectedTier) {
      toast.error('Please select payment method and plan');
      return;
    }

    // 📊 Track payment started
    if (posthog.__loaded && user) {
      posthog.capture('payment_started', {
        tier: selectedTier,
        duration_months: selectedDuration,
        amount_usd: finalPrice,
        provider: paymentProvider,
        current_tier: user.subscription?.tier || 'free',
        platform: 'miniapp',
      });
    }

    try {
      // Import api client dynamically to avoid SSR issues
      const { api } = await import('@/shared/api/client');

      if (paymentProvider === 'telegram_stars') {
        // Check if we're in Telegram platform
        if (platformType !== 'telegram' || !platform) {
          toast.error('Telegram Stars payment is only available in Telegram Mini App');
          return;
        }

        // Create payment via platform abstraction
        // Provider handles API call and invoice opening internally
        const loadingToast = toast.loading('Creating invoice...');

        try {
          const result = await platform.payments.createPayment({
            tier: selectedTier,
            duration_months: selectedDuration,
            amount: finalPrice,
            currency: 'STARS',
          });

          toast.dismiss(loadingToast);

          // Handle payment result
          if (result.status === 'completed') {
            toast.success('Payment successful! Subscription activated 🎉');
            onSuccess?.();
            handleClose();
          } else if (result.status === 'failed') {
            toast.error('Payment cancelled or failed');
          } else if (result.status === 'pending') {
            toast.loading('Processing payment...', { duration: 3000 });
          }
        } catch (error) {
          toast.dismiss(loadingToast);
          throw error;
        }
      } else if (paymentProvider === 'ton_connect') {
        // TON Connect payment - создаем payment request
        toast.loading('Creating payment request...');

        const response = await api.payment.createTonPayment({
          tier: selectedTier,
          duration_months: selectedDuration,
          currency: selectedCurrency,
        });

        toast.dismiss();

        if (response.success && response.data) {
          // Сохраняем payment данные и переходим на шаг 4
          setPaymentData(response.data);
          setStep(4);
          toast.success('Payment request created! Connect your wallet');
        } else {
          toast.error(response.error || 'Failed to create payment request');
        }
      } else {
        toast.error('Payment method not available yet');
      }
    } catch (error) {
      console.error('Payment error:', error);
      toast.dismiss();
      toast.error('Payment failed. Please try again.');
    }
  };

  // Start polling payment status after TON/USDT send
  const startPaymentPolling = async () => {
    if (!paymentData) {
      toast.error('Payment data not found');
      return;
    }

    const MAX_ATTEMPTS = 36; // 36 attempts * 5 seconds = 3 minutes
    const POLL_INTERVAL = 5000; // 5 seconds
    let attempts = 0;

    setIsPolling(true);
    toast.success(t('premium.ton_payment.payment_sent'));

    const pollInterval = setInterval(async () => {
      attempts++;
      setPollingAttempts(attempts);

      try {
        const { api } = await import('@/shared/api/client');
        const statusResponse = await api.payment.getPaymentStatus(paymentData.payment_id);

        if (statusResponse.success && statusResponse.payment) {
          const { payment, subscription } = statusResponse;

          if (payment.status === 'completed') {
            // Payment confirmed!
            clearInterval(pollInterval);
            setIsPolling(false);

            // 📊 Track payment completed (frontend confirmation)
            if (posthog.__loaded && user) {
              posthog.capture('subscription_purchased', {
                tier: subscription?.tier || selectedTier,
                duration_months: selectedDuration,
                amount_usd: finalPrice,
                provider: paymentProvider || 'ton_connect',
                is_upgrade: (user.subscription?.tier || 'free') !== 'free',
                platform: 'miniapp',
              });
            }

            toast.success(
              t('premium.ton_payment.payment_confirmed', {
                tier: subscription?.tier.toUpperCase() || '',
                date: subscription?.expires_at
                  ? new Date(subscription.expires_at).toLocaleDateString()
                  : 'N/A'
              })
            );

            // Call onSuccess callback to refresh user data
            onSuccess?.();

            // Close modal after 2 seconds
            setTimeout(() => {
              handleClose();
            }, 2000);
          } else if (payment.status === 'failed') {
            // Payment failed
            clearInterval(pollInterval);
            setIsPolling(false);
            toast.error(t('premium.ton_payment.payment_failed'));
          }
        }
      } catch (error) {
        console.error('Polling error:', error);
      }

      // Stop polling after max attempts
      if (attempts >= MAX_ATTEMPTS) {
        clearInterval(pollInterval);
        setIsPolling(false);
        toast.error(t('premium.ton_payment.payment_timeout'));
      }
    }, POLL_INTERVAL);
  };

  // Handle TON/USDT payment send
  const handleSendTonPayment = async () => {
    if (!paymentData || !isTonConnected) {
      toast.error(t('premium.ton_payment.wallet_required'));
      return;
    }

    setIsSendingPayment(true);

    try {
      const result = selectedCurrency === 'ton'
        ? await sendTonPayment({
            address: paymentData.deposit_address,
            amount: paymentData.amount_ton,
            memo: paymentData.memo,
          })
        : await sendUsdtPayment({
            address: paymentData.deposit_address,
            amount: paymentData.amount_usdt,
            memo: paymentData.memo,
          });

      if (result.success) {
        // Start polling for payment confirmation
        await startPaymentPolling();
      }
    } catch (error) {
      console.error('Payment send error:', error);
      toast.error('Failed to send payment. Please try again.');
    } finally {
      setIsSendingPayment(false);
    }
  };

  // Create CryptoBot invoice and open payment
  const handleCryptoBotPayment = async () => {
    if (!selectedTier) {
      toast.error('Please select a plan');
      return;
    }

    setIsCreatingInvoice(true);
    const loadingToast = toast.loading('Creating invoice...');

    try {
      const { api } = await import('@/shared/api/client');

      const response = await api.cryptoPay.createInvoice({
        tier: selectedTier,
        duration_months: selectedDuration,
        asset: cryptoBotAsset,
      });

      toast.dismiss(loadingToast);

      if (response.success && response.data) {
        const invoiceData = response.data;

        // Save invoice data
        setCryptoBotInvoice({
          invoice_id: invoiceData.invoice_id,
          bot_invoice_url: invoiceData.bot_invoice_url,
          mini_app_invoice_url: invoiceData.mini_app_invoice_url,
          amount_crypto: invoiceData.amount_crypto,
          asset: invoiceData.asset,
          status: invoiceData.status,
        });

        // 📊 Track CryptoBot payment started
        if (posthog.__loaded && user) {
          posthog.capture('payment_started', {
            tier: selectedTier,
            duration_months: selectedDuration,
            amount_usd: finalPrice,
            provider: 'crypto_bot',
            asset: cryptoBotAsset,
            platform: platformType,
          });
        }

        // Open CryptoBot for payment
        const paymentUrl = invoiceData.mini_app_invoice_url || invoiceData.bot_invoice_url;

        // In Telegram Mini App, use openTelegramLink for @CryptoBot
        if (platformType === 'telegram' && window.Telegram?.WebApp) {
          window.Telegram.WebApp.openTelegramLink(invoiceData.bot_invoice_url);
        } else {
          // On web, open in new tab
          window.open(paymentUrl, '_blank');
        }

        toast.success('Invoice created! Complete payment in @CryptoBot');

        // Start polling for payment confirmation
        startCryptoBotPolling(invoiceData.invoice_id);
      } else {
        toast.error(response.error || 'Failed to create invoice');
      }
    } catch (error) {
      console.error('CryptoBot payment error:', error);
      toast.dismiss(loadingToast);
      toast.error('Failed to create invoice. Please try again.');
    } finally {
      setIsCreatingInvoice(false);
    }
  };

  // Create NOWPayments invoice and open payment page
  const handleNOWPaymentsPayment = async () => {
    if (!selectedTier) {
      toast.error('Please select a plan');
      return;
    }

    setIsCreatingNOWInvoice(true);
    const loadingToast = toast.loading('Creating invoice...');

    try {
      const { api } = await import('@/shared/api/client');

      const response = await api.nowPayments.createInvoice({
        tier: selectedTier,
        duration_months: selectedDuration,
      });

      toast.dismiss(loadingToast);

      if (response.success && response.data) {
        const invoiceData = response.data;

        // 📊 Track NOWPayments payment started
        if (posthog.__loaded && user) {
          posthog.capture('payment_started', {
            tier: selectedTier,
            duration_months: selectedDuration,
            amount_usd: finalPrice,
            provider: 'nowpayments',
            platform: platformType,
          });
        }

        // Save payment_id for polling
        setNowPaymentId(invoiceData.payment_id);

        // Open NOWPayments invoice page in new window
        window.open(invoiceData.invoice_url, '_blank');

        toast.success('Complete payment in the opened window');

        // Start polling for payment status
        startNOWPaymentsPolling(invoiceData.payment_id);
      } else {
        toast.error(response.error || 'Failed to create invoice');
      }
    } catch (error) {
      console.error('NOWPayments payment error:', error);
      toast.dismiss(loadingToast);
      toast.error('Failed to create invoice. Please try again.');
    } finally {
      setIsCreatingNOWInvoice(false);
    }
  };

  // Poll NOWPayments payment status
  const startNOWPaymentsPolling = async (paymentId: number) => {
    const MAX_ATTEMPTS = 180; // 180 * 5s = 15 minutes
    const POLL_INTERVAL = 5000;
    let attempts = 0;

    setIsNOWPolling(true);

    const pollInterval = setInterval(async () => {
      attempts++;
      setPollingAttempts(attempts);

      try {
        const { api } = await import('@/shared/api/client');
        const statusResponse = await api.nowPayments.getPaymentStatus(paymentId);

        if (statusResponse.success && statusResponse.payment) {
          const { payment, subscription } = statusResponse;

          // NOWPayments statuses: waiting, confirming, confirmed, sending, finished, failed, expired
          if (payment.status === 'completed' || payment.status === 'finished') {
            // Payment confirmed!
            clearInterval(pollInterval);
            setIsNOWPolling(false);

            // 📊 Track payment completed
            if (posthog.__loaded && user) {
              posthog.capture('subscription_purchased', {
                tier: subscription?.tier || selectedTier,
                duration_months: selectedDuration,
                amount_usd: finalPrice,
                provider: 'nowpayments',
                platform: platformType,
              });
            }

            toast.success('Payment confirmed! Subscription activated 🎉');
            onSuccess?.();

            setTimeout(() => {
              handleClose();
            }, 2000);
          } else if (payment.status === 'failed' || payment.status === 'expired') {
            clearInterval(pollInterval);
            setIsNOWPolling(false);
            toast.error('Payment failed or expired');
          }
        }
      } catch (error) {
        console.error('NOWPayments polling error:', error);
      }

      if (attempts >= MAX_ATTEMPTS) {
        clearInterval(pollInterval);
        setIsNOWPolling(false);
        toast.error('Payment verification timeout. Check your email for confirmation.');
      }
    }, POLL_INTERVAL);
  };

  // Poll CryptoBot invoice status
  const startCryptoBotPolling = async (invoiceId: number) => {
    const MAX_ATTEMPTS = 120; // 120 * 5s = 10 minutes (invoice expires in 30 min)
    const POLL_INTERVAL = 5000;
    let attempts = 0;

    setIsCryptoBotPolling(true);

    const pollInterval = setInterval(async () => {
      attempts++;
      setPollingAttempts(attempts);

      try {
        const { api } = await import('@/shared/api/client');
        const statusResponse = await api.cryptoPay.getInvoiceStatus(invoiceId);

        if (statusResponse.success && statusResponse.data) {
          const { status, processed } = statusResponse.data;

          // Update local state
          if (cryptoBotInvoice) {
            setCryptoBotInvoice({ ...cryptoBotInvoice, status });
          }

          if (status === 'paid' && processed) {
            // Payment confirmed and subscription activated!
            clearInterval(pollInterval);
            setIsCryptoBotPolling(false);

            // 📊 Track payment completed
            if (posthog.__loaded && user) {
              posthog.capture('subscription_purchased', {
                tier: selectedTier,
                duration_months: selectedDuration,
                amount_usd: finalPrice,
                provider: 'crypto_bot',
                asset: cryptoBotAsset,
                platform: platformType,
              });
            }

            toast.success('Payment confirmed! Subscription activated 🎉');
            onSuccess?.();

            setTimeout(() => {
              handleClose();
            }, 2000);
          } else if (status === 'expired' || status === 'cancelled') {
            clearInterval(pollInterval);
            setIsCryptoBotPolling(false);
            toast.error('Invoice expired or cancelled');
          }
        }
      } catch (error) {
        console.error('CryptoBot polling error:', error);
      }

      if (attempts >= MAX_ATTEMPTS) {
        clearInterval(pollInterval);
        setIsCryptoBotPolling(false);
        toast.error('Payment verification timeout. Check @CryptoBot for status.');
      }
    }, POLL_INTERVAL);
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/80 flex items-end sm:items-center justify-center z-50"
      onClick={handleClose}
    >
      <motion.div
        initial={{ opacity: 0, y: 100 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 100 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="bg-[#111] border-t sm:border border-white/5 rounded-t-2xl sm:rounded-2xl w-full sm:max-w-md max-h-[92vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header - sticky */}
        <div className="flex items-center justify-between p-4 border-b border-white/5 shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-white font-bold text-lg">{t('premium.title')}</h2>
            {/* Progress dots */}
            <div className="flex gap-1">
              {(paymentProvider === 'ton_connect'
                ? [1, 2, 3, 4]
                : paymentProvider === 'telegram_stars'
                ? [1, 2]
                : paymentProvider === 'nowpayments'
                ? [1, 2, 3]
                : paymentProvider === 'crypto_bot'
                ? [1, 2, 3]
                : [1, 2, 3]
              ).map((s) => (
                <div
                  key={s}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    s <= step ? 'bg-blue-500' : 'bg-gray-700'
                  }`}
                />
              ))}
            </div>
          </div>
          <button
            onClick={() => { vibrate('light'); handleClose(); }}
            className="text-gray-400 hover:text-white transition-colors p-1"
          >
            ✕
          </button>
        </div>

        {/* Scrollable content area */}
        <div className="flex-1 overflow-y-auto overscroll-contain">
          <AnimatePresence mode="wait">
            {/* Step 1: Payment Method Selection */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-4"
              >
                <h3 className="text-white font-medium text-sm mb-3">{t('premium.payment_methods.title')}</h3>

                <div className="space-y-2">
                  {/* Telegram Stars */}
                  <button
                    onClick={() => { vibrateSelection(); setPaymentProvider('telegram_stars'); }}
                    className={`w-full bg-gray-900/50 border border-white/5 rounded-xl p-3 text-left transition-all ${
                      paymentProvider === 'telegram_stars'
                        ? 'ring-2 ring-blue-500 bg-blue-500/10'
                        : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center text-lg">
                        ⭐
                      </div>
                      <div className="flex-1">
                        <div className="text-white font-medium text-sm">Telegram Stars</div>
                        <div className="text-gray-400 text-xs">Fast & secure</div>
                      </div>
                      {paymentProvider === 'telegram_stars' && (
                        <div className="text-blue-500">✓</div>
                      )}
                    </div>
                  </button>

                  {/* TON Connect */}
                  <button
                    onClick={() => { vibrateSelection(); setPaymentProvider('ton_connect'); }}
                    className={`w-full bg-gray-900/50 border border-white/5 rounded-xl p-3 text-left transition-all ${
                      paymentProvider === 'ton_connect'
                        ? 'ring-2 ring-blue-500 bg-blue-500/10'
                        : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-[#0098EA] flex items-center justify-center overflow-hidden">
                        <img src="/icons/crypto/TON.png" alt="TON" className="w-6 h-6" />
                      </div>
                      <div className="flex-1">
                        <div className="text-white font-medium text-sm">TON Connect</div>
                        <div className="text-gray-400 text-xs flex items-center gap-1">
                          <img src="/icons/crypto/USDT.png" alt="USDT" className="w-3 h-3" />
                          <span>USDT</span>
                          <span className="text-gray-600">•</span>
                          <img src="/icons/crypto/TON.png" alt="TON" className="w-3 h-3" />
                          <span>TON</span>
                        </div>
                      </div>
                      {paymentProvider === 'ton_connect' && (
                        <div className="text-blue-500">✓</div>
                      )}
                    </div>
                  </button>

                  {/* Crypto Bot */}
                  <button
                    onClick={() => { vibrateSelection(); setPaymentProvider('crypto_bot'); }}
                    className={`w-full bg-gray-900/50 border border-white/5 rounded-xl p-3 text-left transition-all ${
                      paymentProvider === 'crypto_bot'
                        ? 'ring-2 ring-blue-500 bg-blue-500/10'
                        : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full overflow-hidden bg-[#2AABEE]">
                        <img src="/icons/crypto/cryptobot.png" alt="CryptoBot" className="w-full h-full object-cover" />
                      </div>
                      <div className="flex-1">
                        <div className="text-white font-medium text-sm">Crypto Bot</div>
                        <div className="text-gray-400 text-xs flex items-center gap-0.5">
                          <img src="/icons/crypto/BTC.png" alt="BTC" className="w-3 h-3" />
                          <img src="/icons/crypto/ETH.png" alt="ETH" className="w-3 h-3" />
                          <img src="/icons/crypto/USDT.png" alt="USDT" className="w-3 h-3" />
                          <img src="/icons/crypto/TON.png" alt="TON" className="w-3 h-3" />
                          <span className="ml-1">+4 more</span>
                        </div>
                      </div>
                      {paymentProvider === 'crypto_bot' && (
                        <div className="text-blue-500">✓</div>
                      )}
                    </div>
                  </button>

                  {/* NOWPayments */}
                  <button
                    onClick={() => { vibrateSelection(); setPaymentProvider('nowpayments'); }}
                    className={`w-full bg-gray-900/50 border border-white/5 rounded-xl p-3 text-left transition-all ${
                      paymentProvider === 'nowpayments'
                        ? 'ring-2 ring-blue-500 bg-blue-500/10'
                        : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-xs">
                        NOW
                      </div>
                      <div className="flex-1">
                        <div className="text-white font-medium text-sm">NOWPayments</div>
                        <div className="text-gray-400 text-xs">300+ cryptocurrencies</div>
                      </div>
                      {paymentProvider === 'nowpayments' && (
                        <div className="text-blue-500">✓</div>
                      )}
                    </div>
                  </button>
                </div>
              </motion.div>
            )}

            {/* Step 2: Plan Selection */}
            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-4"
              >
                <h3 className="text-white font-medium text-sm mb-3">{t('premium.plan_selection.title')}</h3>

                {/* Tier Selection with features */}
                <div className="space-y-2 mb-4">
                  {(['basic', 'premium', 'vip'] as SubscriptionTier[]).map((tier) => {
                    const pricing = PLAN_PRICING[tier];
                    const featureKeys = TIER_FEATURE_KEYS[tier];
                    return (
                      <button
                        key={tier}
                        onClick={() => { vibrateSelection(); setSelectedTier(tier); }}
                        className={`w-full bg-gray-900/50 border border-white/5 rounded-xl p-3 text-left transition-all ${
                          selectedTier === tier
                            ? 'ring-2 ring-blue-500 bg-blue-500/10'
                            : 'hover:bg-white/5'
                        }`}
                      >
                        {/* Header row */}
                        <div className="flex items-center gap-3 mb-2">
                          <div className="text-2xl">{PLAN_ICONS[tier]}</div>
                          <div className="flex-1 min-w-0">
                            <div className="text-white font-medium text-sm">{t(`premium.tiers.${tier}.name`)}</div>
                            <div className="text-gray-500 text-xs">{t(`premium.tiers.${tier}.features.limits`)}</div>
                          </div>
                          <div className="text-right shrink-0">
                            <div className="text-white font-bold text-sm">
                              ${pricing.monthly}
                            </div>
                            <div className="text-gray-500 text-xs">/{t('premium.plan_selection.month_short')}</div>
                          </div>
                          {selectedTier === tier && (
                            <div className="text-blue-500 shrink-0">✓</div>
                          )}
                        </div>
                        {/* Features list */}
                        <div className="pl-10 space-y-0.5">
                          {featureKeys.slice(1, 4).map((key) => (
                            <div key={key} className="text-gray-400 text-xs flex items-start gap-1.5">
                              <span className="text-blue-500 mt-0.5">•</span>
                              <span>{t(`premium.tiers.${tier}.features.${key}`)}</span>
                            </div>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {/* Duration Selection - always visible */}
                <div className="mb-4">
                  <label className="text-gray-400 text-xs mb-2 block">{t('premium.plan_selection.select_duration')}</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { months: 1 as Duration, labelKey: 'duration_1', discount: 0 },
                      { months: 3 as Duration, labelKey: 'duration_3', discount: 15 },
                      { months: 12 as Duration, labelKey: 'duration_12', discount: 25 },
                    ].map(({ months, labelKey, discount }) => (
                      <button
                        key={months}
                        onClick={() => { vibrateSelection(); setSelectedDuration(months); }}
                        className={`py-2 px-2 rounded-lg text-xs font-medium transition-all ${
                          selectedDuration === months
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-900/50 border border-white/5 text-gray-400 hover:text-white'
                        }`}
                      >
                        <div>{t(`premium.plan_selection.${labelKey}`)}</div>
                        {discount > 0 && (
                          <div className={`text-[10px] ${selectedDuration === months ? 'text-blue-200' : 'text-green-400'}`}>
                            -{discount}%
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Price Summary */}
                {selectedTier && selectedPricing && (
                  <div className="bg-gray-900/30 rounded-lg p-3 mb-2">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400 text-xs">Total</span>
                      <div className="text-right">
                        {getDurationDiscount() > 0 && (
                          <span className="text-gray-500 text-xs line-through mr-2">
                            ${getOriginalPrice().toFixed(0)}
                          </span>
                        )}
                        <span className="text-white font-bold">${finalPrice.toFixed(2)}</span>
                        {paymentProvider === 'telegram_stars' && (
                          <span className="text-gray-400 text-xs ml-1">
                            ≈ {usdToStars(finalPrice)} ⭐
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* $SYNTRA Points Bonus */}
                {selectedTier && (
                  <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg p-3 mb-2">
                    <div className="flex items-center gap-2">
                      <img
                        src="/syntra/$SYNTRA.png"
                        alt="$SYNTRA"
                        className="w-5 h-5"
                      />
                      <span className="text-sm font-medium bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                        +{SUBSCRIPTION_POINTS_BONUS[selectedTier][selectedDuration].toLocaleString()} $SYNTRA Points
                      </span>
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* Step 3: Confirmation (TON Connect) or CryptoBot Currency Selection */}
            {step === 3 && selectedTier && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-4"
              >
                {/* NOWPayments: Simple confirmation (no currency selection) */}
                {paymentProvider === 'nowpayments' ? (
                  <>
                    <h3 className="text-white font-medium text-sm mb-3">Confirm Payment</h3>

                    {/* Compact Order Summary */}
                    <div className="bg-gray-900/50 border border-white/5 rounded-lg p-3 mb-3">
                      <div className="flex items-center gap-2">
                        <div className="text-xl">{PLAN_ICONS[selectedTier]}</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-white font-medium text-sm">{t(`premium.tiers.${selectedTier}.name`)}</div>
                          <div className="text-gray-400 text-xs">
                            {selectedDuration} {t('premium.plan_selection.month_short')}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-white font-bold text-sm">${finalPrice.toFixed(2)}</div>
                        </div>
                      </div>
                    </div>

                    {/* Payment Info */}
                    {!isNOWPolling && (
                      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mb-3">
                        <div className="flex items-start gap-2">
                          <div className="text-blue-400 text-sm">ℹ️</div>
                          <div className="text-blue-400 text-xs">
                            Choose from 300+ cryptocurrencies on payment page (BTC, ETH, USDT, TON, and more)
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Polling Status */}
                    {isNOWPolling && nowPaymentId && (
                      <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 mb-3">
                        <div className="flex items-center gap-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-green-500"></div>
                          <div>
                            <div className="text-green-400 text-sm font-medium">
                              Waiting for payment...
                            </div>
                            <div className="text-green-400/70 text-xs">
                              Complete payment in the opened window
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                ) : paymentProvider === 'crypto_bot' ? (
                  /* CryptoBot: Currency Selection + Payment */
                  <>
                    <h3 className="text-white font-medium text-sm mb-3">{t('premium.crypto_bot.select_currency')}</h3>

                    {/* Compact Crypto Currency Grid */}
                    <div className="grid grid-cols-4 gap-1.5 mb-4">
                      {CRYPTO_ASSETS.map((asset) => (
                        <button
                          key={asset.id}
                          onClick={() => { vibrateSelection(); setCryptoBotAsset(asset.id); }}
                          className={`bg-gray-900/50 border border-white/5 rounded-lg p-2 transition-all ${
                            cryptoBotAsset === asset.id
                              ? 'ring-2 ring-blue-500 bg-blue-500/10'
                              : 'hover:bg-white/5'
                          }`}
                        >
                          <div className="text-center">
                            <img
                              src={asset.icon}
                              alt={asset.name}
                              className="w-6 h-6 mx-auto mb-0.5 rounded-full"
                              onError={(e) => {
                                (e.target as HTMLImageElement).style.display = 'none';
                              }}
                            />
                            <div className="text-white text-[10px] font-medium">{asset.id}</div>
                          </div>
                        </button>
                      ))}
                    </div>

                    {/* Compact Order Summary */}
                    <div className="bg-gray-900/50 border border-white/5 rounded-lg p-3 mb-3">
                      <div className="flex items-center gap-2">
                        <div className="text-xl">{PLAN_ICONS[selectedTier]}</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-white font-medium text-sm">{t(`premium.tiers.${selectedTier}.name`)}</div>
                          <div className="text-gray-400 text-xs">
                            {selectedDuration} {t('premium.plan_selection.month_short')}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-white font-bold text-sm">${finalPrice.toFixed(2)}</div>
                        </div>
                      </div>
                    </div>

                    {/* Polling Status */}
                    {isCryptoBotPolling && (
                      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-2 mb-3">
                        <div className="flex items-center gap-2">
                          <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-500"></div>
                          <span className="text-blue-400 text-xs">
                            Waiting for payment...
                          </span>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  /* TON Connect: Confirmation */
                  <>
                    <h3 className="text-white font-medium text-sm mb-3">{t('premium.confirmation.title')}</h3>

                    {/* Compact Order Summary */}
                    <div className="bg-gray-900/50 border border-white/5 rounded-lg p-3 mb-3">
                      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-800">
                        <div className="text-xl">{PLAN_ICONS[selectedTier]}</div>
                        <div className="flex-1">
                          <div className="text-white font-medium text-sm">{t(`premium.tiers.${selectedTier}.name`)}</div>
                          <div className="text-gray-400 text-xs">
                            {selectedDuration} {t('premium.plan_selection.month_short')}
                          </div>
                        </div>
                      </div>

                      <div className="space-y-1 text-xs">
                        {getDurationDiscount() > 0 && (
                          <div className="flex justify-between text-green-400">
                            <span>Discount ({getDurationDiscount()}%)</span>
                            <span>-${(getOriginalPrice() * (getDurationDiscount() / 100)).toFixed(2)}</span>
                          </div>
                        )}

                        {referralDiscount > 0 && (
                          <div className="flex justify-between text-green-400">
                            <span>Referral ({referralDiscount}%)</span>
                            <span>-${(getPriceWithDurationDiscount() * (referralDiscount / 100)).toFixed(2)}</span>
                          </div>
                        )}

                        <div className="flex justify-between pt-1 border-t border-gray-800">
                          <span className="text-white font-medium">Total</span>
                          <span className="text-white font-bold">${finalPrice.toFixed(2)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Payment Method Badge */}
                    <div className="bg-gray-900/30 rounded-lg p-2 mb-2 flex items-center gap-2">
                      <img src="/icons/crypto/TON.png" alt="TON" className="w-5 h-5" />
                      <span className="text-gray-400 text-xs">TON Connect</span>
                    </div>
                  </>
                )}
              </motion.div>
            )}

            {/* Step 4: TON Connect Payment */}
            {step === 4 && paymentData && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-4 space-y-3"
              >
                <h3 className="text-white font-medium text-sm">{t('premium.ton_payment.title')}</h3>

                {/* Compact Currency Selection */}
                <div>
                  <label className="text-gray-400 text-xs mb-2 block">{t('premium.ton_payment.select_currency')}</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => { vibrateSelection(); setSelectedCurrency('usdt'); }}
                      className={`bg-gray-900/50 border border-white/5 rounded-lg p-3 transition-all ${
                        selectedCurrency === 'usdt'
                          ? 'ring-2 ring-blue-500 bg-blue-500/10'
                          : 'hover:bg-white/5'
                      }`}
                    >
                      <div className="flex flex-col items-center">
                        <img src="/icons/crypto/USDT.png" alt="USDT" className="w-8 h-8 mb-1" />
                        <div className="text-white font-medium text-sm">USDT</div>
                        <div className="text-gray-400 text-xs">{paymentData.amount_usdt}</div>
                      </div>
                    </button>
                    <button
                      onClick={() => { vibrateSelection(); setSelectedCurrency('ton'); }}
                      className={`bg-gray-900/50 border border-white/5 rounded-lg p-3 transition-all ${
                        selectedCurrency === 'ton'
                          ? 'ring-2 ring-blue-500 bg-blue-500/10'
                          : 'hover:bg-white/5'
                      }`}
                    >
                      <div className="flex flex-col items-center">
                        <img src="/icons/crypto/TON.png" alt="TON" className="w-8 h-8 mb-1" />
                        <div className="text-white font-medium text-sm">TON</div>
                        <div className="text-gray-400 text-xs">{paymentData.amount_ton.toFixed(2)}</div>
                      </div>
                    </button>
                  </div>
                </div>

                {/* TON Connect Button */}
                <div className="bg-gray-900/50 border border-white/5 rounded-lg p-3">
                  <div className="text-gray-400 text-xs mb-2">Connect Wallet</div>
                  <div className="ton-connect-wrapper">
                    <TonConnectButton />
                  </div>
                </div>

                {/* Payment Details (shown when wallet connected) */}
                {isTonConnected && wallet && (
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="text-green-400 text-sm">✓</div>
                      <div className="text-white font-medium text-xs">Wallet Connected</div>
                    </div>
                    <div className="text-xs text-gray-400 space-y-1">
                      <div className="flex justify-between">
                        <span>Amount:</span>
                        <span className="text-white">
                          {selectedCurrency === 'usdt'
                            ? `${paymentData.amount_usdt} USDT`
                            : `${paymentData.amount_ton.toFixed(2)} TON`
                          }
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Info Message */}
                {!isTonConnected && (
                  <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-2">
                    <p className="text-yellow-400 text-xs">
                      ⚠️ Connect wallet to pay
                    </p>
                  </div>
                )}

                {/* Polling Status */}
                {isPolling && (
                  <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-2">
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-500"></div>
                      <span className="text-blue-400 text-xs">
                        Confirming... ({pollingAttempts}/36)
                      </span>
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Sticky Footer with Action Buttons */}
        <div className="p-4 border-t border-white/5 shrink-0 bg-[#111]">
          {/* Step 1: Continue */}
          {step === 1 && (
            <button
              onClick={() => { vibrate('medium'); setStep(2); }}
              disabled={!paymentProvider}
              className={`w-full py-3 rounded-xl font-medium text-sm transition-all ${
                paymentProvider
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-gray-800 text-gray-500 cursor-not-allowed'
              }`}
            >
              Continue
            </button>
          )}

          {/* Step 2: Back + Continue/Pay */}
          {step === 2 && (
            <div className="flex gap-2">
              <button
                onClick={() => { vibrate('light'); setStep(1); }}
                className="flex-1 py-3 rounded-xl font-medium text-sm bg-gray-800 hover:bg-gray-700 text-white transition-colors"
              >
                Back
              </button>
              {paymentProvider === 'telegram_stars' ? (
                <button
                  onClick={() => { vibrate('heavy'); handlePayment(); }}
                  disabled={!selectedTier}
                  className={`flex-1 py-3 rounded-xl font-medium text-sm transition-all ${
                    selectedTier
                      ? 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white'
                      : 'bg-gray-800 text-gray-500 cursor-not-allowed'
                  }`}
                >
                  ⭐ Pay {selectedTier && selectedPricing ? `$${finalPrice.toFixed(0)}` : ''}
                </button>
              ) : (
                <button
                  onClick={() => { vibrate('medium'); setStep(3); }}
                  disabled={!selectedTier}
                  className={`flex-1 py-3 rounded-xl font-medium text-sm transition-all ${
                    selectedTier
                      ? 'bg-blue-600 hover:bg-blue-700 text-white'
                      : 'bg-gray-800 text-gray-500 cursor-not-allowed'
                  }`}
                >
                  Continue
                </button>
              )}
            </div>
          )}

          {/* Step 3: Back + Pay */}
          {step === 3 && (
            <div className="flex gap-2">
              <button
                onClick={() => { vibrate('light'); setStep(2); }}
                disabled={isCryptoBotPolling || isCreatingNOWInvoice || isNOWPolling}
                className="flex-1 py-3 rounded-xl font-medium text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white transition-colors"
              >
                Back
              </button>
              {paymentProvider === 'nowpayments' ? (
                <button
                  onClick={() => { vibrate('heavy'); handleNOWPaymentsPayment(); }}
                  disabled={isCreatingNOWInvoice || isNOWPolling}
                  className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 text-white py-3 rounded-xl font-medium text-sm transition-all"
                >
                  {isCreatingNOWInvoice ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white"></div>
                      Creating...
                    </span>
                  ) : isNOWPolling ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white"></div>
                      Waiting...
                    </span>
                  ) : (
                    `Pay $${finalPrice.toFixed(2)}`
                  )}
                </button>
              ) : paymentProvider === 'crypto_bot' ? (
                <button
                  onClick={() => { vibrate('heavy'); handleCryptoBotPayment(); }}
                  disabled={isCreatingInvoice || isCryptoBotPolling}
                  className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 text-white py-3 rounded-xl font-medium text-sm transition-all"
                >
                  {isCreatingInvoice ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white"></div>
                      Creating...
                    </span>
                  ) : isCryptoBotPolling ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white"></div>
                      Waiting...
                    </span>
                  ) : (
                    `Pay with ${cryptoBotAsset}`
                  )}
                </button>
              ) : (
                <button
                  onClick={() => { vibrate('heavy'); handlePayment(); }}
                  className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white py-3 rounded-xl font-medium text-sm transition-all"
                >
                  Pay ${finalPrice.toFixed(2)}
                </button>
              )}
            </div>
          )}

          {/* Step 4: Back + Send */}
          {step === 4 && paymentData && (
            <div className="flex gap-2">
              <button
                onClick={() => { vibrate('light'); setStep(3); }}
                className="flex-1 py-3 rounded-xl font-medium text-sm bg-gray-800 hover:bg-gray-700 text-white transition-colors"
              >
                Back
              </button>
              <button
                onClick={() => { vibrate('heavy'); handleSendTonPayment(); }}
                disabled={!isTonConnected || isSendingPayment || isPolling}
                className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-3 rounded-xl font-medium text-sm transition-all"
              >
                {isSendingPayment ? (
                  <span className="flex items-center justify-center gap-2">
                    <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white"></div>
                    Sending...
                  </span>
                ) : isPolling ? (
                  <span className="flex items-center justify-center gap-2">
                    <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white"></div>
                    Confirming...
                  </span>
                ) : (
                  `Send ${selectedCurrency === 'usdt' ? `${paymentData.amount_usdt} USDT` : `${paymentData.amount_ton.toFixed(2)} TON`}`
                )}
              </button>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
