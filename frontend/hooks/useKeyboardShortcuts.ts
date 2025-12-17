/**
 * Keyboard Shortcuts Hook
 * ChatGPT-style keyboard shortcuts для desktop
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { usePlatform } from '@/lib/platform';

interface ShortcutConfig {
  key: string;
  ctrl?: boolean;
  meta?: boolean; // Cmd на Mac
  shift?: boolean;
  handler: () => void;
  description: string;
}

export function useKeyboardShortcuts() {
  const router = useRouter();
  const { platformType, platform } = usePlatform();

  const isDesktop = platformType === 'web';

  useEffect(() => {
    // Только для desktop
    if (!isDesktop) return;

    const shortcuts: ShortcutConfig[] = [
      // Cmd/Ctrl + K - Focus search (будет реализовано позже)
      {
        key: 'k',
        meta: true,
        ctrl: true,
        handler: () => {
          console.log('🔍 Focus search (not implemented yet)');
          platform?.ui.haptic?.impact('light');
          // TODO: Focus search input
        },
        description: 'Focus search',
      },

      // Cmd/Ctrl + N - New chat
      {
        key: 'n',
        meta: true,
        ctrl: true,
        handler: () => {
          console.log('💬 New chat');
          platform?.ui.haptic?.impact('medium');
          router.push('/chat');
          // TODO: Clear chat history
        },
        description: 'New chat',
      },

      // Cmd/Ctrl + / - Show shortcuts help
      {
        key: '/',
        meta: true,
        ctrl: true,
        handler: () => {
          console.log('❓ Show shortcuts help');
          platform?.ui.haptic?.impact('light');
          // TODO: Show shortcuts modal
          alert(
            'Keyboard Shortcuts:\n\n' +
              '⌘ + K / Ctrl + K - Focus search\n' +
              '⌘ + N / Ctrl + N - New chat\n' +
              '⌘ + / / Ctrl + / - Show this help\n' +
              '⌘ + 1 / Ctrl + 1 - Chat\n' +
              '⌘ + 2 / Ctrl + 2 - Home\n' +
              '⌘ + 3 / Ctrl + 3 - Profile'
          );
        },
        description: 'Show shortcuts',
      },

      // Cmd/Ctrl + 1 - Go to Chat
      {
        key: '1',
        meta: true,
        ctrl: true,
        handler: () => {
          console.log('💬 Navigate to Chat');
          platform?.ui.haptic?.impact('light');
          router.push('/chat');
        },
        description: 'Go to Chat',
      },

      // Cmd/Ctrl + 2 - Go to Home
      {
        key: '2',
        meta: true,
        ctrl: true,
        handler: () => {
          console.log('🏠 Navigate to Home');
          platform?.ui.haptic?.impact('light');
          router.push('/home');
        },
        description: 'Go to Home',
      },

      // Cmd/Ctrl + 3 - Go to Profile
      {
        key: '3',
        meta: true,
        ctrl: true,
        handler: () => {
          console.log('👤 Navigate to Profile');
          platform?.ui.haptic?.impact('light');
          router.push('/profile');
        },
        description: 'Go to Profile',
      },
    ];

    const handleKeyDown = (e: KeyboardEvent) => {
      // Игнорировать если пользователь печатает в input/textarea
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        // Но разрешить некоторые shortcuts в input
        if (!['k', 'n', '/'].includes(e.key)) {
          return;
        }
      }

      // Проверяем каждый shortcut
      for (const shortcut of shortcuts) {
        const keyMatch = e.key.toLowerCase() === shortcut.key.toLowerCase();
        const metaMatch = shortcut.meta ? e.metaKey : true;
        const ctrlMatch = shortcut.ctrl ? e.ctrlKey : true;
        const shiftMatch = shortcut.shift ? e.shiftKey : !e.shiftKey;

        // Для shortcuts с meta или ctrl - проверяем что один из них нажат
        if (shortcut.meta || shortcut.ctrl) {
          const modifierPressed = e.metaKey || e.ctrlKey;
          if (keyMatch && modifierPressed && shiftMatch) {
            e.preventDefault();
            shortcut.handler();
            return;
          }
        } else if (keyMatch && metaMatch && ctrlMatch && shiftMatch) {
          e.preventDefault();
          shortcut.handler();
          return;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    // Cleanup
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isDesktop, router, platform]);

  return {
    isEnabled: isDesktop,
  };
}

/**
 * Показать доступные shortcuts
 */
export function getAvailableShortcuts() {
  return [
    { keys: ['⌘', 'K'], description: 'Focus search' },
    { keys: ['⌘', 'N'], description: 'New chat' },
    { keys: ['⌘', '/'], description: 'Show shortcuts' },
    { keys: ['⌘', '1'], description: 'Go to Chat' },
    { keys: ['⌘', '2'], description: 'Go to Home' },
    { keys: ['⌘', '3'], description: 'Go to Profile' },
  ];
}
