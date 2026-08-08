import Link from "next/link";
import BloomorbitCredit from "./components/BloomorbitCredit";

// Global 404. Kept short and honest; carries the Bloomorbit credit
// because it's a public page and the credit rule is "every public page".

export const metadata = {
  title: "Page not found",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center bg-cream px-6 pt-32">
      <div className="max-w-lg text-center" data-testid="not-found">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/50">
          Error 404
        </p>
        <h1 className="mt-3 font-display text-5xl font-bold tracking-tight md:text-6xl">
          This page slipped the frame.
        </h1>
        <p className="mt-4 text-ink/70">
          The link you followed doesn&rsquo;t exist (or doesn&rsquo;t exist
          any more). Try one of these instead.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/"
            data-testid="not-found-home-link"
            className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-cream hover:bg-ink/90"
          >
            Back to home
          </Link>
          <Link
            href="/portfolio"
            data-testid="not-found-portfolio-link"
            className="rounded-full border border-ink/20 px-6 py-3 text-sm font-medium text-ink hover:border-ink hover:bg-ink hover:text-cream"
          >
            See the work
          </Link>
          <Link
            href="/faq"
            data-testid="not-found-faq-link"
            className="rounded-full border border-ink/20 px-6 py-3 text-sm font-medium text-ink hover:border-ink hover:bg-ink hover:text-cream"
          >
            FAQ
          </Link>
        </div>
        <p className="mt-10 font-mono text-xs uppercase tracking-[0.25em] text-ink/40">
          <BloomorbitCredit
            testId="not-found-bloomorbit-credit"
            linkClassName="text-ink/60 underline decoration-dotted underline-offset-4 hover:decoration-solid hover:text-ink"
          />
        </p>
      </div>
    </div>
  );
}
