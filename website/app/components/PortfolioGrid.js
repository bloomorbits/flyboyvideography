"use client";
import { useMemo, useState } from "react";
import { CATEGORIES, items } from "../../lib/portfolio";
import Reveal from "./Reveal";

function PlayGlyph() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

// Uniform tile. Deliberately no col-span / row-span variants —
// mixed spans plus aspect-ratio children created the empty-slot bug
// reported on the live site. All 15 tiles share the same 4:3 frame so
// every row is the same height and CSS Grid cannot leave holes.
function Card({ item }) {
  const isVideo = item.kind === "video";
  return (
    <article
      data-testid={`portfolio-card-${item.id}`}
      data-cursor
      data-kind={item.kind}
      className="group relative cursor-pointer overflow-hidden rounded-lg border border-dune bg-coal transition-transform duration-500 ease-out hover:-translate-y-1 hover:scale-[1.01] hover:shadow-[0_18px_44px_rgba(23,20,15,0.18)]"
    >
      <div className="relative aspect-[4/3] w-full">
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

        {/* Single per-tile placeholder marker — the diagonal ribbon.
            The old amber caption line was removed after the top banner +
            ribbon was judged sufficient. Ribbon has strong contrast
            (cream text on ink@90) so it's readable on any stock photo. */}
        <div
          aria-hidden
          data-testid={`portfolio-ribbon-${item.id}`}
          className="pointer-events-none absolute -right-11 top-6 rotate-45 bg-ink/95 px-14 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.3em] text-cream shadow-lg ring-1 ring-cream/25"
        >
          Placeholder
        </div>

        {/* Kind + duration badges. Not a placeholder indicator —
            these convey what the tile IS (reel vs still, runtime). */}
        <div className="absolute left-4 top-4 flex items-center gap-2">
          <span className="rounded-sm border border-cream/25 bg-black/45 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-cream backdrop-blur-sm">
            {isVideo ? "Reel" : "Still"}
          </span>
          {isVideo && (
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

        {/* Title strip. Placeholder marker is intentionally dropped from
            here — the top-of-page banner + diagonal ribbon carry it. */}
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/35 to-transparent p-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-cream/75">
            {item.meta}
          </p>
          <p className="mt-1 font-display text-lg font-semibold text-cream">
            {item.title.replace(" · Placeholder", "")}
          </p>
        </div>
      </div>
    </article>
  );
}

export default function PortfolioGrid() {
  const [active, setActive] = useState("all");

  const filtered = useMemo(
    () => (active === "all" ? items : items.filter((i) => i.category === active)),
    [active]
  );

  const counts = useMemo(() => {
    const c = { all: items.length };
    for (const i of items) c[i.category] = (c[i.category] || 0) + 1;
    return c;
  }, []);

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
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-[0.2em] transition-all duration-200 ${
                  isActive
                    ? "border-ink bg-ink text-cream"
                    : "border-ink/15 bg-white/50 text-ink/70 hover:border-ink/40 hover:text-ink"
                }`}
              >
                {cat.label}
                <span
                  className={`rounded-sm px-1.5 py-0.5 text-[9px] tracking-widest ${
                    isActive ? "bg-cream/20 text-cream" : "bg-ink/5 text-ink/50"
                  }`}
                >
                  {counts[cat.id] || 0}
                </span>
              </button>
            );
          })}
        </div>
      </Reveal>

      {/* Uniform 1/2/3-column grid. No auto-rows, no col/row-span variants,
          no per-card Reveal wrapper (Reveal in a grid child was collapsing
          to ~2px on load, which is what caused the huge unexplained gaps
          reported on the live site). */}
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
          No work in this category yet — placeholder set only.
        </p>
      )}
    </section>
  );
}
