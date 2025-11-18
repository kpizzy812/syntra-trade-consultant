/**
 * Header Component
 * Верхний header с логотипом и балансом
 * Поддерживает кастомные заголовки и кнопку назад
 */

'use client';

import { useRouter } from 'next/navigation';
import { useUserStore } from '@/shared/store/userStore';
import LanguageSwitcher from '@/components/LanguageSwitcher';

interface HeaderProps {
  title?: string;
  showBack?: boolean;
  showBalance?: boolean;
  onBack?: () => void;
}

export default function Header({
  title,
  showBack = false,
  showBalance = true,
  onBack,
}: HeaderProps = {}) {
  const user = useUserStore((state) => state.user);
  const router = useRouter();

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      router.back();
    }
  };

  return (
    <header className="glassmorphism-header px-4 py-3">
      <div className="flex items-center justify-between max-w-[520px] mx-auto">
        {/* Left Section */}
        <div className="flex items-center gap-3">
          {/* Back Button (если showBack=true) */}
          {showBack && (
            <button
              onClick={handleBack}
              className="w-9 h-9 rounded-full bg-gray-800/50 hover:bg-gray-700/50 flex items-center justify-center transition-colors active:scale-95"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth="2"
              >
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
            </button>
          )}

          {/* Title или Logo */}
          {title ? (
            <h1 className="text-white font-bold text-lg">{title}</h1>
          ) : (
            <>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                <span className="text-white text-lg font-bold">S</span>
              </div>
              <div>
                <h1 className="text-white font-bold text-lg">Syntra</h1>
                <p className="text-gray-400 text-xs">AI Trade Consultant</p>
              </div>
            </>
          )}
        </div>

        {/* Right Section: Language Switcher and Balance */}
        <div className="flex items-center gap-2">
          {/* Language Switcher */}
          <LanguageSwitcher />

          {/* Balance (если пользователь авторизован и showBalance=true) */}
          {user && showBalance && user.balance !== undefined && (
            <div className="glassmorphism rounded-full px-3 py-1.5">
              <p className="text-xs text-gray-400">Balance</p>
              <p className="text-sm font-bold text-white">
                ${user.balance.toFixed(2)}
              </p>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
