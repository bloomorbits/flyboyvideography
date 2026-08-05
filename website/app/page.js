import Link from "next/link";

export const metadata = {
  title: "Flyboy Videography — Cinematic Event Films",
};

export default function Home() {
  return (
    <section className="bg-coal text-cream">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-28 md:py-40">
        <p className="font-mono text-xs uppercase tracking-[0.35em] text-dune">
          Weddings · Birthdays · Ceremonies · Lifestyle · Graduations
        </p>
        <h1 className="max-w-3xl font-display text-5xl font-bold leading-tight tracking-tight md:text-7xl">
          Your day, cut like cinema.
        </h1>
        <p className="max-w-xl text-lg text-dune">
          Cinematic films of the moments that matter — with clear, transparent pricing and fast delivery.
        </p>
        <div>
          <Link
            href="/services"
            data-testid="hero-services-cta"
            className="inline-block rounded-full bg-cream px-8 py-3 font-medium text-ink transition-opacity hover:opacity-85"
          >
            See services &amp; pricing
          </Link>
        </div>
      </div>
    </section>
  );
}
