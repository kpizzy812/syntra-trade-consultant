/**
 * Icon Component - Wrapper for SVG icons
 * Simplifies usage of icon files with consistent sizing and colors
 */

import Image from 'next/image';

interface IconProps {
  name: string;
  size?: number;
  className?: string;
}

export default function Icon({ name, size = 20, className = '' }: IconProps) {
  return (
    <Image
      src={`/icons/${name}.svg`}
      width={size}
      height={size}
      alt={name}
      className={className}
    />
  );
}
