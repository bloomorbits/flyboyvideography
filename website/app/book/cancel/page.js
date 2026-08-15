import Link from "next/link";

export const metadata = {
  title: "Booking cancelled",
  description: "Your booking wasn't completed.",
};

export default function CancelPage() {
  return (
    <main className="min-h-screen bg-cream text-ink">
      <div className="mx-auto max-w-2xl px-6 pb-24 pt-24">
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink/60">Booking cancelled</p>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
          No payment was taken.
        </h1>
        <p className="mt-4 text-base leading-relaxed text-ink/70">
          Your booking wasn&apos;t completed. Your date is still open unless someone else grabs it
          in the next few minutes — head back and try again whenever you&apos;re ready.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/book"
            data-testid="cancel-retry-cta"
            className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-cream hover:opacity-90"
          >
            Back to booking →
          </Link>
          <a
            href="mailto:hello@flyboyvideography.com"
            className="inline-flex items-center gap-2 rounded-full border border-ink/25 px-5 py-3 text-sm font-medium text-ink hover:border-ink"
          >
            Email us instead
          </a>
        </div>
      </div>
    </main>
  );
}
