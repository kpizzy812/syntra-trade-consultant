/**
 * Points Earn Animation Component
 * Красивая анимация начисления поинтов (+5, +10, +15 и т.д.)
 * Летящая цифра с иконкой $SYNTRA
 */

'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';
import Image from 'next/image';

interface PointsEarnAnimationProps {
  amount: number;
  trigger: number; // Увеличивайте это значение, чтобы запустить анимацию
}

interface AnimationInstance {
  id: string;
  amount: number;
  x: number;
}

export default function PointsEarnAnimation({ amount, trigger }: PointsEarnAnimationProps) {
  const [animations, setAnimations] = useState<AnimationInstance[]>([]);

  useEffect(() => {
    if (trigger > 0 && amount > 0) {
      // Генерируем случайное смещение по X для разнообразия
      const randomX = Math.random() * 40 - 20; // от -20 до +20

      const newAnimation: AnimationInstance = {
        id: `points-${Date.now()}-${Math.random()}`,
        amount,
        x: randomX,
      };

      setAnimations((prev) => [...prev, newAnimation]);

      // Удаляем анимацию через 2 секунды
      setTimeout(() => {
        setAnimations((prev) => prev.filter((a) => a.id !== newAnimation.id));
      }, 2000);
    }
  }, [trigger, amount]);

  return (
    <div className="fixed inset-0 pointer-events-none z-[9000] flex items-start justify-center pt-20">
      <AnimatePresence mode="sync">
        {animations.map((anim) => (
          <motion.div
            key={anim.id}
            initial={{ opacity: 0, y: 0, scale: 0.8 }}
            animate={{
              opacity: [0, 1, 1, 0],
              y: [-10, -80, -120],
              scale: [0.8, 1.2, 1],
            }}
            exit={{ opacity: 0 }}
            transition={{
              duration: 1.8,
              ease: [0.4, 0, 0.2, 1],
            }}
            className="absolute flex items-center gap-1.5 bg-gradient-to-r from-blue-500/90 to-purple-500/90 px-4 py-2 rounded-full shadow-2xl backdrop-blur-sm border border-white/20"
            style={{
              left: `calc(50% + ${anim.x}px)`,
              transform: 'translateX(-50%)',
            }}
          >
            {/* $SYNTRA Icon */}
            <Image
              src="/syntra/$SYNTRA.png"
              alt="$SYNTRA"
              width={20}
              height={20}
              className="object-contain"
            />

            {/* Amount */}
            <motion.span
              initial={{ scale: 0.8 }}
              animate={{ scale: [0.8, 1.3, 1] }}
              transition={{ duration: 0.5 }}
              className="text-white font-bold text-lg"
            >
              +{anim.amount}
            </motion.span>

            {/* Sparkle effect */}
            <motion.div
              initial={{ scale: 0, rotate: 0 }}
              animate={{ scale: [0, 1.5, 0], rotate: [0, 180, 360] }}
              transition={{ duration: 1, delay: 0.2 }}
              className="absolute -top-2 -right-2 text-yellow-300 text-xl"
            >
              ✨
            </motion.div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
