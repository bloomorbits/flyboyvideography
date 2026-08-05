"use client";
import { useEffect, useRef, useState } from "react";

export default function Cursor() {
  const ref = useRef(null);
  const [enabled, setEnabled] = useState(false);
  const [hovering, setHovering] = useState(false);

  useEffect(() => {
    if (!window.matchMedia("(hover: hover)").matches) return;
    setEnabled(true);
    document.documentElement.classList.add("custom-cursor");
    const move = (e) => {
      if (ref.current) ref.current.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
    };
    const over = (e) => {
      setHovering(!!e.target.closest("a, button, input, select, textarea, [data-cursor]"));
    };
    window.addEventListener("mousemove", move, { passive: true });
    window.addEventListener("mouseover", over, { passive: true });
    return () => {
      document.documentElement.classList.remove("custom-cursor");
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseover", over);
    };
  }, []);

  if (!enabled) return null;
  return (
    <div ref={ref} data-testid="custom-cursor" className="pointer-events-none fixed left-0 top-0 z-[100]" aria-hidden>
      <div
        className={`flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full mix-blend-difference transition-all duration-200 ease-out ${
          hovering ? "h-14 w-14 bg-white" : "h-6 w-6 border-2 border-white bg-transparent"
        }`}
      >
        <span className={`font-mono text-[10px] font-bold uppercase tracking-widest text-black transition-opacity duration-150 ${hovering ? "opacity-100" : "opacity-0"}`}>
          view
        </span>
      </div>
    </div>
  );
}
