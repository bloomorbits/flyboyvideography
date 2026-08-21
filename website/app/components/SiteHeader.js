"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";

// Pages that start with a dark hero at the top. Everywhere else the
// header must render in its light/frosted variant from the outset, or
// cream text on cream background makes the nav invisible.
const DARK_HERO_ROUTES = new Set(["/", "/portfolio", "/services"]);

const NAV_LINKS = [
  { href: "/portfolio", label: "Work", testid: "nav-portfolio" },
  { href: "/services", label: "Services & Pricing", testid: "nav-services" },
  { href: "/faq", label: "FAQ", testid: "nav-faq" },
  { href: "/contact", label: "Contact", testid: "nav-contact" },
];

function BurgerIcon({ open }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {open ? (
        <>
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </>
      ) : (
        <>
          <line x1="3" y1="7" x2="21" y2="7" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="17" x2="21" y2="17" />
        </>
      )}
    </svg>
  );
}

export default function SiteHeader() {
  const pathname = usePathname();
  const hasDarkHero = DARK_HERO_ROUTES.has(pathname || "/");
  const [scrolled, setScrolled] = useState(!hasDarkHero);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(!hasDarkHero || window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [hasDarkHero]);

  // Close mobile drawer on route change
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  // Prevent body scroll while drawer is open
  useEffect(() => {
    if (typeof document === "undefined") return;
    if (menuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  // Close drawer on Escape
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e) => e.key === "Escape" && setMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  // Drawer forces a cream-on-ink treatment regardless of scroll state, so
  // colour contrast is deterministic. Header itself keeps its scrolled/hero
  // treatment so the transition into the drawer feels intentional.
  const bookBtnClass = scrolled ? "bg-ink text-cream" : "bg-cream text-ink";

  return (
    <>
      <header
        data-testid="site-header"
        data-scrolled={scrolled}
        className={`fixed top-0 z-50 w-full border-b transition-all duration-300 ${
          scrolled ? "border-dune bg-cream text-ink shadow-[0_4px_20px_rgba(23,20,15,0.06)]" : "border-transparent bg-transparent text-cream"
        }`}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 md:px-6 md:py-4">
          <Link
            href="/"
            data-testid="site-logo"
            className="inline-flex h-11 items-center font-display text-base font-bold tracking-tight md:text-lg"
          >
            FLYBOY<span className="opacity-40">/</span>VIDEOGRAPHY
            <span className="sr-only"> — home</span>
          </Link>

          {/* Desktop nav — hidden below md */}
          <nav className="hidden items-center gap-7 text-sm md:flex">
            {NAV_LINKS.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                data-testid={n.testid}
                className="inline-flex h-11 items-center underline-offset-4 hover:underline"
              >
                {n.label}
              </Link>
            ))}
            <Link
              href="/book"
              data-testid="nav-book"
              className={`inline-flex h-11 items-center rounded-full px-5 font-medium transition-colors duration-300 ${bookBtnClass}`}
            >
              Book
            </Link>
          </nav>

          {/* Mobile controls — visible below md.
              Book button + hamburger. Both are 44px min tap targets. */}
          <div className="flex items-center gap-2 md:hidden">
            <Link
              href="/book"
              data-testid="nav-book"
              className={`inline-flex h-11 items-center rounded-full px-4 text-sm font-medium transition-colors duration-300 ${bookBtnClass}`}
            >
              Book
            </Link>
            <button
              type="button"
              data-testid="mobile-menu-toggle"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav-drawer"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              onClick={() => setMenuOpen((v) => !v)}
              className={`inline-flex h-11 w-11 items-center justify-center rounded-full border transition-colors ${
                scrolled ? "border-ink/20 text-ink hover:bg-ink/5" : "border-cream/30 text-cream hover:bg-cream/10"
              }`}
            >
              <BurgerIcon open={menuOpen} />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile drawer.
          Full-screen, ink background so contrast is always guaranteed.
          Only rendered when menuOpen === true so it isn't in the tab order
          when closed. Every link is min 56px tall for easy thumb-tap. */}
      {menuOpen && (
        <div
          id="mobile-nav-drawer"
          data-testid="mobile-nav-drawer"
          role="dialog"
          aria-modal="true"
          aria-label="Site navigation"
          className="fixed inset-0 z-40 flex flex-col bg-ink text-cream md:hidden"
        >
          <div className="h-[56px]" aria-hidden />
          <nav className="flex flex-1 flex-col gap-1 px-6 pt-6">
            {NAV_LINKS.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                data-testid={`mobile-${n.testid}`}
                className="flex min-h-[56px] items-center border-b border-cream/10 py-3 font-display text-2xl font-semibold"
              >
                {n.label}
              </Link>
            ))}
            <Link
              href="/book"
              data-testid="mobile-nav-book"
              className="mt-6 inline-flex min-h-[56px] items-center justify-center rounded-full bg-cream px-6 font-medium text-ink"
            >
              Book your date
            </Link>
          </nav>
          <p className="px-6 pb-8 pt-6 font-mono text-[11px] uppercase tracking-[0.25em] text-cream/70">
            Leeds · Sheffield · West Yorkshire
          </p>
        </div>
      )}
    </>
  );
}
