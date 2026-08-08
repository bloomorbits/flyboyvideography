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
      <section className="mx-auto max-w-6xl px-6 py-20">
        <Reveal>
          <h2 className="max-w-2xl font-display text-3xl font-bold tracking-tight md:text-4xl">
            One videographer. Every milestone. Priced in plain English.
          </h2>
          <p className="mt-4 max-w-xl text-ink/70">
            From full wedding days to ninety-second reels — pick a package, add extras only if you need them.
          </p>
          <Link href="/services" data-testid="home-packages-link" className="mt-8 inline-block font-mono text-sm font-bold uppercase tracking-widest underline underline-offset-8">
            Browse packages →
          </Link>
        </Reveal>
      </section>
    </>
  );
}
