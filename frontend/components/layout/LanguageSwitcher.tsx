/**
 * LanguageSwitcher - Компонент переключения языка
 * Круглая кнопка с полностью залитым флагом
 * Красивая spring анимация dropdown с stagger эффектом
 * Синхронизация с бэкендом для сохранения предпочтений пользователя
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { setLocaleCookie, getPreferredLocale } from '@/shared/lib/locale';
import { api } from '@/shared/api/client';
import { useUserStore } from '@/shared/store/userStore';
import type { Locale } from '@/i18n';
import { vibrate, vibrateSelection } from '@/shared/telegram/vibration';

interface LanguageSwitcherProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const LANGUAGE_FLAGS = {
  en: '/icons/en.svg',
  ru: '/icons/ru.svg',
} as const;

const LANGUAGE_NAMES = {
  en: 'English',
  ru: 'Русский',
} as const;

const LANGUAGES: Locale[] = ['en', 'ru'];

export default function LanguageSwitcher({
  className = '',
  size = 'md'
}: LanguageSwitcherProps) {
  const [currentLocale, setCurrentLocale] = useState<Locale>('en');
  const [isOpen, setIsOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [mounted, setMounted] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 });
  const { user, setUser } = useUserStore();

  // Размеры кнопки в зависимости от size prop (уменьшены)
  const buttonSize = {
    sm: 28,
    md: 32,
    lg: 38,
  }[size];

  // Инициализация - определяем текущий язык
  useEffect(() => {
    const locale = getPreferredLocale();
    setCurrentLocale(locale);
    setMounted(true);
  }, []);

  // Функция обновления позиции dropdown
  const updateDropdownPosition = () => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();

    setDropdownPosition({
      top: rect.bottom,                // ровно под кнопкой
      left: rect.left + rect.width / 2 // центр по X
    });
  };

  // Обновляем позицию при открытии + на скролл/ресайз
  useEffect(() => {
    if (!isOpen) return;

    updateDropdownPosition();

    const handleScrollOrResize = () => updateDropdownPosition();

    window.addEventListener('scroll', handleScrollOrResize, true);
    window.addEventListener('resize', handleScrollOrResize);

    return () => {
      window.removeEventListener('scroll', handleScrollOrResize, true);
      window.removeEventListener('resize', handleScrollOrResize);
    };
  }, [isOpen]);

  // Закрытие dropdown при клике вне компонента
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Переключение языка
  const handleLanguageChange = async (newLocale: Locale) => {
    if (isUpdating || newLocale === currentLocale) return;

    setIsUpdating(true);
    setCurrentLocale(newLocale);
    setLocaleCookie(newLocale);
    setIsOpen(false);

    try {
      // Отправить запрос на бэкенд для сохранения языка (только для залогиненных)
      if (user) {
        await api.profile.updateSettings({ language: newLocale });

        // Обновить user store
        if (setUser) {
          setUser({ ...user, language: newLocale });
        }

        console.log('✅ Language preference saved to backend:', newLocale);
      } else {
        console.log('ℹ️ Language saved locally (user not logged in)');
      }
    } catch (error) {
      console.error('❌ Failed to save language preference to backend:', error);
      // Продолжаем даже если бэкенд запрос упал - локаль уже сохранена в cookie
    } finally {
      setIsUpdating(false);
    }

    // Обновляем URL параметр ?lang= перед перезагрузкой
    const url = new URL(window.location.href);
    url.searchParams.set('lang', newLocale);

    // Перезагружаем страницу с новым параметром lang
    window.location.href = url.toString();
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Круглая кнопка с полностью залитым флагом */}
      <motion.button
        ref={buttonRef}
        onClick={() => { vibrate('light'); setIsOpen(!isOpen); }}
        disabled={isUpdating}
        className="relative overflow-hidden"
        style={{
          width: buttonSize,
          height: buttonSize,
          borderRadius: '50%',
          border: '2px solid rgba(255, 255, 255, 0.15)',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05)',
        }}
        whileHover={{
          scale: isUpdating ? 1 : 1.08,
          borderColor: 'rgba(255, 255, 255, 0.3)',
          boxShadow: '0 6px 20px rgba(0, 0, 0, 0.5), 0 0 0 2px rgba(255, 255, 255, 0.1)',
        }}
        whileTap={{ scale: isUpdating ? 1 : 0.95 }}
        title={LANGUAGE_NAMES[currentLocale]}
      >
        {/* Флаг как фон - полностью заполняет круг */}
        <div
          className="absolute inset-0 w-full h-full"
          style={{
            backgroundImage: `url(${LANGUAGE_FLAGS[currentLocale]})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            borderRadius: '50%',
          }}
        />

        {/* Градиентный overlay для глубины */}
        <div
          className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/10"
          style={{ borderRadius: '50%' }}
        />
      </motion.button>

      {/* Dropdown с выбором языка - через Portal */}
      {mounted && createPortal(
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10, transition: { duration: 0.15 } }}
              transition={{
                type: 'spring',
                stiffness: 300,
                damping: 24,
                mass: 0.8,
              }}
              className="rounded-2xl overflow-hidden p-2"
              style={{
                position: 'fixed',
                top: `${dropdownPosition.top}px`,
                left: `${dropdownPosition.left}px`,
                transform: 'translate(-50%, 8px)', // 8px вниз от нижней грани кнопки
                width: buttonSize + 10,
                zIndex: 999999,
                background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.1) 100%)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
                border: '1px solid rgba(59, 130, 246, 0.2)',
                boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(59, 130, 246, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
                pointerEvents: 'auto',
              }}
            >
            <motion.div
              initial="closed"
              animate="open"
              exit="closed"
              variants={{
                open: {
                  transition: {
                    staggerChildren: 0.05,
                    delayChildren: 0.1,
                  }
                },
                closed: {
                  transition: {
                    staggerChildren: 0.03,
                    staggerDirection: -1,
                  }
                }
              }}
            >
              {LANGUAGES.map((locale) => {
                const isActive = locale === currentLocale;

                return (
                  <motion.button
                    key={locale}
                    onClick={() => { vibrateSelection(); handleLanguageChange(locale); }}
                    variants={{
                      open: {
                        opacity: 1,
                        y: 0,
                        transition: {
                          type: 'spring',
                          stiffness: 300,
                          damping: 24,
                        }
                      },
                      closed: {
                        opacity: 0,
                        y: -10,
                      }
                    }}
                    className="relative p-1 rounded-full transition-all duration-200 flex items-center justify-center w-full"
                    style={{
                      backgroundColor: isActive ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                    }}
                    whileHover={{
                      scale: 1.1,
                      backgroundColor: isActive ? 'rgba(59, 130, 246, 0.25)' : 'rgba(255, 255, 255, 0.1)',
                    }}
                    whileTap={{ scale: 0.95 }}
                    title={LANGUAGE_NAMES[locale]}
                  >
                    {/* Круглый флаг */}
                    <div
                      className="relative overflow-hidden shrink-0"
                      style={{
                        width: 30,
                        height: 30,
                        borderRadius: '50%',
                        border: isActive ? '2px solid rgba(59, 130, 246, 0.5)' : '2px solid rgba(255, 255, 255, 0.2)',
                        boxShadow: isActive
                          ? '0 4px 12px rgba(59, 130, 246, 0.4), 0 0 0 1px rgba(59, 130, 246, 0.2)'
                          : '0 2px 8px rgba(0, 0, 0, 0.3)',
                      }}
                    >
                      <div
                        className="absolute inset-0 w-full h-full"
                        style={{
                          backgroundImage: `url(${LANGUAGE_FLAGS[locale]})`,
                          backgroundSize: 'cover',
                          backgroundPosition: 'center',
                        }}
                      />

                      {/* Галочка для активного языка */}
                      {isActive && (
                        <motion.div
                          initial={{ scale: 0, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          transition={{
                            type: 'spring',
                            stiffness: 400,
                            damping: 20,
                          }}
                          className="absolute inset-0 flex items-center justify-center"
                          style={{
                            background: 'rgba(0, 0, 0, 0.4)',
                            backdropFilter: 'blur(2px)',
                          }}
                        >
                          <svg
                            className="w-5 h-5 text-white drop-shadow-lg"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </motion.div>
                      )}
                    </div>
                  </motion.button>
                );
              })}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>,
      document.body
      )}
    </div>
  );
}
