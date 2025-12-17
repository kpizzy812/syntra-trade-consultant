/**
 * TabBar Component
 * Нижняя навигация с анимированными табами
 * Показывается только на mobile/Telegram, скрыт на desktop
 */

'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { vibrate } from '@/shared/telegram/vibration';
import { usePlatform } from '@/lib/platform';
import { useKeyboardVisible } from '@/hooks/useKeyboardVisible';

interface Tab {
  key: 'home' | 'chat' | 'tasks' | 'referral' | 'profile';
  icon: React.ReactNode;
  path: string;
}

const tabsConfig: Tab[] = [
  {
    key: 'home',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" />
      </svg>
    ),
    path: '/home',
  },
  {
    key: 'chat',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
      </svg>
    ),
    path: '/chat',
  },
  {
    key: 'tasks',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9 14l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
      </svg>
    ),
    path: '/tasks',
  },
  {
    key: 'referral',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" />
      </svg>
    ),
    path: '/referral',
  },
  {
    key: 'profile',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
      </svg>
    ),
    path: '/profile',
  },
];

export default function TabBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { platformType } = usePlatform();
  const t = useTranslations('nav');
  const isKeyboardVisible = useKeyboardVisible();

  // Hide TabBar on desktop - Sidebar используется вместо этого
  const isDesktop = platformType === 'web';
  if (isDesktop) {
    return null;
  }

  const handleTabClick = (tab: Tab) => {
    vibrate('light');
    router.push(tab.path);
  };

  return (
    <div
      className={`
        fixed bottom-0 left-0 right-0 z-50
        border-t border-white/5 bg-black/95 backdrop-blur-lg
        transition-transform duration-300 ease-in-out
        ${isKeyboardVisible ? 'translate-y-full' : 'translate-y-0'}
      `}
      style={{
        paddingBottom: 'max(env(safe-area-inset-bottom), 0.5rem)',
      }}
    >
      <div className="flex">
        {tabsConfig.map((tab) => {
          const isActive = pathname === tab.path;

          return (
            <button
              key={tab.key}
              onClick={() => handleTabClick(tab)}
              className={`
                flex-1 py-3 px-2
                transition-colors duration-200
                flex flex-col items-center justify-center gap-1
                ${isActive ? 'text-blue-500' : 'text-gray-500 hover:text-gray-300'}
              `}
            >
              <div className="transition-transform active:scale-90">
                {tab.icon}
              </div>
              <span className="text-[10px] font-medium">{t(tab.key)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
