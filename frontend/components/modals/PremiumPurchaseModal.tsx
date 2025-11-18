/**
 * Premium Purchase Modal
 * Multi-step payment flow: Payment Method → Plan Selection → Confirmation
 */

'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TonConnectButton } from '@tonconnect/ui-react';
import { useTonPayment } from '@/shared/hooks/useTonPayment';
import { useTranslations } from 'next-intl';
import toast from 'react-hot-toast';

interface PremiumPurchaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void; // Callback when payment is successful
  referralDiscount?: number; // Discount percentage from referral tier
}

type PaymentProvider = 'telegram_stars' | 'ton_connect' | 'crypto_bot';
type SubscriptionTier = 'basic' | 'premium' | 'vip';
type Duration = 1 | 3 | 12;

interface PlanOption {
  tier: SubscriptionTier;
  name: string;
  icon: string;
  color: string;
  features: string[];
  pricing: {
    monthly: number;
    quarterly: number;
    yearly: number;
  };
}

// Pricing configuration from backend (matching telegram_stars_service.py)
const PLAN_OPTIONS: PlanOption[] = [
  {
    tier: 'basic',
    name: 'Basic',
    icon: '⭐',
    color: 'from-blue-500 to-blue-700',
    features: [
      '20 requests per day',
      'Basic technical indicators',
      'Email support',
    ],
    pricing: {
      monthly: 4.99, // Stars: 384
      quarterly: 12.72, // Stars: 978 (-15%)
      yearly: 44.91, // Stars: 3453 (-25%)
    },
  },
  {
    tier: 'premium',
    name: 'Premium',
    icon: '💎',
    color: 'from-purple-500 to-purple-700',
    features: [
      '100 requests per day',
      'Advanced technical indicators',
      'Priority support',
      'Price level tracking',
    ],
    pricing: {
      monthly: 24.99, // Stars: 1923
      quarterly: 63.72, // Stars: 4899 (-15%)
      yearly: 224.91, // Stars: 17298 (-25%)
    },
  },
  {
    tier: 'vip',
    name: 'VIP',
    icon: '👑',
    color: 'from-yellow-400 to-yellow-600',
    features: [
      'Unlimited requests',
      'All indicators and metrics',
      'Margin tracking',
      'Dedicated support',
      'API access',
    ],
    pricing: {
      monthly: 49.99, // Stars: 3845
      quarterly: 127.47, // Stars: 9802 (-15%)
      yearly: 449.91, // Stars: 34597 (-25%)
    },
  },
];

