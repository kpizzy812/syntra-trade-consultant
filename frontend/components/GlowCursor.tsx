
"use client";

import { useEffect } from "react";

export default function GlowCursor() {
  useEffect(() => {
    const glow = document.querySelector(".cursor-glow") as HTMLElement | null;
    if (!glow) return;

    const move = (e: MouseEvent) => {
      // 500x500px курсор, центрируем на 250px от позиции мыши
      const x = e.clientX - 250;
      const y = e.clientY - 250;
      glow.style.transform = `translate(${x}px, ${y}px)`;
    };

    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  return <div className="cursor-glow" />;
}
