/**
 * Points Balance Component
 * Отображение баланса $SYNTRA Points в Header с логотипом
 * При клике открывает модалку с описанием
 */

'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { usePointsStore } from '@/shared/store/pointsStore';
import { api } from '@/shared/api/client';
import { useTranslations } from 'next-intl';
import PointsModal from './PointsModal';
import { vibrate } from '@/shared/telegram/vibration';

export default function PointsBalance() {
  const { balance, setBalance, setLoading } = usePointsStore();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const t = useTranslations();

  // Fetch balance on mount
  useEffect(() => {
    const fetchBalance = async () => {
      try {
        setLoading(true);
        const data = await api.points.getBalance();
        setBalance(data);
      } catch (error) {
        console.error('Failed to fetch points balance:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchBalance();
  }, [setBalance, setLoading]);

  // Don't render if no balance
  if (!balance) {
    return null;
  }

  const handleClick = () => {
    vibrate('light');
    setIsModalOpen(true);
  };

  return (
    <>
      {/* Points Balance Button */}
      <button
        onClick={handleClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={`
          flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg
          transition-all duration-200
          ${isHovered
            ? 'bg-gradient-to-r from-blue-500/20 to-purple-500/20 scale-105'
            : 'bg-white/5 hover:bg-white/10'
          }
        `}
      >
        {/* $SYNTRA Logo */}
        <div className="relative w-5 h-5 flex-shrink-0">
          <Image
            src="/syntra/$SYNTRA.png"
            alt="$SYNTRA"
            width={20}
            height={20}
            className="object-contain"
          />
        </div>

        {/* Balance */}
        <span className={`
          text-sm font-semibold tabular-nums
          ${isHovered
            ? 'bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent'
            : 'text-white'
          }
        `}>
          {balance.balance.toLocaleString()}
        </span>

        {/* Level Icon (only on desktop) */}
        <span className="hidden sm:block text-base">
          {balance.level_icon}
        </span>
      </button>

      {/* Points Modal */}
      {isModalOpen && (
        <PointsModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
        />
      )}
    </>
  );
}
