'use client';

import { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { getPreferredLocale } from '@/shared/lib/locale';
import { api } from '@/shared/api/client';

function VerifyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [error, setError] = useState('');
  const verificationAttempted = useRef(false);
  // Lazy initialization - определяем язык один раз при создании компонента
  const [language] = useState<'en' | 'ru'>(() => {
    const detectedLang = getPreferredLocale();
    console.log('🌍 Detected language for verification:', detectedLang);
    return detectedLang;
  });

  // Simple translations
  const t = {
    en: {
      verifying: 'Verifying...',
      verifyingDesc: 'Please wait, we are verifying your link',
      success: 'Success!',
      successDesc: 'You are signed in. Redirecting...',
      errorTitle: 'Verification error',
      invalidToken: 'Invalid magic link - no token provided',
      possibleReasons: 'Possible reasons:',
      linkUsed: 'Link has already been used',
      linkExpired: 'Link has expired (15 minutes from sending)',
      linkCorrupted: 'Link is corrupted or incomplete',
      requestNew: 'Request a new link',
      backToChoice: '← Back to method selection',
    },
    ru: {
      verifying: 'Проверяем...',
      verifyingDesc: 'Пожалуйста, подождите, мы проверяем вашу ссылку',
      success: 'Успешно!',
      successDesc: 'Вы вошли в систему. Перенаправляем...',
      errorTitle: 'Ошибка верификации',
      invalidToken: 'Неверная magic link - токен не предоставлен',
      possibleReasons: 'Возможные причины:',
      linkUsed: 'Ссылка уже была использована',
      linkExpired: 'Ссылка истекла (15 минут с момента отправки)',
      linkCorrupted: 'Ссылка повреждена или неполная',
      requestNew: 'Запросить новую ссылку',
      backToChoice: '← Назад к выбору метода',
    },
  }[language];

  // Effect для верификации токена - выполняется только один раз
  useEffect(() => {
    // Защита от повторных вызовов (React Strict Mode, быстрые ремаунты)
    if (verificationAttempted.current) {
      return;
    }

    const token = searchParams.get('token');

    if (!token) {
      setStatus('error');
      setError(language === 'ru'
        ? 'Неверная magic link - токен не предоставлен'
        : 'Invalid magic link - no token provided'
      );
      return;
    }

    verificationAttempted.current = true;

    const verifyToken = async () => {
      try {
        const data = await api.auth.verifyMagicLink(token);

        if (data.success) {
          localStorage.setItem('auth_token', data.token);
          localStorage.setItem('user', JSON.stringify(data.user));
          setStatus('success');

          setTimeout(() => {
            router.push('/chat');
          }, 2000);
        } else {
          setStatus('error');
          setError('Verification failed');
        }
      } catch (err: any) {
        setStatus('error');

        console.error('Verification error:', {
          status: err?.response?.status,
          detail: err?.response?.data?.detail,
          message: err?.message,
          token: token?.substring(0, 10) + '...'
        });

        let errorMessage = t.invalidToken;

        if (err?.response?.status === 400) {
          errorMessage = err?.response?.data?.detail || t.linkExpired;
        } else if (err?.response?.status === 401) {
          errorMessage = err?.response?.data?.detail || t.linkUsed;
        } else if (err?.message?.includes('Network')) {
          errorMessage = language === 'ru'
            ? 'Ошибка сети. Проверьте подключение к интернету.'
            : 'Network error. Please check your internet connection.';
        } else if (err?.response?.data?.detail) {
          errorMessage = err.response.data.detail;
        }

        setError(errorMessage);
      }
    };

    verifyToken();
  }, [searchParams, router, t, language]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-gray-800 to-black px-4">
      <div className="max-w-md w-full space-y-8 bg-gray-800/50 p-8 rounded-2xl shadow-2xl border border-gray-700 text-center">
        {status === 'verifying' && (
          <>
            {/* Loading Spinner */}
            <div className="mx-auto flex items-center justify-center h-16 w-16 mb-4">
              <svg className="animate-spin h-16 w-16 text-cyan-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>

            <h2 className="text-2xl font-bold text-white mt-4">
              {t.verifying}
            </h2>
            <p className="text-gray-400">
              {t.verifyingDesc}
            </p>
          </>
        )}

        {status === 'success' && (
          <>
            {/* Success Icon */}
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-500/20 mb-4">
              <svg className="h-10 w-10 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            </div>

            <h2 className="text-2xl font-bold text-white mt-4">
              {t.success}
            </h2>
            <p className="text-gray-400 mb-4">
              {t.successDesc}
            </p>

            {/* Progress bar */}
            <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
              <div className="bg-gradient-to-r from-cyan-400 to-blue-500 h-2 rounded-full animate-pulse" style={{ width: '100%' }}></div>
            </div>
          </>
        )}

        {status === 'error' && (
          <>
            {/* Error Icon */}
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-red-500/20 mb-4">
              <svg className="h-10 w-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>

            <h2 className="text-2xl font-bold text-white mt-4">
              {t.errorTitle}
            </h2>
            <p className="text-gray-400 mb-4">
              {error}
            </p>

            {/* Common errors explanation */}
            <div className="bg-gray-900/50 p-4 rounded-lg mb-6 text-left">
              <p className="text-sm text-gray-300 mb-2">
                {t.possibleReasons}
              </p>
              <ul className="text-xs text-gray-500 space-y-1 list-disc list-inside">
                <li>{t.linkUsed}</li>
                <li>{t.linkExpired}</li>
                <li>{t.linkCorrupted}</li>
              </ul>
            </div>

            <button
              onClick={() => router.push('/auth/login')}
              className="w-full px-4 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 text-white rounded-lg hover:from-cyan-600 hover:to-blue-600 transition-all font-medium"
            >
              {t.requestNew}
            </button>

            <button
              onClick={() => router.push('/auth/choose')}
              className="mt-3 text-gray-400 hover:text-gray-300 text-sm"
            >
              {t.backToChoice}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-gray-800 to-black">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-cyan-400"></div>
      </div>
    }>
      <VerifyContent />
    </Suspense>
  );
}
