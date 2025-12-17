/**
 * Desktop Layout Wrapper
 * Адаптивный layout: Sidebar на desktop, mobile на Telegram
 * Mobile: Sidebar overlay с hamburger menu
 */

'use client';

import { ReactNode, useState, createContext, useContext } from 'react';
import { usePlatform } from '@/lib/platform';
import Sidebar from './Sidebar';

interface DesktopLayoutProps {
  children: ReactNode;
}

interface SidebarContextType {
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  closeSidebar: () => void;
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export const useSidebar = () => {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error('useSidebar must be used within DesktopLayout');
  }
  return context;
};

export default function DesktopLayout({ children }: DesktopLayoutProps) {
  const { platformType, isReady } = usePlatform();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);
  const closeSidebar = () => setIsSidebarOpen(false);

  // Wait for platform detection
  if (!isReady) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  const isDesktop = platformType === 'web';

  // Mobile/Telegram: original mobile-body layout
  if (!isDesktop) {
    return <div className="mobile-body">{children}</div>;
  }

  // Desktop: Sidebar + Main Content
  // Mobile: Overlay Sidebar
  return (
    <SidebarContext.Provider value={{ isSidebarOpen, toggleSidebar, closeSidebar }}>
      <div className="flex h-screen bg-black overflow-hidden">
        {/* Sidebar Navigation */}
        <Sidebar isOpen={isSidebarOpen} onClose={closeSidebar} />

        {/* Backdrop for Mobile */}
        {isSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
            onClick={closeSidebar}
          />
        )}

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {children}
        </main>
      </div>
    </SidebarContext.Provider>
  );
}
