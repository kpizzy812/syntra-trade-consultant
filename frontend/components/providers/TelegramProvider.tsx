'use client'

import { useEffect, useRef, createContext, useContext, ReactNode, useState } from 'react'

interface TelegramContextValue {
  isReady: boolean
  isMiniApp: boolean
  webApp: any | null
}

const TelegramContext = createContext<TelegramContextValue>({
  isReady: false,
  isMiniApp: false,
  webApp: null,
})

export const useTelegram = () => useContext(TelegramContext)

interface TelegramProviderProps {
  children: ReactNode
}

export default function TelegramProvider({ children }: TelegramProviderProps) {
  const [isReady, setIsReady] = useState(false)
  const [isMiniApp, setIsMiniApp] = useState(false)
  const [webApp, setWebApp] = useState<any | null>(null)

  // Флаг что инициализация уже выполнена
  const isInitializedRef = useRef(false)

  useEffect(() => {
    // Защита от повторной инициализации
    if (isInitializedRef.current) {
      console.log('⚠️ TelegramProvider уже инициализирован')
      return
    }

    const initTelegramApp = () => {
      try {
        // Проверяем наличие Telegram WebApp
        if (!window.Telegram?.WebApp) {
          console.log('🌐 Запуск вне Telegram Mini App')
          setIsMiniApp(false)
          setIsReady(true)
          isInitializedRef.current = true
          return
        }

        console.log('📱 Обнаружено Telegram Mini App')
        setIsMiniApp(true)

        const WebApp = window.Telegram.WebApp

        // ШАГ 1: Готовность
        WebApp.ready()
        console.log('✅ WebApp.ready()')

        // ШАГ 2: Развернуть viewport
        if (WebApp.expand) {
          WebApp.expand()
          console.log('✅ Viewport развернут')
        }

        // ШАГ 3: Настройка цветов
        if (WebApp.setHeaderColor) {
          WebApp.setHeaderColor('#000000')
        }
        if (WebApp.setBackgroundColor) {
          WebApp.setBackgroundColor('#000000')
        }

        // ШАГ 4: Подтверждение закрытия
        if (WebApp.enableClosingConfirmation) {
          WebApp.enableClosingConfirmation()
          console.log('✅ Подтверждение закрытия включено')
        }

        // ШАГ 5: Отключить вертикальные свайпы
        if (WebApp.disableVerticalSwipes) {
          WebApp.disableVerticalSwipes()
          console.log('✅ Вертикальные свайпы отключены')
        }

        console.log('📱 Telegram WebApp Info:', {
          version: WebApp.version,
          platform: WebApp.platform,
          isExpanded: WebApp.isExpanded,
        })

        setWebApp(WebApp)
        setIsReady(true)
        isInitializedRef.current = true

        console.log('🎉 Telegram Mini App инициализирован!')

      } catch (error) {
        console.error('❌ Ошибка инициализации:', error)
        setIsReady(true)
      }
    }

    initTelegramApp()

    // Cleanup
    return () => {
      if (window.Telegram?.WebApp) {
        const WebApp = window.Telegram.WebApp
        if (WebApp.MainButton) {
          WebApp.MainButton.hide()
        }
        if (WebApp.BackButton) {
          WebApp.BackButton.hide()
        }
      }
      setIsReady(false)
      setWebApp(null)
      isInitializedRef.current = false
    }
  }, [])

  return (
    <TelegramContext.Provider value={{ isReady, isMiniApp, webApp }}>
      {children}
    </TelegramContext.Provider>
  )
}
