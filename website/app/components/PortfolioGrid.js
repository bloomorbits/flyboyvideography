"use client";
import { useMemo, useState } from "react";
import { CATEGORIES } from "../../lib/portfolio";
import Reveal from "./Reveal";

function PlayGlyph() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

// Uniform tile. Real tiles are genuine click-to-play YouTube embeds (the
// iframe loads in place on click — YouTube-hosted, plays on the page, not a
// link-out). Placeholder tiles keep the diagonal "Placeholder" ribbon.
function Card({ item }) {
  const isVideo = item.kind === "video";
  const [playing, setPlaying] = useState(false);

  return (
    <article
      data-testid={`portfolio-card-${item.id}`}
      data-cursor={item.real ? undefined : true}
      data-kind={item.kind}
      data-real={item.real ? "true" : "false"}
      onClick={() => { if (item.real) setPlaying(true); }}
      className={`group relative overflow-hidden rounded-lg border border-dune bg-coal transition-transform duration-500 ease-out hover:-translate-y-1 hover:scale-[1.01] hover:shadow-[0_18px_44px_rgba(23,20,15,0.18)] ${item.real ? "cursor-pointer" : "cursor-pointer"}`}
    >
      <div className="relative aspect-[4/3] w-full">
        {playing ? (
          <iframe
            data-testid={`portfolio-embed-${item.id}`}
            className="absolute inset-0 h-full w-full"
            src={`https://www.youtube.com/embed/${item.youtubeId}?autoplay=1&rel=0&modestbranding=1`}
            title={item.title}
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        ) : (
          <>
            <img
              src={item.src}
              alt=""
              aria-hidden
              loading="lazy"
              decoding="async"
              className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
            />
            <div aria-hidden className="absolute inset-0 bg-black/25" />
            <div aria-hidden className="grain opacity-50" />

            {/* Placeholder ribbon — ONLY on non-real tiles. Real embeds never
                carry it, so real and placeholder content are never mixed
                without a clear distinction. */}
            {!item.real && (
              <div
                aria-hidden
                data-testid={`portfolio-ribbon-${item.id}`}
                className="pointer-events-none absolute -right-11 top-6 rotate-45 bg-ink/95 px-14 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.3em] text-cream shadow-lg ring-1 ring-cream/25"
              >
                Placeholder
              </div>
            )}

            <div className="absolute left-4 top-4 flex items-center gap-2">
              <span className="rounded-sm border border-cream/25 bg-black/45 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-cream backdrop-blur-sm">
                {isVideo ? "Reel" : "Still"}
              </span>
              {isVideo && item.duration && (
                <span
                  data-testid={`portfolio-duration-${item.id}`}
                  className="rounded-sm bg-cream/95 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-ink"
                >
                  {item.duration}
                </span>
              )}
            </div>

            {isVideo && (
              <div
                data-testid={`portfolio-play-${item.id}`}
                className="absolute inset-0 flex items-center justify-center"
              >
                <span className="flex h-16 w-16 items-center justify-center rounded-full border border-cream/40 bg-black/40 text-cream backdrop-blur-md transition-transform duration-300 group-hover:scale-110">
                  <PlayGlyph />
                </span>
              </div>
            )}

            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/35 to-transparent p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-cream/75">
                {item.meta}
              </p>
              <p className="mt-1 font-display text-lg font-semibold text-cream">
                {item.title.replace(" · Placeholder", "")}
              </p>
            </div>
          </>
        )}
      </div>
    </article>
  );
}

export default function PortfolioGrid({ tiles = [] }) {
  const [active, setActive] = useState("all");

  const filtered = useMemo(
    () => (active === "all" ? tiles : tiles.filter((i) => i.category === active)),
    [active, tiles]
  );

  const counts = useMemo(() => {
    const c = { all: tiles.length };
    for (const i of tiles) c[i.category] = (c[i.category] || 0) + 1;
    return c;
  }, [tiles]);

  return (
    <section className="mx-auto max-w-6xl px-6 py-16 md:py-20">
      <Reveal>
        <div
          data-testid="portfolio-filters"
          className="flex flex-wrap items-center gap-2"
          role="tablist"
          aria-label="Portfolio categories"
        >
          {CATEGORIES.map((cat) => {
            const isActive = active === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setActive(cat.id)}
                data-testid={`portfolio-filter-${cat.id}`}
                data-active={isActive}
                role="tab"
                aria-selected={isActive}
                aria-label={`${cat.label}, ${counts[cat.id] || 0} items`}
                className={`inline-flex min-h-[44px] items-center gap-2 rounded-full border px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-[0.2em] transition-all duration-200 ${
                  isActive
                    ? "border-ink bg-ink text-cream"
                    : "border-ink/15 bg-white/50 text-ink/70 hover:border-ink/40 hover:text-ink"
                }`}
              >
                <span>{cat.label}</span>
                <span
                  aria-hidden
                  className={`rounded-sm px-1.5 py-0.5 text-[9px] tracking-widest ${
                    isActive ? "bg-cream/20 text-cream" : "bg-ink/5 text-ink/70"
                  }`}
                >
                  {counts[cat.id] || 0}
                </span>
              </button>
            );
          })}
        </div>
      </Reveal>

      <div
        data-testid="portfolio-grid"
        data-active-category={active}
        className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3"
      >
        {filtered.map((item) => (
          <Card key={item.id} item={item} />
        ))}
      </div>

      {filtered.length === 0 && (
        <p data-testid="portfolio-empty" className="mt-10 font-mono text-xs uppercase tracking-widest text-ink/40">
          Nothing in this category yet.
        </p>
      )}
    </section>
  );
}
