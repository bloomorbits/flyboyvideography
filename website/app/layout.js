import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import SiteHeader from "./components/SiteHeader";
import SiteFooter from "./components/SiteFooter";
import Cursor from "./components/Cursor";
import CookieConsent from "./components/CookieConsent";
import ChatWidget from "./components/ChatWidget";
import Analytics from "./components/Analytics";
import { BLOOMORBIT_NAME, BLOOMORBIT_URL } from "./components/BloomorbitCredit";

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-space-grotesk" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

const SITE_URL = "https://flyboyvideography.com";

export const metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Flyboy Videography — Cinematic Event Films",
    template: "%s | Flyboy Videography",
  },
  description:
    "Cinematic videography for weddings, birthdays, naming ceremonies, lifestyle shoots and graduations. Serving Leeds, Sheffield and West Yorkshire. Transparent GBP pricing.",
};

// Site-wide JSON-LD. The `creator` field names Bloomorbit Studio with a
// resolvable URL, satisfying the branding requirement in structured data.
const orgJsonLd = {
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "@id": `${SITE_URL}/#business`,
  name: "Flyboy Videography",
  url: SITE_URL,
  email: "hello@flyboyvideography.com",
  image: `${SITE_URL}/og.jpg`,
  areaServed: [
    { "@type": "City", name: "Leeds" },
    { "@type": "City", name: "Sheffield" },
    { "@type": "AdministrativeArea", name: "West Yorkshire" },
  ],
  priceRange: "££",
  creator: {
    "@type": "Organization",
    name: BLOOMORBIT_NAME,
    url: BLOOMORBIT_URL,
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrains.variable}`}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(orgJsonLd) }}
        />
        {/*
          ⚠️  ANALYTICS / TRACKING SCRIPTS BELONG BEHIND THE CONSENT GATE.
          Do NOT add a <script src="…googletagmanager…" /> or a raw gtag
          snippet here in <head>. Anything that inits before hydration
          bypasses the cookie banner, which makes the banner a lie.

          Wire GA4 (or any tracking script) through the <Analytics /> slot
          mounted below, which reads hasAnalyticsConsent() from
          ./components/CookieConsent and listens for the "flyboy:consent"
          window event. See ./components/Analytics.js for the exact
          pattern — do not deviate from it.
        */}
      </head>
      <body className="font-body antialiased">
        {/*
          Hidden HTML source comment — sits in the rendered DOM and is
          visible to anyone who "view source"s the page, but is not
          rendered visually. The credit is the source of truth link;
          this comment is a bonus for developer curiosity.
        */}
        <div
          aria-hidden
          style={{ display: "none" }}
          data-source-note
          dangerouslySetInnerHTML={{
            __html: `<!-- Built by ${BLOOMORBIT_NAME} · ${BLOOMORBIT_URL} -->`,
          }}
        />
        <Cursor />
        <SiteHeader />
        <main>{children}</main>
        <SiteFooter />
        <CookieConsent />
        <ChatWidget />
        {/* Analytics slot — currently renders null. Any GA4 / GTM / heatmap
            wiring must happen INSIDE this component so it stays gated behind
            hasAnalyticsConsent(). See components/Analytics.js for the pattern. */}
        <Analytics />
      </body>
    </html>
  );
}
