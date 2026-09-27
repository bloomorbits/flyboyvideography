import Link from "next/link";
import { items } from "../../lib/portfolio";

// Homepage "Recent Work" — renders the 4 admin-featured projects (Migration
// 020) in the admin-set order, using the SAME visual language as the Work page.
// If no projects are featured yet (or the API is unavailable), it falls back to
// the honest placeholder set so the homepage never renders empty.

const CATEGORY_LABELS = {
  weddings: "Wedding",
  birthdays: "Birthday",
  naming: "Naming Ceremony",
  corporate: "Corporate / Brand",
  lifestyle: "Lifestyle",
};

// Fallback placeholder picks (unchanged) — used only when nothing is featured.
const PICKS = ["w-01", "b-01", "c-01", "l-01"];
const placeholderHighlights = PICKS.map((id) => items.find((i) => i.id === id)).filter(Boolean);

function fmtDuration(secs) {
  if (!secs || secs <= 0) return null;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function PlayGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function Tile({ href, testid, thumb, badge, duration, meta, title, ribbon }) {
  return (
    <Link
      href={href}
      data-testid={testid}
      data-cursor
      className="group relative block overflow-hidden rounded-lg border border-dune bg-coal transition-transform duration-500 ease-out hover:-translate-y-1 hover:scale-[1.01] hover:shadow-[0_18px_44px_rgba(23,20,15,0.15)]"
    >
      <div className="relative aspect-[4/5] w-full">
        <img
          src={thumb}
          alt=""
          aria-hidden
          loading="lazy"
          decoding="async"
          className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
        />
        <div aria-hidden className="absolute inset-0 bg-black/30" />
        <div aria-hidden className="grain opacity-50" />

        {ribbon && (
          <div
            aria-hidden
            className="pointer-events-none absolute -right-11 top-6 rotate-45 bg-ink/90 px-14 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.3em] text-cream shadow-lg ring-1 ring-cream/20"
          >
            {ribbon}
          </div>
        )}

        <div className="absolute left-4 top-4 flex items-center gap-2">
          <span className="rounded-sm border border-cream/25 bg-black/40 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-cream/90 backdrop-blur-sm">
            {badge}
          </span>
          {duration && (
            <span className="rounded-sm bg-cream/90 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-ink">
              {duration}
            </span>
          )}
        </div>

        <div className="absolute inset-0 flex items-center justify-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full border border-cream/40 bg-black/40 text-cream backdrop-blur-md transition-transform duration-300 group-hover:scale-110">
            <PlayGlyph />
          </span>
        </div>

        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-cream/75">{meta}</p>
          <p className="mt-1 font-display text-sm font-semibold text-cream">{title}</p>
        </div>
      </div>
    </Link>
  );
}

export default function HomePortfolioHighlights({ projects }) {
  const featured = Array.isArray(projects) ? projects.slice(0, 4) : [];
  const usingReal = featured.length > 0;

  return (
    <section data-testid="home-portfolio-highlights" className="border-t border-dune bg-cream">
      <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">
        <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/70">
              {usingReal ? "Recent work" : "Recent work · Placeholder set"}
            </p>
            <h2 className="mt-2 font-display text-3xl font-bold tracking-tight md:text-4xl">
              A quick look at the mix.
            </h2>
          </div>
          <Link
            href="/portfolio"
            data-testid="home-view-full-portfolio"
            className="inline-flex min-h-[44px] items-center gap-2 rounded-full border border-ink/20 px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-[0.2em] text-ink transition-colors hover:border-ink hover:bg-ink hover:text-cream"
          >
            View full portfolio <span aria-hidden>→</span>
          </Link>
        </div>

        <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
          {usingReal
            ? featured.map((p) => (
                <Tile
                  key={p.id}
                  href="/portfolio"
                  testid={`home-highlight-${p.id}`}
                  thumb={p.thumbnail_url || `https://i.ytimg.com/vi/${p.youtube_video_id}/hqdefault.jpg`}
                  badge="Reel"
                  duration={fmtDuration(p.duration_seconds)}
                  meta={CATEGORY_LABELS[p.category] || p.category}
                  title={p.title}
                />
              ))
            : placeholderHighlights.map((item) => (
                <Tile
                  key={item.id}
                  href="/portfolio"
                  testid={`home-highlight-${item.id}`}
                  thumb={item.src}
                  badge={item.kind === "video" ? "Reel" : "Still"}
                  duration={item.kind === "video" ? item.duration : null}
                  meta={item.meta}
                  title={item.title.replace(" · Placeholder", "")}
                  ribbon="Placeholder"
                />
              ))}
        </div>
      </div>
    </section>
  );
}
