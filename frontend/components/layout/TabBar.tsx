/**
 * TabBar Component
 * Нижняя навигация с анимированными табами
 */

'use client';

import { motion } from 'framer-motion';
import { usePathname, useRouter } from 'next/navigation';
import { vibrate } from '@/shared/telegram/vibration';

interface Tab {
  key: string;
  label: string;
  icon: React.ReactNode;
  path: string;
}

const tabs: Tab[] = [
  {
    key: 'home',
    label: 'Home',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" />
      </svg>
    ),
    path: '/',
  },
  {
    key: 'chat',
    label: 'AI Chat',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
      </svg>
    ),
    path: '/chat',
  },
  {
    key: 'analytics',
    label: 'Analytics',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M3 13h2v8H3zm4-6h2v14H7zm4-4h2v18h-2zm4 9h2v9h-2zm4-5h2v14h-2z" />
      </svg>
    ),
    path: '/analytics',
  },
  {
    key: 'profile',
    label: 'Profile',
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

  const handleTabClick = (tab: Tab) => {
    vibrate('light');
    router.push(tab.path);
  };

  return (
    <div
      className="fixed left-1/2 -translate-x-1/2 w-[90%] max-w-[520px] z-50"
      style={{
        bottom: 'max(env(safe-area-inset-bottom, 16px), 16px)',
      }}
    >
      <div className="glassmorphism-card rounded-3xl p-1">
        <div className="flex">
          {tabs.map((tab) => {
            const isActive = pathname === tab.path;

            return (
              <div key={tab.key} className="flex-1 relative">
                {/* Animated active indicator */}
                {isActive && (
                  <motion.div
                    className="absolute inset-0 glassmorphism-button rounded-2xl"
                    layoutId="activeTab"
                    transition={{ type: 'spring', duration: 0.3 }}
                  />
                )}

                <button
                  onClick={() => handleTabClick(tab)}
                  className={`
                    relative w-full py-3 px-2 text-center
                    transition-all duration-200 rounded-2xl
                    flex flex-col items-center justify-center gap-1
                    ${isActive ? 'text-white z-10' : 'text-gray-400 hover:text-gray-200'}
                  `}
                >
                  {tab.icon}
                  <span className="text-[10px] font-semibold">{tab.label}</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
