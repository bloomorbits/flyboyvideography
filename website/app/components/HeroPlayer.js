"use client";
import { useEffect, useRef, useState } from "react";

// Hero background is an admin-editable YouTube video (Migration 019): autoplays
// muted + looping behind the headline, with a small overlaid unmute button so
// visitors can opt into sound. Autoplay policies require mute=1 up front; the
// unmute button talks to the player via the YouTube IFrame API (postMessage,
// enablejsapi=1) so opting into sound doesn't reload/restart the clip.
export default function HeroPlayer({ videoId, kicker, headline, sub, cta }) {
  const [muted, setMuted] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const iframeRef = useRef(null);

  // Respect prefers-reduced-motion: no autoplaying embed, show the poster.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mql.matches);
    const onChange = () => setReducedMotion(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  const command = (func, args = []) => {
    const w = iframeRef.current?.contentWindow;
    if (!w) return;
    w.postMessage(JSON.stringify({ event: "command", func, args }), "*");
  };

  const toggleMute = () => {
    if (muted) {
      command("unMute");
      command("setVolume", [100]);
      command("playVideo");
      setMuted(false);
    } else {
      command("mute");
      setMuted(true);
    }
  };

  // loop=1 needs playlist=<id> for a single video; enablejsapi=1 powers unmute.
  const params = new URLSearchParams({
    autoplay: "1",
    mute: "1",
    loop: "1",
    playlist: videoId,
    controls: "0",
    modestbranding: "1",
    rel: "0",
    playsinline: "1",
    enablejsapi: "1",
    disablekb: "1",
    fs: "0",
    iv_load_policy: "3",
  });
  const src = `https://www.youtube.com/embed/${videoId}?${params.toString()}`;

  return (
    <section data-cursor="video" className="relative overflow-hidden bg-coal text-cream">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {reducedMotion ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src="/videos/hero-poster.webp" alt="" className="hero-video-bg" />
        ) : (
          <div className="hero-yt-cover">
            <iframe
              ref={iframeRef}
              data-testid="hero-youtube-embed"
              src={src}
              title="Showreel"
              allow="autoplay; encrypted-media; picture-in-picture"
              tabIndex={-1}
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
      {!reducedMotion && (
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
