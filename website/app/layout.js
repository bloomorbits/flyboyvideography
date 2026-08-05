import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import SiteHeader from "./components/SiteHeader";
import Cursor from "./components/Cursor";

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
        <Cursor />
        <SiteHeader />
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
