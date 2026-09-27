"use client";
import { useEffect, useRef, useState } from "react";

const UNMUTE_KEY = "flyboyHeroUnmuted";
const LAST_KEY = "flyboyHeroLast";

// Weighted pick: expand each video by its weight, pick at random, and avoid
// immediately repeating the last-shown video when the queue has alternatives —
// so favourites (higher weight) appear more often while each visit still tends
// to differ.
function weightedPick(videos, lastId) {
  const pool = [];
  videos.forEach((v) => {
    const w = Math.max(1, Number(v.weight) || 1);
    for (let i = 0; i < w; i++) pool.push(v.id);
  });
  if (!pool.length) return null;
  const distinct = new Set(videos.map((v) => v.id));
  let pick = pool[Math.floor(Math.random() * pool.length)];
  let tries = 0;
  while (pick === lastId && distinct.size > 1 && tries < 12) {
    pick = pool[Math.floor(Math.random() * pool.length)];
    tries++;
  }
  return pick;
}

// Hero background is an admin-editable, WEIGHTED queue of YouTube videos
// (Migration 019): rotates per visit (favourites appear more often), remembers
// a visitor's unmute choice in localStorage, and shows an admin-uploaded poster
// instantly while the embed buffers. Autoplay policy requires mute=1 up front;
// the overlaid unmute button (and remembered preference) drive the player via
// the YouTube IFrame API (postMessage, enablejsapi=1) without reloading.
export default function HeroPlayer({ videos = [], posterUrl, kicker, headline, sub, cta }) {
  const list = Array.isArray(videos) ? videos.filter((v) => v && v.id) : [];
  const [chosenId, setChosenId] = useState(null);
  const [muted, setMuted] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const iframeRef = useRef(null);
  const wantUnmuteRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined" || !list.length) return;

    try {
      wantUnmuteRef.current = window.localStorage.getItem(UNMUTE_KEY) === "1";
    } catch { /* storage blocked — default muted */ }

    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mql.matches);
    const onChange = () => setReducedMotion(mql.matches);
    mql.addEventListener("change", onChange);

    let lastId = null;
    try { lastId = window.localStorage.getItem(LAST_KEY); } catch {}
    const pick = weightedPick(list, lastId);
    try { if (pick) window.localStorage.setItem(LAST_KEY, pick); } catch {}
    setChosenId(pick);

    return () => mql.removeEventListener("change", onChange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const command = (func, args = []) => {
    const w = iframeRef.current?.contentWindow;
    if (!w) return;
    w.postMessage(JSON.stringify({ event: "command", func, args }), "*");
  };

  const applyUnmute = () => {
    command("unMute");
    command("setVolume", [100]);
    command("playVideo");
  };

  const onIframeLoad = () => {
    if (wantUnmuteRef.current) {
      setTimeout(() => {
        applyUnmute();
        setMuted(false);
      }, 700);
    }
  };

  const toggleMute = () => {
    if (muted) {
      applyUnmute();
      setMuted(false);
      try { window.localStorage.setItem(UNMUTE_KEY, "1"); } catch {}
    } else {
      command("mute");
      setMuted(true);
      try { window.localStorage.setItem(UNMUTE_KEY, "0"); } catch {}
    }
  };

  const posterId = chosenId || (list[0] && list[0].id);
  const poster = posterUrl
    || (posterId ? `https://i.ytimg.com/vi/${posterId}/maxresdefault.jpg` : "/videos/hero-poster.webp");

  const params = chosenId
    ? new URLSearchParams({
        autoplay: "1",
        mute: "1",
        loop: "1",
        playlist: chosenId,
        controls: "0",
        modestbranding: "1",
        rel: "0",
        playsinline: "1",
        enablejsapi: "1",
        disablekb: "1",
        fs: "0",
        iv_load_policy: "3",
      }).toString()
    : null;

  return (
    <section data-cursor="video" className="relative overflow-hidden bg-coal text-cream">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={poster} alt="" className="hero-video-bg" data-testid="hero-poster" />
        {!reducedMotion && chosenId && (
          <div className="hero-yt-cover">
            <iframe
              ref={iframeRef}
              data-testid="hero-youtube-embed"
              src={`https://www.youtube.com/embed/${chosenId}?${params}`}
              title="Showreel"
              allow="autoplay; encrypted-media; picture-in-picture"
              tabIndex={-1}
              onLoad={onIframeLoad}
            />
          </div>
        )}
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

      {/* Small unmute button overlaid on the video */}
      {!reducedMotion && chosenId && (
        <button
          data-testid="hero-mute-toggle"
          onClick={toggleMute}
          aria-label={muted ? "Unmute video" : "Mute video"}
          className="absolute bottom-6 right-6 z-20 inline-flex h-11 w-11 items-center justify-center rounded-full border border-cream/30 bg-coal/50 text-cream/80 backdrop-blur transition-colors hover:border-cream/70 hover:text-cream"
        >
          {muted ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" /><line x1="23" y1="9" x2="17" y2="15" /><line x1="17" y1="9" x2="23" y2="15" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" /><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
            </svg>
          )}
        </button>
      )}
    </section>
  );
}
