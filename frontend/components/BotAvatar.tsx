"use client";

import Image from "next/image";
import { motion } from "framer-motion";

interface BotAvatarProps {
  size?: number;
  className?: string;
  animated?: boolean; // Включить анимацию glow/pulse
}

/**
 * Анимированный аватар бота с glow эффектом
 * Использует Framer Motion для плавной анимации
 */
export default function BotAvatar({
  size = 40,
  className = "",
  animated = true
}: BotAvatarProps) {
  if (!animated) {
    // Простой аватар без анимации (для мобильных устройств)
    return (
      <div
        className={`rounded-xl overflow-hidden bg-black flex-shrink-0 ring-1 ring-blue-500/30 ${className}`}
        style={{ width: size, height: size }}
      >
        <Image
          src="/syntra/aiminiature.png"
          width={size}
          height={size}
          alt="Syntra AI"
          className="object-cover"
        />
      </div>
    );
  }

  return (
    <motion.div
      className={`relative ${className}`}
      animate={{
        scale: [1, 1.03, 1],
      }}
      transition={{
        duration: 3,
        repeat: Infinity,
        ease: "easeInOut",
      }}
      style={{ width: size, height: size }}
    >
      {/* Внешний glow слой - большой радиус */}
      <motion.div
        className="absolute inset-0 rounded-xl"
        animate={{
          boxShadow: [
            "0 0 20px rgba(59, 130, 246, 0.4), 0 0 40px rgba(59, 130, 246, 0.2), 0 0 60px rgba(59, 130, 246, 0.1)",
            "0 0 30px rgba(59, 130, 246, 0.6), 0 0 60px rgba(59, 130, 246, 0.3), 0 0 90px rgba(59, 130, 246, 0.15)",
            "0 0 20px rgba(59, 130, 246, 0.4), 0 0 40px rgba(59, 130, 246, 0.2), 0 0 60px rgba(59, 130, 246, 0.1)",
          ],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />

      {/* Средний glow слой - градиент */}
      <motion.div
        className="absolute inset-0 rounded-xl"
        style={{
          background: "radial-gradient(circle, rgba(59, 130, 246, 0.3), transparent 70%)",
          filter: "blur(8px)",
        }}
        animate={{
          opacity: [0.5, 0.8, 0.5],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 0.5,
        }}
      />

      {/* Аватар */}
      <div
        className="relative rounded-xl overflow-hidden bg-black z-10 ring-1 ring-blue-500/30"
        style={{ width: size, height: size }}
      >
        <Image
          src="/syntra/aiminiature.png"
          width={size}
          height={size}
          alt="Syntra AI"
          className="object-cover"
          priority
        />
      </div>
    </motion.div>
  );
}
