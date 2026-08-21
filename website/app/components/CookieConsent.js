"use client";
// CookieConsent — granular opt-in banner.
//
// Behaviour:
//   - On first visit (no `flyboy_consent` key in localStorage) the banner
//     appears fixed to the bottom of the viewport.
//   - Categories: `necessary` (always on, cannot be disabled), `analytics`
//     (default OFF, requires explicit opt-in).
//   - Three actions: "Only necessary" (records analytics=false),
//     "Accept all" (records analytics=true), "Manage" (expands checkboxes).
//   - Result is stored in localStorage as:
//       { necessary: true, analytics: bool, ts: ISO string, v: 1 }
//   - `hasAnalyticsConsent()` helper is exported so any future analytics
//     script loader can gate on it. Until it returns true, no third-party
//     tracking script may be injected into the DOM.
//
// Current state of the site: no analytics scripts are wired in yet, so
// the "block tracking until consent" requirement is trivially satisfied.
// The banner exists so we're already compliant on the day analytics are
// switched on — no scramble later.

import { useEffect, useState } from "react";
import Link from "next/link";

const STORAGE_KEY = "flyboy_consent";
const CONSENT_VERSION = 1;

function readConsent() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed.v !== CONSENT_VERSION) return null; // invalidate old shape
    return parsed;
  } catch {
    return null;
  }
}

function writeConsent(analytics) {
  if (typeof window === "undefined") return;
  const value = {
    v: CONSENT_VERSION,
    necessary: true,
    analytics: Boolean(analytics),
    ts: new Date().toISOString(),
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  // Broadcast so any listener can react (e.g. an analytics loader added later).
  window.dispatchEvent(new CustomEvent("flyboy:consent", { detail: value }));
}

/** Returns true if the visitor has explicitly opted in to analytics. */
export function hasAnalyticsConsent() {
  const c = readConsent();
  return Boolean(c && c.analytics === true);
}

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [analytics, setAnalytics] = useState(false);

  useEffect(() => {
    if (readConsent() === null) setVisible(true);
  }, []);

  if (!visible) return null;

  const done = (analyticsChoice) => {
    writeConsent(analyticsChoice);
    setVisible(false);
  };

  return (
    <div
      data-testid="cookie-consent"
      role="dialog"
      aria-label="Cookie consent"
      className="fixed inset-x-3 bottom-3 z-[60] mx-auto max-w-3xl rounded-xl border border-ink/15 bg-cream/95 p-5 shadow-2xl backdrop-blur-md md:inset-x-6 md:bottom-6 md:p-6"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between md:gap-6">
        <div className="text-sm text-ink/85">
          <p className="font-display text-base font-semibold text-ink">Cookies on this site</p>
          <p className="mt-1.5 leading-relaxed">
            We use essential cookies to make this site work. With your permission,
            we&rsquo;d also like to use analytics cookies to understand how visitors
            navigate the site so we can improve it. Analytics stay off unless you
            explicitly opt in.{" "}
            <Link
              href="/privacy"
              data-testid="cookie-consent-privacy-link"
              className="underline underline-offset-4"
            >
              Read our privacy policy
            </Link>
            .
          </p>

          {expanded && (
            <div data-testid="cookie-consent-preferences" className="mt-4 space-y-2 rounded-md border border-ink/10 bg-white/60 p-3">
              <label className="flex items-start gap-3 text-sm">
                <input
                  type="checkbox"
                  checked
                  disabled
                  data-testid="cookie-toggle-necessary"
                  className="mt-1 h-4 w-4 accent-ink"
                  aria-label="Necessary cookies (always on)"
                />
                <span>
                  <span className="font-semibold">Necessary</span>
                  <span className="ml-2 rounded-sm bg-ink/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-ink/70">Always on</span>
                  <span className="mt-0.5 block text-ink/70">Required for basic site navigation and remembering your consent choice.</span>
                </span>
              </label>
              <label className="flex items-start gap-3 text-sm">
                <input
                  type="checkbox"
                  checked={analytics}
                  onChange={(e) => setAnalytics(e.target.checked)}
                  data-testid="cookie-toggle-analytics"
                  className="mt-1 h-4 w-4 accent-ink"
                  aria-label="Analytics cookies"
                />
                <span>
                  <span className="font-semibold">Analytics</span>
                  <span className="mt-0.5 block text-ink/70">Anonymised page-view and interaction data so we can improve the site. No cross-site tracking, no advertising.</span>
                </span>
              </label>
            </div>
          )}
        </div>

        <div className="flex flex-shrink-0 flex-wrap gap-2 md:flex-col md:items-stretch">
          {expanded ? (
            <>
              <button
                data-testid="cookie-consent-save"
                onClick={() => done(analytics)}
                className="rounded-full bg-ink px-5 py-2 text-sm font-medium text-cream hover:bg-ink/90"
              >
                Save choices
              </button>
              <button
                data-testid="cookie-consent-collapse"
                onClick={() => setExpanded(false)}
                className="rounded-full border border-ink/20 px-5 py-2 text-sm font-medium text-ink hover:border-ink/50"
              >
                Back
              </button>
            </>
          ) : (
            <>
              <button
                data-testid="cookie-consent-accept-all"
                onClick={() => done(true)}
                className="inline-flex min-h-[44px] items-center justify-center rounded-full bg-ink px-5 py-2 text-sm font-medium text-cream hover:bg-ink/90"
              >
                Accept all
              </button>
              <button
                data-testid="cookie-consent-necessary-only"
                onClick={() => done(false)}
                className="inline-flex min-h-[44px] items-center justify-center rounded-full border border-ink/20 px-5 py-2 text-sm font-medium text-ink hover:border-ink/50"
              >
                Only necessary
              </button>
              <button
                data-testid="cookie-consent-manage"
                onClick={() => setExpanded(true)}
                className="inline-flex min-h-[44px] items-center justify-center rounded-full px-5 py-2 text-sm font-medium text-ink/70 underline underline-offset-4 hover:text-ink"
              >
                Manage
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
