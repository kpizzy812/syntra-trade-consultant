/**
 * Toast Provider
 * Глобальный провайдер для уведомлений
 */

'use client';

import { Toaster } from 'react-hot-toast';

export default function ToastProvider() {
  return (
    <Toaster
      position="top-center"
      reverseOrder={false}
      gutter={8}
      toastOptions={{
        // Дефолтные настройки для всех toast
        duration: 4000,
        style: {
          background: '#1A1A1A',
          color: '#fff',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '12px',
          padding: '12px 16px',
          fontSize: '14px',
          fontFamily: 'Inter, system-ui, sans-serif',
        },
        // Success toast
        success: {
          duration: 3000,
          style: {
            background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
          },
          iconTheme: {
            primary: '#fff',
            secondary: '#10B981',
          },
        },
        // Error toast
        error: {
          duration: 5000,
          style: {
            background: 'linear-gradient(135deg, #EF4444 0%, #DC2626 100%)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
          },
          iconTheme: {
            primary: '#fff',
            secondary: '#EF4444',
          },
        },
        // Loading toast
        loading: {
          duration: Infinity,
          style: {
            background: 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
          },
        },
      }}
    />
  );
}
