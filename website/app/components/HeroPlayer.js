"use client";
import { useEffect, useRef, useState } from "react";

const DURATION = 167; // 02:47 simulated reel length

const tc = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export default function HeroPlayer({ kicker, headline, sub, cta }) {
  const [time, setTime] = useState(0);
  const [muted, setMuted] = useState(true);
  const trackRef = useRef(null);

  useEffect(() => {
    const id = setInterval(() => setTime((t) => (t + 1) % DURATION), 1000);
    return () => clearInterval(id);
  }, []);

  const seek = (e) => {
    const rect = trackRef.current.getBoundingClientRect();
    const pct = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    setTime(Math.floor(pct * DURATION));
  };

  return (
    <section className="relative overflow-hidden bg-coal text-cream">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="blob blob-1" />
        <div className="blob blob-2" />
        <div className="blob blob-3" />
        <div className="grain" />
      </div>

      <div className="relative z-10 mx-auto max-w-6xl px-6 pb-28 pt-40 md:pt-48">
        <p className="font-mono text-xs uppercase tracking-[0.35em] text-dune">{kicker}</p>
        <h1 className="mt-6 max-w-3xl font-display text-5xl font-bold leading-[1.05] tracking-tight md:text-7xl">
          {headline}
        </h1>
        {sub && <p className="mt-6 max-w-xl text-lg text-dune">{sub}</p>}
        {cta}
      </div>

      <div className="relative z-10 border-t border-cream/10">
        <div className="mx-auto flex max-w-6xl items-center gap-5 px-6 py-5">
          <button
            data-testid="hero-mute-toggle"
            onClick={() => setMuted(!muted)}
            aria-label={muted ? "Unmute" : "Mute"}
            className="text-cream/70 transition-colors hover:text-cream"
          >
            {muted ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" /><line x1="23" y1="9" x2="17" y2="15" /><line x1="17" y1="9" x2="23" y2="15" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" /><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
              </svg>
            )}
          </button>
          <div
            ref={trackRef}
            data-testid="hero-scrubber"
            onClick={seek}
            role="slider"
            aria-label="Reel position"
            aria-valuemin={0}
            aria-valuemax={DURATION}
            aria-valuenow={time}
            className="group relative h-6 flex-1"
          >
            <div className="absolute top-1/2 h-[3px] w-full -translate-y-1/2 rounded bg-cream/20" />
            <div
              className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded bg-cream transition-[width] duration-500 ease-linear"
              style={{ width: `${(time / DURATION) * 100}%` }}
            />
            <div
              className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-cream opacity-0 transition-opacity group-hover:opacity-100"
              style={{ left: `${(time / DURATION) * 100}%` }}
            />
          </div>
          <p data-testid="hero-timecode" className="font-mono text-xs tracking-widest text-cream/80">
            {tc(time)} <span className="text-cream/40">/ {tc(DURATION)}</span>
          </p>
          <p className="hidden font-mono text-[10px] uppercase tracking-[0.25em] text-cream/40 md:block">
            Showreel · placeholder
          </p>
        </div>
      </div>
    </section>
  );
}
