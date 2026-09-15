"use client";
import { useState } from "react";

// Click-to-play video hero for SEO landing pages. Mirrors the portfolio grid's
// embed discipline: a poster + play button render first (no iframe, no network
// to YouTube on load, NOT autoplay), and the YouTube iframe is only injected on
// click. This keeps the hero cheap for LCP/SEO while still showing real work.
// Rendered ONLY when a real active video exists for the page's category — there
// is no placeholder state here (that's the page's existing fallback hero).

function PlayGlyph() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

export default function SeoVideoHero({ youtubeId, title, thumbnailUrl, label }) {
  const [playing, setPlaying] = useState(false);
  const poster = thumbnailUrl || `https://i.ytimg.com/vi/${youtubeId}/hqdefault.jpg`;

  return (
    <section data-testid="seo-video-hero" className="bg-coal text-cream">
      <div className="mx-auto max-w-4xl px-6 pb-12 pt-32 md:pb-16 md:pt-36">
        <p
          data-testid="seo-hero-kicker"
          className="font-mono text-xs uppercase tracking-[0.35em] text-dune"
        >
          Recent work
        </p>

        <div
          data-testid="seo-hero-frame"
          onClick={() => { if (!playing) setPlaying(true); }}
          className={`group relative mt-5 overflow-hidden rounded-xl border border-cream/10 bg-black ${playing ? "" : "cursor-pointer"}`}
        >
          <div className="relative aspect-video w-full">
            {playing ? (
              <iframe
                data-testid="seo-hero-embed"
                className="absolute inset-0 h-full w-full"
                src={`https://www.youtube.com/embed/${youtubeId}?autoplay=1&rel=0&modestbranding=1`}
                title={title}
                frameBorder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
              />
            ) : (
              <>
                <img
                  src={poster}
                  alt=""
                  aria-hidden
                  fetchPriority="high"
                  decoding="async"
                  className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
                />
                <div aria-hidden className="absolute inset-0 bg-black/35" />
                <div aria-hidden className="grain opacity-40" />

                {label && (
                  <span className="absolute left-4 top-4 rounded-sm border border-cream/25 bg-black/45 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-cream backdrop-blur-sm">
                    {label}
                  </span>
                )}

                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="flex h-16 w-16 items-center justify-center rounded-full border border-cream/40 bg-black/40 text-cream backdrop-blur-md transition-transform duration-300 group-hover:scale-110">
                    <PlayGlyph />
                  </span>
                </div>

                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent p-5">
                  <p data-testid="seo-hero-title" className="font-display text-lg font-semibold text-cream">
                    {title}
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
