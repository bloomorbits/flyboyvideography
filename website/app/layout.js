import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-space-grotesk" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

export const metadata = {
  metadataBase: new URL("https://flyboyvideography.com"),
  title: {
    default: "Flyboy Videography — Cinematic Event Films",
    template: "%s | Flyboy Videography",
  },
  description:
    "Cinematic videography for weddings, birthdays, naming ceremonies, lifestyle shoots and graduations. UK-based, transparent GBP pricing.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrains.variable}`}>
      <body className="font-body antialiased">
        <header className="sticky top-0 z-50 border-b border-dune bg-cream/90 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" data-testid="site-logo" className="font-display text-lg font-bold tracking-tight">
              FLYBOY<span className="opacity-40">/</span>VIDEOGRAPHY
            </Link>
            <nav className="flex items-center gap-8 text-sm">
              <Link href="/services" data-testid="nav-services" className="hover:underline underline-offset-4">
                Services &amp; Pricing
              </Link>
              <a
                href="mailto:hello@flyboyvideography.com"
                data-testid="nav-enquire"
                className="rounded-full bg-ink px-5 py-2 font-medium text-cream transition-opacity hover:opacity-80"
              >
                Enquire
              </a>
            </nav>
          </div>
        </header>
        <main>{children}</main>
        <footer className="border-t border-dune bg-sand">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-10 text-sm">
            <p className="font-display font-bold">FLYBOY/VIDEOGRAPHY</p>
            <p className="font-mono text-xs text-ink/60">
              A 50% deposit secures your date · balance due 3–5 days before your event
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
