import BloomorbitCredit from "./components/BloomorbitCredit";

// Global loading UI. Next.js renders this while server components are
// streaming in. Carries the Bloomorbit credit as the fade-in line the
// user briefly sees.

export default function Loading() {
  return (
    <div
      data-testid="loading-screen"
      className="flex min-h-[70vh] flex-col items-center justify-center bg-cream px-6 pt-32"
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="inline-block h-2 w-2 animate-pulse rounded-full bg-ink"
          style={{ animationDelay: "0ms" }}
        />
        <span
          aria-hidden
          className="inline-block h-2 w-2 animate-pulse rounded-full bg-ink"
          style={{ animationDelay: "150ms" }}
        />
        <span
          aria-hidden
          className="inline-block h-2 w-2 animate-pulse rounded-full bg-ink"
          style={{ animationDelay: "300ms" }}
        />
      </div>
      <p className="mt-6 font-display text-lg font-medium tracking-tight text-ink/70">
        Cueing up your frame…
      </p>
      <p
        data-testid="loading-bloomorbit-line"
        className="mt-4 animate-[fadeIn_1.6s_ease-out] font-mono text-[11px] uppercase tracking-[0.3em] text-ink/45"
      >
        <BloomorbitCredit
          prefix="Crafted by"
          testId="loading-bloomorbit-credit"
          linkClassName="text-ink/60 underline decoration-dotted underline-offset-4 hover:decoration-solid hover:text-ink"
        />
      </p>
    </div>
  );
}
