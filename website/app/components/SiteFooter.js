import Link from "next/link";
import BloomorbitCredit from "./BloomorbitCredit";

// Service area — reused across footer, /services, /portfolio.
export const SERVICE_AREA = "Leeds · Sheffield · West Yorkshire";

const NAV = [
  { href: "/portfolio", label: "Work" },
  { href: "/services", label: "Services & Pricing" },
  { href: "/faq", label: "FAQ" },
];

const LEGAL = [
  { href: "/privacy", label: "Privacy Policy", testid: "footer-privacy-link" },
  { href: "/terms", label: "Terms & Conditions", testid: "footer-terms-link" },
];

// Instagram / TikTok social links. External so open in new tab.
// Handles are placeholders — update once real accounts are confirmed.
const SOCIAL = [
  {
    href: "https://www.instagram.com/flyboyvideography",
    label: "Instagram",
    testid: "footer-social-instagram",
  },
  {
    href: "https://www.tiktok.com/@flyboyvideography",
    label: "TikTok",
    testid: "footer-social-tiktok",
  },
];

function InstagramGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function TikTokGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M16 3v3.2A5.8 5.8 0 0 0 21 12v3a8.7 8.7 0 0 1-5-1.6V17a5.5 5.5 0 1 1-5.5-5.5c.3 0 .5 0 .8.1v3.1a2.5 2.5 0 1 0 1.7 2.4V3H16z" />
    </svg>
  );
}

const socialGlyph = { Instagram: InstagramGlyph, TikTok: TikTokGlyph };

export default function SiteFooter() {
  return (
    <footer data-testid="site-footer" className="border-t border-dune bg-sand">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-4">
          {/* Brand block */}
          <div className="md:col-span-2">
            <p className="font-display text-lg font-bold tracking-tight">
              FLYBOY<span className="opacity-40">/</span>VIDEOGRAPHY
            </p>
            <p className="mt-3 max-w-sm text-sm text-ink/70">
              Cinematic films of the moments that matter — priced in plain English,
              delivered on time.
            </p>
            <p
              data-testid="footer-service-area"
              className="mt-4 font-mono text-xs uppercase tracking-[0.25em] text-ink/60"
            >
              Serving {SERVICE_AREA}
            </p>
            <p className="mt-4 text-sm">
              <a
                href="mailto:hello@flyboyvideography.com"
                data-testid="footer-email-link"
                className="underline decoration-dotted underline-offset-4 hover:decoration-solid"
              >
                hello@flyboyvideography.com
              </a>
            </p>

            <div className="mt-6 flex items-center gap-3">
              {SOCIAL.map((s) => {
                const Glyph = socialGlyph[s.label];
                return (
                  <a
                    key={s.label}
                    href={s.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={s.label}
                    data-testid={s.testid}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-ink/15 text-ink transition-colors hover:border-ink hover:bg-ink hover:text-cream"
                  >
                    {Glyph ? <Glyph /> : s.label}
                  </a>
                );
              })}
            </div>
          </div>

          {/* Navigate */}
          <div>
            <p className="font-mono text-[11px] font-bold uppercase tracking-[0.25em] text-ink/50">Navigate</p>
            <ul className="mt-4 space-y-2 text-sm">
              {NAV.map((n) => (
                <li key={n.href}>
                  <Link href={n.href} className="hover:underline underline-offset-4">
                    {n.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal */}
          <div>
            <p className="font-mono text-[11px] font-bold uppercase tracking-[0.25em] text-ink/50">Legal</p>
            <ul className="mt-4 space-y-2 text-sm">
              {LEGAL.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    data-testid={l.testid}
                    className="hover:underline underline-offset-4"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-12 flex flex-col gap-3 border-t border-ink/10 pt-6 text-xs text-ink/60 md:flex-row md:items-center md:justify-between">
          <p>© {new Date().getFullYear()} Flyboy Videography. All rights reserved.</p>
          <BloomorbitCredit
            testId="footer-bloomorbit-credit"
            className="text-xs text-ink/60"
            linkClassName="font-medium text-ink underline decoration-dotted underline-offset-4 hover:decoration-solid"
          />
        </div>
      </div>
    </footer>
  );
}
