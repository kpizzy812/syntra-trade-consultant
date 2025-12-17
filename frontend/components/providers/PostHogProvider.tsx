'use client'

import { useEffect } from 'react'
import { usePathname, useSearchParams } from 'next/navigation'
import posthog from 'posthog-js'

// Initialize PostHog once when the module loads
if (typeof window !== 'undefined') {
  const posthogKey = process.env.NEXT_PUBLIC_POSTHOG_KEY
  const posthogHost = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com'
  const isDev = process.env.NODE_ENV === 'development'

  // Проверяем, не был ли PostHog уже инициализирован
  // В dev режиме полностью отключаем PostHog чтобы не видеть ошибки блокировки
  if (posthogKey && !posthog.__loaded && !isDev) {
    try {
      posthog.init(posthogKey, {
        api_host: posthogHost,
        autocapture: false, // Disable autocapture, we'll manually track events
        capture_pageview: false, // Disable automatic pageview tracking

        // Обработка ошибок при блокировке - молча игнорируем
        on_request_error: () => {
          // Не логируем ошибки - они замусоривают консоль
        },

        // Таймауты для предотвращения бесконечных retry
        feature_flag_request_timeout_ms: 3000,

        // Дополнительные настройки для graceful degradation
        advanced_disable_decide: false, // Включаем feature flags
        persistence: 'localStorage+cookie', // Кэшируем в localStorage

        // В dev режиме отключаем некоторые фичи для уменьшения запросов
        disable_session_recording: isDev,
        disable_surveys: isDev,

        loaded: () => {
          if (process.env.NODE_ENV === 'production') {
            console.log('✅ PostHog initialized in production')
          }
        }
      })
    } catch {
      // Если PostHog полностью заблокирован - молча игнорируем
      console.warn('⚠️ PostHog initialization failed (possibly blocked by adblocker)')
    }
  } else if (isDev) {
    console.log('🔕 PostHog отключен в dev режиме (чтобы избежать ошибок блокировщика рекламы)')
  }
}

export function PostHogPageView() {
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (pathname && posthog.__loaded) {
      try {
        let url = window.origin + pathname
        if (searchParams && searchParams.toString()) {
          url = url + `?${searchParams.toString()}`
        }

        posthog.capture('$pageview', {
          $current_url: url,
        })
      } catch {
        // Молча игнорируем ошибки при отправке событий
        // (например, если PostHog заблокирован)
      }
    }
  }, [pathname, searchParams])

  return null
}

// Интерфейс для безопасной обёртки PostHog
interface SafePostHog {
  __loaded: boolean
  capture: (event: string, properties?: Record<string, unknown>) => unknown
  identify: (distinctId: string, properties?: Record<string, unknown>) => void
  reset: () => void
  isFeatureEnabled: (flag: string) => boolean | undefined
  getFeatureFlag: (flag: string) => string | boolean | undefined
}

// Безопасная обёртка над PostHog API
const safePostHog: SafePostHog = {
  get __loaded() {
    try {
      return posthog.__loaded || false
    } catch {
      return false
    }
  },
  capture: (event: string, properties?: Record<string, unknown>) => {
    try {
      if (posthog.__loaded) {
        return posthog.capture(event, properties)
      }
    } catch {
      // Молча игнорируем ошибки
    }
  },
  identify: (distinctId: string, properties?: Record<string, unknown>) => {
    try {
      if (posthog.__loaded) {
        return posthog.identify(distinctId, properties)
      }
    } catch {
      // Молча игнорируем ошибки
    }
  },
  reset: () => {
    try {
      if (posthog.__loaded) {
        return posthog.reset()
      }
    } catch {
      // Молча игнорируем ошибки
    }
  },
  isFeatureEnabled: (flag: string) => {
    try {
      if (posthog.__loaded) {
        return posthog.isFeatureEnabled(flag)
      }
    } catch {
      // Молча игнорируем ошибки
    }
    return false
  },
  getFeatureFlag: (flag: string) => {
    try {
      if (posthog.__loaded) {
        return posthog.getFeatureFlag(flag)
      }
    } catch {
      // Молча игнорируем ошибки
    }
    return undefined
  },
}

// Хук для удобного использования PostHog в компонентах
export function usePostHog() {
  return safePostHog
}
