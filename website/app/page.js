import Link from "next/link";
import HeroPlayer from "./components/HeroPlayer";
import Marquee from "./components/Marquee";
import Reveal from "./components/Reveal";
import HomePortfolioHighlights from "./components/HomePortfolioHighlights";

export const metadata = {
  title: "Flyboy Videography — Cinematic Event Films",
};

const CATEGORIES = ["Weddings", "Birthdays", "Naming Ceremonies", "Gender Reveals", "Lifestyle", "Graduations", "Extra Reels"];

export default function Home() {
  return (
    <>
      <HeroPlayer
        kicker="Weddings · Birthdays · Ceremonies · Lifestyle · Graduations"
        headline="Turning visuals into value"
        sub="Cinematic films of the moments that matter — with clear, transparent pricing and fast delivery."
        cta={
          <div className="mt-10 flex flex-wrap gap-3">
            <Link
              href="/services"
              data-testid="hero-services-cta"
              className="inline-block rounded-full bg-cream px-8 py-3 font-medium text-ink transition-opacity hover:opacity-85"
            >
              See services &amp; pricing
            </Link>
            <Link
              href="/portfolio"
              data-testid="hero-portfolio-cta"
              className="inline-block rounded-full border border-cream/40 px-8 py-3 font-medium text-cream transition-colors hover:bg-cream/10"
            >
              See the work
            </Link>
          </div>
        }
      />
      <Marquee items={CATEGORIES} />
      <HomePortfolioHighlights />

      {/* Compact CTA strip. Was previously py-20 with content only in the
          top-left, producing ~350px of empty space before the footer. Now
          a two-column layout: heading+copy on the left, action stack on
          the right, with lean py-14 vertical rhythm. */}
      <section className="border-t border-dune bg-sand">
        <div className="mx-auto max-w-6xl px-6 py-14 md:py-16">
          <div className="grid grid-cols-1 items-center gap-8 md:grid-cols-2">
            <Reveal>
              <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">
                One videographer. Every milestone. Priced in plain English.
              </h2>
              <p className="mt-4 max-w-xl text-ink/70">
                From full wedding days to ninety-second reels — pick a package,
                add extras only if you need them. No hidden fees, no surprise
                travel charges within the service area.
              </p>
            </Reveal>
            <Reveal delay={120}>
              <div className="flex flex-col items-start gap-3 md:items-end">
                <Link
                  href="/services"
                  data-testid="home-packages-link"
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-medium text-cream hover:bg-ink/90"
                >
                  Browse packages <span aria-hidden className="font-mono">→</span>
                </Link>
                <Link
                  href="/faq"
                  data-testid="home-faq-link"
                  className="inline-flex items-center gap-2 rounded-full border border-ink/20 px-6 py-3 text-sm font-medium text-ink hover:border-ink hover:bg-ink hover:text-cream"
                >
                  Read the FAQ <span aria-hidden className="font-mono">→</span>
                </Link>
                <a
                  href="mailto:hello@flyboyvideography.com"
                  data-testid="home-enquire-link"
                  className="inline-flex items-center gap-2 px-1 py-1 text-sm font-medium text-ink underline decoration-dotted underline-offset-4 hover:decoration-solid"
                >
                  hello@flyboyvideography.com
                </a>
              </div>
            </Reveal>
          </div>
        </div>
      </section>
    </>
  );
}
