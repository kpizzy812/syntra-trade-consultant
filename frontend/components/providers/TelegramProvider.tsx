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

        // ШАГ 3: Настройка цветов (с проверкой версии для избежания warnings)
        const version = parseFloat(WebApp.version || '0')

        if (version >= 6.1 && WebApp.setHeaderColor) {
          try {
            WebApp.setHeaderColor('#000000')
          } catch (e) {
            // Игнорируем ошибки для старых версий
          }
        }
        if (version >= 6.1 && WebApp.setBackgroundColor) {
          try {
            WebApp.setBackgroundColor('#000000')
          } catch (e) {
            // Игнорируем ошибки для старых версий
          }
        }

        // ШАГ 4: Подтверждение закрытия (только для версий 6.2+)
        if (version >= 6.2 && WebApp.enableClosingConfirmation) {
          try {
            WebApp.enableClosingConfirmation()
            console.log('✅ Подтверждение закрытия включено')
          } catch (e) {
            // Игнорируем ошибки для старых версий
          }
        }

        // ШАГ 5: Отключить вертикальные свайпы (только для версий 7.0+)
        if (version >= 7.0 && WebApp.disableVerticalSwipes) {
          try {
            WebApp.disableVerticalSwipes()
            console.log('✅ Вертикальные свайпы отключены')
          } catch (e) {
            // Игнорируем ошибки для старых версий
          }
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
