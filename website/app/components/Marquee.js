export default function Marquee({ items }) {
  const row = (prefix) =>
    items.map((it, i) => (
      <span key={`${prefix}-${it}-${i}`} className="mx-6 flex items-center gap-6">
        {it} <span aria-hidden className="text-ink/30">·</span>
      </span>
    ));
  return (
    <div data-testid="marquee-divider" className="overflow-hidden border-y border-dune bg-cream py-4" aria-hidden>
      <div className="marquee-track flex w-max font-mono text-xs font-bold uppercase tracking-[0.3em] text-ink/50">
        <div className="flex shrink-0">{row("a")}</div>
        <div className="flex shrink-0">{row("b")}</div>
      </div>
    </div>
  );
}
