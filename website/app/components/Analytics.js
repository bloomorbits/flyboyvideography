"use client";
// Analytics — DELIBERATELY EMPTY UNTIL GA4 (or any tracking script) is wired in.
//
// ─────────────────────────────────────────────────────────────────────────────
//  READ THIS BEFORE ADDING GA4 / GTM / PLAUSIBLE / POSTHOG / ANYTHING ELSE
// ─────────────────────────────────────────────────────────────────────────────
//
// The public site is currently 100% tracking-free. When GA4 (or any analytics
// / marketing / heatmap / session-replay script) is added, it MUST be gated
// behind the visitor's explicit analytics consent — from the FIRST commit
// that introduces it. Not "in a follow-up". Not "we'll add the gate later".
// The gate is what makes the cookie banner truthful.
//
// The gate lives in one place:
//     import { hasAnalyticsConsent } from "./CookieConsent";
//
// The correct pattern (do NOT deviate):
//
//   1. Load the script ONLY after hasAnalyticsConsent() returns true.
//   2. React to the `flyboy:consent` window event the banner dispatches, so
//      a visitor who opts in on a later visit gets analytics started without
//      a full page reload. Also handle the inverse — if they revoke, unload.
//   3. Use next/script `strategy="afterInteractive"` (never `beforeInteractive`
//      or inlined into <head> — that would fire before consent state exists).
//   4. Never proxy the tracking script through a first-party route to bypass
//      cookie categorisation. That's what the ICO calls a dark pattern.
//
// Skeleton for when GA4 gets added (uncomment + replace GA_ID):
//
//     "use client";
//     import Script from "next/script";
//     import { useEffect, useState } from "react";
//     import { hasAnalyticsConsent } from "./CookieConsent";
//
//     const GA_ID = process.env.NEXT_PUBLIC_GA_ID; // e.g. "G-XXXXXXXXXX"
//
//     export default function Analytics() {
//       const [enabled, setEnabled] = useState(false);
//
//       useEffect(() => {
//         const sync = () => setEnabled(hasAnalyticsConsent());
//         sync();
//         window.addEventListener("flyboy:consent", sync);
//         return () => window.removeEventListener("flyboy:consent", sync);
//       }, []);
//
//       if (!GA_ID || !enabled) return null;
//
//       return (
//         <>
//           <Script
//             src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
//             strategy="afterInteractive"
//           />
//           <Script id="ga-init" strategy="afterInteractive">
//             {`window.dataLayer = window.dataLayer || [];
//               function gtag(){dataLayer.push(arguments);}
//               gtag('js', new Date());
//               gtag('config', '${GA_ID}', { anonymize_ip: true });`}
//           </Script>
//         </>
//       );
//     }
//
// Also remember to:
//   - Add NEXT_PUBLIC_GA_ID to Vercel env vars.
//   - Update /app/website/app/privacy/page.js "Who we share it with" to list
//     Google as a processor.
//   - Update docs/CREDENTIAL_ROTATION.md with a rotation entry (the tracking
//     ID itself is not a secret, but the guardrail runbook needs to know).
//   - Add a `NEXT_PUBLIC_GA_ID` row to the env-var table in the README /
//     Vercel setup docs.
//
// Until then, this component intentionally renders nothing.
export default function Analytics() {
  return null;
}
