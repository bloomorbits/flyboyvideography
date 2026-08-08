"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";

// Pages that start with a dark hero at the top. Everywhere else the
// header must render in its light/frosted variant from the outset, or
// cream text on cream background makes the nav invisible.
const DARK_HERO_ROUTES = new Set(["/", "/portfolio", "/services"]);

export default function SiteHeader() {
  const pathname = usePathname();
  const hasDarkHero = DARK_HERO_ROUTES.has(pathname || "/");
  const [scrolled, setScrolled] = useState(!hasDarkHero);

  useEffect(() => {
    const onScroll = () => setScrolled(!hasDarkHero || window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [hasDarkHero]);

  return (
    <header
      data-testid="site-header"
      data-scrolled={scrolled}
      className={`fixed top-0 z-50 w-full border-b transition-all duration-300 ${
        scrolled ? "border-dune bg-cream/85 text-ink backdrop-blur-md" : "border-transparent bg-transparent text-cream"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" data-testid="site-logo" className="font-display text-lg font-bold tracking-tight">
          FLYBOY<span className="opacity-40">/</span>VIDEOGRAPHY
        </Link>
        <nav className="flex items-center gap-5 text-sm md:gap-7">
          <Link href="/portfolio" data-testid="nav-portfolio" className="underline-offset-4 hover:underline">
            Work
          </Link>
          <Link href="/services" data-testid="nav-services" className="underline-offset-4 hover:underline">
            Services &amp; Pricing
          </Link>
          <Link href="/faq" data-testid="nav-faq" className="underline-offset-4 hover:underline">
            FAQ
          </Link>
          <a
            href="mailto:hello@flyboyvideography.com"
            data-testid="nav-enquire"
            className={`rounded-full px-5 py-2 font-medium transition-colors duration-300 ${
              scrolled ? "bg-ink text-cream" : "bg-cream text-ink"
            }`}
          >
            Enquire
          </a>
        </nav>
      </div>
    </header>
  );
}
