"use client";
import { useEffect, useRef, useState } from "react";

const DURATION = 167; // 02:47 simulated reel length — placeholder scrubber until real showreel lands

const tc = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export default function HeroPlayer({ kicker, headline, sub, cta }) {
  const [time, setTime] = useState(0);
  const [muted, setMuted] = useState(true);
  const trackRef = useRef(null);
  const videoRef = useRef(null);

  useEffect(() => {
    const id = setInterval(() => setTime((t) => (t + 1) % DURATION), 1000);
    return () => clearInterval(id);
  }, []);

  // Ambient background video: respect prefers-reduced-motion.
  // Sequenced loading strategy: preload="none" on <video>, and only call
  // .load()+.play() AFTER the poster image has finished loading. This
  // gives the poster the full bandwidth on slow connections so users see
  // a real hero background within a few seconds — the video takes over
  // silently once it's ready. Without this, the browser races poster +
  // video for the pipe and users see a black hero for 25-30s on Slow 4G.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const v = videoRef.current;
    if (!v) return;

    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    let cancelled = false;

    const posterReady = new Promise((resolve) => {
      const url = v.poster;
      if (!url) return resolve();
      const img = new Image();
      img.onload = resolve;
      img.onerror = resolve; // never block video on poster fetch failure
      img.src = url;
    });

    const kickoff = async () => {
      await posterReady;
      if (cancelled) return;
      if (mql.matches) {
        // reduced-motion users: poster stays, no video fetch at all
        return;
      }
      // With preload="none", .load() actually initiates the fetch.
      v.load();
      const p = v.play();
      if (p && typeof p.catch === "function") p.catch(() => {});
    };
    kickoff();

    const onMotionPref = () => {
      if (mql.matches) {
        v.pause();
        v.currentTime = 0;
      } else if (v.paused) {
        v.load();
        const p = v.play();
        if (p && typeof p.catch === "function") p.catch(() => {});
      }
    };
    mql.addEventListener("change", onMotionPref);

    return () => {
      cancelled = true;
      mql.removeEventListener("change", onMotionPref);
    };
  }, []);

  const seek = (e) => {
    const rect = trackRef.current.getBoundingClientRect();
    const pct = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    setTime(Math.floor(pct * DURATION));
  };

  return (
    <section className="relative overflow-hidden bg-coal text-cream">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {/*
          Preload the poster with high priority so it's fetched ahead of
          the video sources — critical for slow-connection first paint.
          WebP is served (2026 browser baseline supports it universally);
          the JPG variant is kept in /public/videos as a fallback but not
          preloaded here. React 19 hoists <link> into <head> automatically.
        */}
        <link
          rel="preload"
          as="image"
          href="/videos/hero-poster.webp"
          type="image/webp"
          fetchPriority="high"
        />
        <video
          ref={videoRef}
          className="hero-video-bg"
          data-testid="hero-background-video"
          poster="/videos/hero-poster.webp"
          muted
          loop
          playsInline
          preload="none"
          aria-hidden="true"
          tabIndex={-1}
        >
          {/* WebM first for browsers that support it (smaller); MP4 fallback for Safari */}
          <source src="/videos/hero-loop.webm" type="video/webm" />
          <source src="/videos/hero-loop.mp4" type="video/mp4" />
        </video>
        <div className="hero-scrim" />
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
