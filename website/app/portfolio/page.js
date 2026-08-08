import Link from "next/link";
import HeroPlayer from "../components/HeroPlayer";
import Marquee from "../components/Marquee";
import Reveal from "../components/Reveal";
import PortfolioGrid from "../components/PortfolioGrid";
import { CATEGORIES } from "../../lib/portfolio";

export const metadata = {
  title: "Portfolio",
  description:
    "Flyboy Videography portfolio — weddings, birthday celebrations, naming ceremonies, gender reveals, corporate events and lifestyle reels. Placeholder set while new work is uploaded.",
};

const MARQUEE = CATEGORIES.filter((c) => c.id !== "all").map((c) => c.label);

export default function PortfolioPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "Flyboy Videography — Portfolio",
    description:
      "A hybrid grid of video reels and stills across weddings, birthdays, naming & gender reveals, corporate events and lifestyle work.",
    isPartOf: {
      "@type": "WebSite",
      name: "Flyboy Videography",
      url: "https://flyboyvideography.com",
    },
    about: MARQUEE.map((label) => ({ "@type": "Thing", name: label })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <HeroPlayer
        kicker="Portfolio · Weddings · Birthdays · Naming · Corporate · Lifestyle"
        headline="Work in motion, moments held still."
        sub="A hybrid look at reels and stills across every event we cover. Placeholder tiles for now — new work drops as it clears client approval."
        cta={
          <div className="mt-10 flex flex-wrap gap-3">
            <Link
              href="/services"
              data-testid="portfolio-services-cta"
              className="inline-block rounded-full bg-cream px-8 py-3 font-medium text-ink transition-opacity hover:opacity-85"
            >
              See services &amp; pricing
            </Link>
            <a
              href="mailto:hello@flyboyvideography.com"
              data-testid="portfolio-enquire-cta"
              className="inline-block rounded-full border border-cream/40 px-8 py-3 font-medium text-cream transition-colors hover:bg-cream/10"
            >
              Enquire about your event
            </a>
          </div>
        }
      />

      <Marquee items={MARQUEE} />

      {/* Transparency strip — visible to every visitor before they see the grid.
          Set once, so no visitor can mistake the placeholder set for real work. */}
      <div className="border-b border-dune bg-amber-50/60">
        <div className="mx-auto flex max-w-6xl items-start gap-3 px-6 py-4 text-sm text-ink/80">
          <span
            aria-hidden
            className="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full bg-ink text-[11px] font-bold text-cream"
          >
            !
          </span>
          <p data-testid="portfolio-transparency-note">
            <strong className="font-semibold">These tiles are placeholders</strong> —
            free-licence stock stills sourced from Pexels, not client work. Real
            reels drop as soon as they clear approval. Each tile is labelled to
            avoid any confusion.
          </p>
        </div>
      </div>

      <PortfolioGrid />

      <section className="relative overflow-hidden border-t border-dune bg-sand">
        <div className="relative mx-auto max-w-6xl px-6 py-16 md:py-20">
          <Reveal>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/50">
              What you're looking at
            </p>
            <h2 className="mt-3 max-w-2xl font-display text-3xl font-bold tracking-tight md:text-4xl">
              Placeholder tiles — real reels drop as approvals clear.
            </h2>
            <p className="mt-4 max-w-xl text-ink/70">
              Video cards get a play glyph and a runtime badge, stills stay quiet.
              Filter by category above to see how the mix reads for each event type.
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
