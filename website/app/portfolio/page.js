import Link from "next/link";
import HeroPlayer from "../components/HeroPlayer";
import Marquee from "../components/Marquee";
import Reveal from "../components/Reveal";
import PortfolioGrid from "../components/PortfolioGrid";
import { SERVICE_AREA } from "../components/SiteFooter";
import { CATEGORIES, items as placeholderItems } from "../../lib/portfolio";

export const metadata = {
  title: "Portfolio",
  description:
    "Flyboy Videography portfolio — weddings, birthday celebrations, naming ceremonies, gender reveals, corporate events and lifestyle reels.",
};

// Public-site ISR: same 60s revalidate as /services → /api/pricing.
export const revalidate = 60;

const REAL_CATS = ["weddings", "birthdays", "naming", "corporate", "lifestyle"];
const CAT_LABEL = Object.fromEntries(CATEGORIES.map((c) => [c.id, c.label]));
const MARQUEE = CATEGORIES.filter((c) => c.id !== "all").map((c) => c.label);

function thumb(v) {
  return v.thumbnail_url || `https://i.ytimg.com/vi/${v.youtube_video_id}/hqdefault.jpg`;
}
function fmtDur(s) {
  if (!s) return null;
  const m = Math.floor(s / 60), sec = s % 60;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}
function isoDur(s) {
  return s ? `PT${Math.floor(s / 60)}M${s % 60}S` : undefined;
}

async function getVideos() {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return [];
  try {
    const res = await fetch(`${base}/api/portfolio`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.videos) ? data.videos : [];
  } catch {
    return [];
  }
}

export default async function PortfolioPage() {
  const videos = await getVideos();

  const realByCat = {};
  for (const v of videos) (realByCat[v.category] ||= []).push(v);

  // Build the unified tile list, category by category. A category with real
  // active videos shows ONLY those; a category with none keeps its honest
  // placeholder tiles — never mixed within a category, never unlabelled.
  const tiles = [];
  for (const cat of REAL_CATS) {
    const real = realByCat[cat] || [];
    if (real.length) {
      for (const v of real) {
        tiles.push({
          id: v.id,
          category: cat,
          kind: "video",
          real: true,
          youtubeId: v.youtube_video_id,
          title: v.title,
          meta: `${CAT_LABEL[cat] || cat} · Film`,
          src: thumb(v),
          duration: fmtDur(v.duration_seconds),
        });
      }
    } else {
      for (const i of placeholderItems.filter((p) => p.category === cat)) {
        tiles.push({ ...i, real: false });
      }
    }
  }

  const hasReal = tiles.some((t) => t.real);
  const hasPlaceholder = tiles.some((t) => !t.real);

  // VideoObject JSON-LD — one per REAL video, from its actual metadata.
  const videoLd = videos.map((v) => ({
    "@context": "https://schema.org",
    "@type": "VideoObject",
    name: v.title,
    description: v.description || `${CAT_LABEL[v.category] || v.category} — Flyboy Videography.`,
    thumbnailUrl: thumb(v),
    embedUrl: `https://www.youtube.com/embed/${v.youtube_video_id}`,
    contentUrl: `https://www.youtube.com/watch?v=${v.youtube_video_id}`,
    ...(v.upload_date ? { uploadDate: v.upload_date } : {}),
    ...(isoDur(v.duration_seconds) ? { duration: isoDur(v.duration_seconds) } : {}),
    publisher: {
      "@type": "Organization",
      name: "Flyboy Videography",
      url: "https://flyboyvideography.com",
    },
  }));

  const collectionLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "Flyboy Videography — Portfolio",
    description:
      "Video reels across weddings, birthdays, naming & gender reveals, corporate events and lifestyle work.",
    isPartOf: { "@type": "WebSite", name: "Flyboy Videography", url: "https://flyboyvideography.com" },
    about: MARQUEE.map((label) => ({ "@type": "Thing", name: label })),
  };

  const heroSub = hasReal
    ? (hasPlaceholder
        ? "Real client films, embedded from YouTube. Categories we haven't uploaded yet still show clearly-labelled placeholder tiles."
        : "Real client films across every event we cover — embedded straight from YouTube.")
    : "Placeholder tiles for now — new work drops as it clears client approval.";

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionLd) }} />
      {videoLd.map((ld, i) => (
        <script key={i} type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld) }} />
      ))}

      <HeroPlayer
        kicker="Portfolio"
        headline="Work in motion, moments held still."
        sub={heroSub}
        cta={
          <div className="mt-10 flex flex-wrap gap-3">
            <Link
              href="/services"
              data-testid="portfolio-services-cta"
              className="inline-block rounded-full bg-cream px-8 py-3 font-medium text-ink transition-opacity hover:opacity-85"
            >
              See services &amp; pricing
            </Link>
            <Link
              href="/contact"
              data-testid="portfolio-enquire-cta"
              className="inline-block rounded-full border border-cream/40 px-8 py-3 font-medium text-cream transition-colors hover:bg-cream/10"
            >
              Enquire about your event
            </Link>
          </div>
        }
      />

      <Marquee items={MARQUEE} />

      <div className="border-b border-dune bg-cream">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <p
            data-testid="portfolio-service-area"
            className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink/60"
          >
            Serving {SERVICE_AREA} · Travel elsewhere quoted in advance
          </p>
        </div>
      </div>

      {/* Transparency strip — only shown while ANY placeholder tiles remain,
          and worded to distinguish real embeds from placeholders. Once every
          category has real footage it disappears entirely. */}
      {hasPlaceholder && (
        <div className="border-b border-dune bg-amber-50/60">
          <div className="mx-auto flex max-w-6xl items-start gap-3 px-6 py-4 text-sm text-ink/80">
            <span
              aria-hidden
              className="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full bg-ink text-[11px] font-bold text-cream"
            >
              !
            </span>
            <p data-testid="portfolio-transparency-note">
              {hasReal ? (
                <>
                  <strong className="font-semibold">Some categories show placeholder stills</strong> —
                  free-licence Pexels stock, clearly ribboned, not client work. Tiles
                  without a “Placeholder” ribbon are real client films embedded from YouTube.
                </>
              ) : (
                <>
                  <strong className="font-semibold">These tiles are placeholders</strong> —
                  free-licence stock stills from Pexels, not client work. Real reels drop
                  as soon as they clear approval. Each tile is labelled to avoid confusion.
                </>
              )}
            </p>
          </div>
        </div>
      )}

      <PortfolioGrid tiles={tiles} />

      <section className="relative overflow-hidden border-t border-dune bg-sand">
        <div className="relative mx-auto max-w-6xl px-6 py-16 md:py-20">
          <Reveal>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/70">
              What you&apos;re looking at
            </p>
            <h2 className="mt-3 max-w-2xl font-display text-3xl font-bold tracking-tight md:text-4xl">
              {hasReal
                ? "Real client films — tap any tile to play."
                : "Placeholder tiles — real reels drop as approvals clear."}
            </h2>
            <p className="mt-4 max-w-xl text-ink/70">
              {hasReal
                ? "Video tiles play right here on the page, streamed from YouTube."
                : "Video cards get a play glyph and a runtime badge, stills stay quiet."}
              {hasPlaceholder && " Categories still awaiting footage keep a clearly-labelled placeholder."}
            </p>
            <Link
              href="/services"
              data-testid="portfolio-packages-link"
              className="mt-8 inline-block font-mono text-sm font-bold uppercase tracking-widest underline underline-offset-8"
            >
              Browse packages →
            </Link>
          </Reveal>
        </div>
      </section>
    </>
  );
}
