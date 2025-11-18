/**
 * TON Connect Provider
 * Оборачивает приложение для работы с TON Connect
 */

'use client';

import { TonConnectUIProvider } from '@tonconnect/ui-react';

interface TonConnectProviderProps {
  children: React.ReactNode;
}

export default function TonConnectProvider({ children }: TonConnectProviderProps) {
  // Manifest URL должен быть доступен публично
  const manifestUrl = 'https://ai.syntratrade.xyz/tonconnect-manifest.json';

  return (
    <TonConnectUIProvider manifestUrl={manifestUrl}>
      {children}
    </TonConnectUIProvider>
  );
}