export default function PremiumPurchaseModal({
  isOpen,
  onClose,
  onSuccess,
  referralDiscount = 0,
}: PremiumPurchaseModalProps) {
  // i18n translations
  const t = useTranslations();

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [paymentProvider, setPaymentProvider] = useState<PaymentProvider | null>(null);
  const [selectedTier, setSelectedTier] = useState<SubscriptionTier | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<Duration>(1);
  const [selectedCurrency, setSelectedCurrency] = useState<'ton' | 'usdt'>('usdt');
  const [paymentData, setPaymentData] = useState<any>(null);
  const [isSendingPayment, setIsSendingPayment] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [pollingAttempts, setPollingAttempts] = useState(0);

  // TON Connect hook
  const {
    sendTonPayment,
    sendUsdtPayment,
    isLoading: isTonLoading,
    isConnected: isTonConnected,
    wallet,
  } = useTonPayment();

  // Reset state when modal closes
  const handleClose = () => {
    setStep(1);
    setPaymentProvider(null);
    setSelectedTier(null);
    setSelectedDuration(1);
    onClose();
  };

  // Calculate price with discount
  const calculatePrice = (basePrice: number): number => {
    const discountAmount = basePrice * (referralDiscount / 100);
    return basePrice - discountAmount;
  };

  // Get selected plan
  const selectedPlan = PLAN_OPTIONS.find((p) => p.tier === selectedTier);

  // Get base price based on duration
  const getBasePrice = (): number => {
    if (!selectedPlan) return 0;
    if (selectedDuration === 1) return selectedPlan.pricing.monthly;
    if (selectedDuration === 3) return selectedPlan.pricing.quarterly;
    return selectedPlan.pricing.yearly;
  };

  const finalPrice = calculatePrice(getBasePrice());

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

    try {
      // Import api client dynamically to avoid SSR issues
      const { api } = await import('@/shared/api/client');

      if (paymentProvider === 'telegram_stars') {
        // Create Telegram Stars invoice via backend
        toast.loading('Creating invoice...');

        const response = await api.payment.createStarsInvoice({
          tier: selectedTier,
          duration_months: selectedDuration,
        });

        if (response.success) {
          // Invoice created successfully - Telegram will handle the payment flow
          toast.dismiss();
          toast.success('Invoice sent! Complete payment in Telegram');
          onSuccess?.();
          onClose();
        } else {
          toast.dismiss();
          toast.error(response.error || 'Failed to create invoice');
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

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4"
      onClick={handleClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="glassmorphism-card rounded-2xl p-6 max-w-md w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-white font-bold text-xl">{t('premium.title')}</h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Progress Indicator */}
        <div className="flex gap-2 mb-6">
          {(paymentProvider === 'ton_connect' ? [1, 2, 3, 4] : [1, 2, 3]).map((s) => (
            <div
              key={s}
              className={`flex-1 h-1 rounded-full transition-colors ${
                s <= step ? 'bg-blue-500' : 'bg-gray-700'
              }`}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          {/* Step 1: Payment Method Selection */}
          {step === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h3 className="text-white font-bold text-lg mb-4">{t('premium.payment_methods.title')}</h3>

              <div className="space-y-3 mb-6">
                {/* Telegram Stars */}
                <button
                  onClick={() => setPaymentProvider('telegram_stars')}
                  className={`w-full glassmorphism rounded-xl p-4 text-left transition-all ${
                    paymentProvider === 'telegram_stars'
                      ? 'ring-2 ring-blue-500 bg-blue-500/10'
                      : 'hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="text-3xl">⭐</div>
                    <div className="flex-1">
                      <div className="text-white font-medium">Telegram Stars</div>
                      <div className="text-gray-400 text-xs">
                        Native Telegram payment • Fast & secure
                      </div>
                    </div>
                    {paymentProvider === 'telegram_stars' && (
                      <div className="text-blue-500">✓</div>
                    )}
                  </div>
                </button>

                {/* TON Connect */}
                <button
                  onClick={() => setPaymentProvider('ton_connect')}
                  className={`w-full glassmorphism rounded-xl p-4 text-left transition-all ${
                    paymentProvider === 'ton_connect'
                      ? 'ring-2 ring-blue-500 bg-blue-500/10'
                      : 'hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="text-3xl">💎</div>
                    <div className="flex-1">
                      <div className="text-white font-medium">TON Connect</div>
                      <div className="text-gray-400 text-xs">
                        Pay with USDT or TON • Blockchain payment
                      </div>
                    </div>
                    {paymentProvider === 'ton_connect' && (
                      <div className="text-blue-500">✓</div>
                    )}
                  </div>
                </button>

                {/* Crypto Bot */}
                <button
                  onClick={() => setPaymentProvider('crypto_bot')}
                  className={`w-full glassmorphism rounded-xl p-4 text-left transition-all ${
                    paymentProvider === 'crypto_bot'
                      ? 'ring-2 ring-blue-500 bg-blue-500/10'
                      : 'hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="text-3xl">🤖</div>
                    <div className="flex-1">
                      <div className="text-white font-medium">Crypto Bot</div>
                      <div className="text-gray-400 text-xs">
                        Multiple crypto currencies • Anonymous
                      </div>
                    </div>
                    {paymentProvider === 'crypto_bot' && (
                      <div className="text-blue-500">✓</div>
                    )}
                  </div>
                </button>
              </div>

              <button
                onClick={() => setStep(2)}
                disabled={!paymentProvider}
                className={`w-full py-3 rounded-xl font-medium transition-all ${
                  paymentProvider
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                }`}
              >
                Continue
              </button>
            </motion.div>
          )}

          {/* Step 2: Plan Selection */}
          {step === 2 && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h3 className="text-white font-bold text-lg mb-4">{t('premium.plan_selection.title')}</h3>

              {/* Tier Selection */}
              <div className="space-y-3 mb-6">
                {PLAN_OPTIONS.map((plan) => (
                  <button
                    key={plan.tier}
                    onClick={() => setSelectedTier(plan.tier)}
                    className={`w-full glassmorphism rounded-xl p-4 text-left transition-all ${
                      selectedTier === plan.tier
                        ? 'ring-2 ring-blue-500 bg-blue-500/10'
                        : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="text-3xl">{plan.icon}</div>
                      <div className="flex-1">
                        <div className="text-white font-medium mb-1">{plan.name}</div>
                        <div className="space-y-1">
                          {plan.features.slice(0, 3).map((feature, idx) => (
                            <div key={idx} className="text-gray-400 text-xs">
                              • {feature}
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-white font-bold">
                          ${plan.pricing.monthly}
                        </div>
                        <div className="text-gray-400 text-xs">/month</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              {/* Duration Selection */}
              {selectedTier && (
                <div className="mb-6">
                  <label className="text-gray-400 text-sm mb-2 block">Duration</label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => setSelectedDuration(1)}
                      className={`py-2 rounded-xl text-sm font-medium transition-all ${
                        selectedDuration === 1
                          ? 'bg-blue-600 text-white'
                          : 'glassmorphism text-gray-400 hover:text-white'
                      }`}
                    >
                      1 Month
                    </button>
                    <button
                      onClick={() => setSelectedDuration(3)}
                      className={`py-2 rounded-xl text-sm font-medium transition-all ${
                        selectedDuration === 3
                          ? 'bg-blue-600 text-white'
                          : 'glassmorphism text-gray-400 hover:text-white'
                      }`}
                    >
                      3 Months
                    </button>
                    <button
                      onClick={() => setSelectedDuration(12)}
                      className={`py-2 rounded-xl text-sm font-medium transition-all ${
                        selectedDuration === 12
                          ? 'bg-blue-600 text-white'
                          : 'glassmorphism text-gray-400 hover:text-white'
                      }`}
                    >
                      12 Months
                    </button>
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => setStep(1)}
                  className="flex-1 py-3 rounded-xl font-medium bg-gray-700 hover:bg-gray-600 text-white transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={() => setStep(3)}
                  disabled={!selectedTier}
                  className={`flex-1 py-3 rounded-xl font-medium transition-all ${
                    selectedTier
                      ? 'bg-blue-600 hover:bg-blue-700 text-white'
                      : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                  }`}
                >
                  Continue
                </button>
              </div>
            </motion.div>
          )}

          {/* Step 3: Confirmation */}
          {step === 3 && selectedPlan && (
            <motion.div
              key="step3"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h3 className="text-white font-bold text-lg mb-4">{t('premium.confirmation.title')}</h3>

              {/* Order Summary */}
              <div className="glassmorphism rounded-xl p-4 mb-4">
                <div className="flex items-center gap-3 mb-3 pb-3 border-b border-gray-700">
                  <div className="text-3xl">{selectedPlan.icon}</div>
                  <div>
                    <div className="text-white font-medium">{selectedPlan.name} Plan</div>
                    <div className="text-gray-400 text-sm">
                      {selectedDuration} {selectedDuration === 1 ? 'Month' : 'Months'}
                    </div>
                  </div>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Base Price</span>
                    <span className="text-white">${getBasePrice().toFixed(2)}</span>
                  </div>

                  {getDurationDiscount() > 0 && (
                    <div className="flex justify-between text-green-400">
                      <span>Plan Discount ({getDurationDiscount()}%)</span>
                      <span>-${(getBasePrice() * (getDurationDiscount() / 100)).toFixed(2)}</span>
                    </div>
                  )}

                  {referralDiscount > 0 && (
                    <div className="flex justify-between text-green-400">
                      <span>Referral Discount ({referralDiscount}%)</span>
                      <span>-${(getBasePrice() * (referralDiscount / 100)).toFixed(2)}</span>
                    </div>
                  )}

                  <div className="flex justify-between pt-2 border-t border-gray-700">
                    <span className="text-white font-bold">Total</span>
                    <div className="text-right">
                      <div className="text-white font-bold">${finalPrice.toFixed(2)}</div>
                      {paymentProvider === 'telegram_stars' && (
                        <div className="text-gray-400 text-xs">
                          ≈ {usdToStars(finalPrice)} ⭐ Stars
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Payment Method Display */}
              <div className="glassmorphism rounded-xl p-3 mb-4">
                <div className="text-gray-400 text-xs mb-1">Payment Method</div>
                <div className="text-white font-medium">
                  {paymentProvider === 'telegram_stars' && '⭐ Telegram Stars'}
                  {paymentProvider === 'ton_connect' && '💎 TON Connect'}
                  {paymentProvider === 'crypto_bot' && '🤖 Crypto Bot'}
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setStep(2)}
                  className="flex-1 py-3 rounded-xl font-medium bg-gray-700 hover:bg-gray-600 text-white transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={handlePayment}
                  className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white py-3 rounded-xl font-medium transition-all"
                >
                  Pay ${finalPrice.toFixed(2)}
                </button>
              </div>
            </motion.div>
          )}

          {/* Step 4: TON Connect Payment */}
          {step === 4 && paymentData && (
            <motion.div
              key="step4"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="space-y-4"
            >
              <h3 className="text-white font-bold text-lg mb-4">{t('premium.ton_payment.title')}</h3>

              {/* Currency Selection */}
              <div className="space-y-3">
                <label className="text-gray-400 text-sm">{t('premium.ton_payment.select_currency')}</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setSelectedCurrency('usdt')}
                    className={`glassmorphism rounded-xl p-4 transition-all ${
                      selectedCurrency === 'usdt'
                        ? 'ring-2 ring-blue-500 bg-blue-500/10'
                        : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="text-center">
                      <div className="text-2xl mb-1">💵</div>
                      <div className="text-white font-medium">USDT</div>
                      <div className="text-gray-400 text-xs">{paymentData.amount_usdt} USDT</div>
                    </div>
                  </button>
                  <button
                    onClick={() => setSelectedCurrency('ton')}
                    className={`glassmorphism rounded-xl p-4 transition-all ${
                      selectedCurrency === 'ton'
                        ? 'ring-2 ring-blue-500 bg-blue-500/10'
                        : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="text-center">
                      <div className="text-2xl mb-1">💎</div>
                      <div className="text-white font-medium">TON</div>
                      <div className="text-gray-400 text-xs">{paymentData.amount_ton.toFixed(2)} TON</div>
                    </div>
                  </button>
                </div>
              </div>

              {/* TON Connect Button */}
              <div className="glassmorphism rounded-xl p-4">
                <div className="text-gray-400 text-sm mb-3">Connect Your Wallet</div>
                <TonConnectButton />
              </div>

              {/* Payment Details (shown when wallet connected) */}
              {isTonConnected && wallet && (
                <div className="glassmorphism rounded-xl p-4 space-y-3">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="text-green-400">✓</div>
                    <div className="text-white font-medium">Wallet Connected</div>
                  </div>

                  <div className="text-xs text-gray-400 space-y-2">
                    <div className="flex justify-between">
                      <span>Wallet:</span>
                      <span className="font-mono">{wallet.account.address.slice(0, 6)}...{wallet.account.address.slice(-4)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Amount:</span>
                      <span className="text-white">
                        {selectedCurrency === 'usdt'
                          ? `${paymentData.amount_usdt} USDT`
                          : `${paymentData.amount_ton.toFixed(2)} TON`
                        }
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Memo:</span>
                      <span className="font-mono text-blue-400">{paymentData.memo}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Info Message */}
              {!isTonConnected && (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-3">
                  <p className="text-yellow-400 text-xs">
                    ⚠️ Connect your TON wallet (Tonkeeper, MyTonWallet, etc.) to send payment
                  </p>
                </div>
              )}

              {selectedCurrency === 'usdt' && isTonConnected && (
                <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-3">
                  <p className="text-blue-400 text-xs">
                    ℹ️ USDT transfer requires ~0.1 TON for gas fees
                  </p>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => setStep(3)}
                  className="flex-1 glassmorphism hover:bg-white/5 text-white py-3 rounded-xl font-medium transition-all"
                >
                  Back
                </button>
                <button
                  onClick={handleSendTonPayment}
                  disabled={!isTonConnected || isSendingPayment || isPolling}
                  className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-3 rounded-xl font-medium transition-all"
                >
                  {isSendingPayment ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      Sending...
                    </span>
                  ) : isPolling ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      Confirming... ({pollingAttempts}/36)
                    </span>
                  ) : (
                    `Send ${selectedCurrency === 'usdt' ? `${paymentData.amount_usdt} USDT` : `${paymentData.amount_ton.toFixed(2)} TON`}`
                  )}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
