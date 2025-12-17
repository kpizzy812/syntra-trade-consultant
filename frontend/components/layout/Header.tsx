/**
 * Header Component
 * Адаптивный header: full-width на desktop, centered на mobile
 * Поддерживает кастомные заголовки и кнопку назад
 * Mobile (web): Hamburger menu слева для открытия sidebar
 */

'use client';

import { useRouter } from 'next/navigation';
import { useUserStore } from '@/shared/store/userStore';
import { usePlatform } from '@/lib/platform';
import LanguageSwitcher from '@/components/layout/LanguageSwitcher';
import PointsBalance from '@/components/points/PointsBalance';
import { useSidebar } from './DesktopLayout';
import { vibrate } from '@/shared/telegram/vibration';

// Safe wrapper для useSidebar (может быть не в контексте DesktopLayout)
function useSidebarSafe() {
  try {
    return useSidebar();
  } catch {
    return null;
  }
}

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
  const { platformType } = usePlatform();

  const isDesktop = platformType === 'web';
  const sidebar = useSidebarSafe();

  const handleBack = () => {
    vibrate('light');
    if (onBack) {
      onBack();
    } else {
      router.back();
    }
  };

  return (
    <header className="border-b border-white/5 bg-black/80 backdrop-blur-lg px-4 py-1.5 lg:px-6">
      <div
        className={`
        flex items-center justify-between
        ${isDesktop ? 'max-w-full' : 'max-w-[520px] mx-auto'}
      `}
      >
        {/* Left Section */}
        <div className="flex items-center gap-3">
          {/* Hamburger Menu Button (Mobile Web Only) */}
          {isDesktop && sidebar && (
            <button
              onClick={() => { vibrate('light'); sidebar.toggleSidebar(); }}
              className="lg:hidden p-2 -ml-2 rounded-lg hover:bg-white/5 transition-colors"
              aria-label="Toggle sidebar"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="text-gray-400"
              >
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
          )}

          {/* Back Button (если showBack=true) */}
          {showBack && (
            <button
              onClick={handleBack}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
            </button>
          )}

          {/* Syntra AI Title - показываем на мобилке web */}
          {isDesktop && (
            <span className="text-white font-semibold text-base lg:hidden">Syntra AI</span>
          )}

          {/* Original Title - показываем на desktop или если не web */}
          {(!isDesktop || title) && (
            <span className="text-white font-semibold text-sm hidden lg:block">{title || 'Syntra AI'}</span>
          )}
        </div>

        {/* Right Section: Points Balance and Language Switcher */}
        <div className="flex items-center gap-2.5">
          {/* Language Switcher */}
          <LanguageSwitcher />

          {/* $SYNTRA Points Balance */}
          {user && showBalance && (
            <PointsBalance />
          )}
        </div>
      </div>
    </header>
  );
}
