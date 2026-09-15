"use client";
import { useEffect, useRef, useState } from "react";

// Warm coral — deliberately OUTSIDE the site palette (#FAF8F4 cream, #F1EBE0 sand,
// #E9E1D2 dune, #17140F ink, #141210 coal) so the cursor reads with genuine
// contrast on every surface, light or dark. Ties to the hero's warm ambient tones.
const ACCENT = "#FF6A3D";

// Editorial line-art camcorder (lucide "video" shape) — shown over video content.
function Camcorder() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      stroke={ACCENT}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="m22 8-6 4 6 4V8Z" />
      <rect x="2" y="6" width="14" height="12" rx="2" ry="2" />
    </svg>
  );
}

export default function Cursor() {
  const ref = useRef(null);
  const [enabled, setEnabled] = useState(false);
  const [mode, setMode] = useState("default"); // "default" | "view" | "video"

  useEffect(() => {
    // Desktop-only gate: never render on touch / non-hover devices.
    if (!window.matchMedia("(hover: hover)").matches) return;
    setEnabled(true);
    document.documentElement.classList.add("custom-cursor");

    const move = (e) => {
      if (ref.current) ref.current.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
    };
    const over = (e) => {
      const t = e.target;
      if (!t || !t.closest) return setMode("default");
      // Real interactive controls (links/buttons/fields) ALWAYS win — even when
      // they sit inside a video area (e.g. hero CTAs) — so they keep the "view" label.
      if (t.closest("a, button, input, select, textarea")) return setMode("view");
      // Video content → camcorder.
      if (t.closest('[data-cursor="video"]')) return setMode("video");
      // Any other opted-in element (cards, etc.) → "view".
      if (t.closest("[data-cursor]")) return setMode("view");
      setMode("default");
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

  const isView = mode === "view";
  const isVideo = mode === "video";

  return (
    <div
      ref={ref}
      data-testid="custom-cursor"
      data-cursor-mode={mode}
      className="pointer-events-none fixed left-0 top-0 z-[100]"
      aria-hidden
    >
      {isVideo ? (
        <div
          data-testid="cursor-video"
          className="-translate-x-1/2 -translate-y-1/2 transition-all duration-200 ease-out drop-shadow-[0_1px_2px_rgba(0,0,0,0.45)]"
        >
          <Camcorder />
        </div>
      ) : (
        <div
          className="flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full transition-all duration-200 ease-out drop-shadow-[0_0_1.5px_rgba(0,0,0,0.5)]"
          style={
            isView
              ? { height: "3.5rem", width: "3.5rem", backgroundColor: ACCENT }
              : { height: "1.5rem", width: "1.5rem", border: `2px solid ${ACCENT}`, backgroundColor: "transparent" }
          }
        >
          <span
            className="font-mono text-[10px] font-bold uppercase tracking-widest transition-opacity duration-150"
            style={{ color: "#17140F", opacity: isView ? 1 : 0 }}
          >
            view
          </span>
        </div>
      )}
    </div>
  );
}
