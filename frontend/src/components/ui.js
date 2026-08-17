export const fmtMoney = (n, cur = "GBP") =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n || 0);

export const fmtDate = (d) =>
  d ? new Date(d + (d.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

export const secondsToTimecode = (s) => {
  if (s === null || s === undefined) return null;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
};

export const parseTimecode = (str) => {
  if (!str) return null;
  const parts = str.split(":").map(Number);
  if (parts.some(isNaN)) return null;
  return parts.length === 2 ? parts[0] * 60 + parts[1] : parts[0];
};

// Status palette — cream-safe per design agent brief (2026-02 restyle).
// Semantic grouping: neutral / progress (accent cyan) / waiting (amber) /
// success (green) / danger (red). Chips are text + light bg + soft border,
// designed to sit legibly on cream/white/sand.
const NEUTRAL = "text-ink/60 bg-ink/5 border-ink/10";
const PROGRESS = "text-[#0E7490] bg-[#0E7490]/10 border-[#0E7490]/20";
const WAITING = "text-[#B45309] bg-[#B45309]/10 border-[#B45309]/20";
const SUCCESS = "text-[#15803D] bg-[#15803D]/10 border-[#15803D]/20";
const DANGER = "text-[#B91C1C] bg-[#B91C1C]/10 border-[#B91C1C]/20";

export const STATUS_STYLES = {
  // Booking
  inquiry: NEUTRAL,
  draft: NEUTRAL,
  confirmed: PROGRESS,
  shot: WAITING,
  in_post: WAITING,
  delivered: SUCCESS,
  final_delivered: SUCCESS,
  cancelled: DANGER,
  // Deliverable
  in_review: PROGRESS,
  revisions_requested: WAITING,
  approved: SUCCESS,
  // Retainer
  active: SUCCESS,
  paused: WAITING,
  // Invoice
  sent: PROGRESS,
  paid: SUCCESS,
  overdue: DANGER,
  void: NEUTRAL,
};

export function StatusPill({ status, testId }) {
  return (
    <span
      data-testid={testId || `status-${status}`}
      className={`inline-block rounded-full border px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-widest ${STATUS_STYLES[status] || NEUTRAL}`}
    >
      {String(status || "").replace(/_/g, " ")}
    </span>
  );
}

export function SourceBadge({ type }) {
  const isBooking = type === "booking";
  return (
    <span
      data-testid={`source-badge-${type}`}
      className={`inline-block rounded-full px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-widest ${
        isBooking
          ? "bg-[#0E7490]/10 text-[#0E7490]"
          : "bg-[#B45309]/10 text-[#B45309]"
      }`}
    >
      {isBooking ? "Booking" : "Retainer"}
    </span>
  );
}

export function Card({ children, className = "", ...props }) {
  return (
    <div
      className={`rounded-xl border border-dune bg-white shadow-[0_2px_8px_rgba(23,20,15,0.04)] ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function Btn({ children, variant = "primary", className = "", ...props }) {
  const styles =
    variant === "primary"
      ? "bg-ink text-cream hover:bg-coal"
      : variant === "danger"
      ? "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
      : "border border-dune bg-white text-ink hover:bg-sand";
  return (
    <button
      className={`rounded-full px-5 py-2.5 text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-40 ${styles} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Input({ className = "", ...props }) {
  return (
    <input
      className={`w-full rounded-lg border border-dune bg-white px-4 py-2.5 text-sm text-ink placeholder-ink/40 outline-none transition-colors focus:border-transparent focus:ring-2 focus:ring-accent ${className}`}
      {...props}
    />
  );
}

export function Label({ children }) {
  return (
    <label className="mb-1.5 block font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-ink/60">
      {children}
    </label>
  );
}

export function PageHeader({ kicker, title, children }) {
  return (
    <div className="rise mb-10 flex flex-wrap items-end justify-between gap-4">
      <div>
        {kicker && (
          <p className="mb-2 font-mono text-[11px] font-bold uppercase tracking-[0.3em] text-accent">
            {kicker}
          </p>
        )}
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">{title}</h1>
      </div>
      {children}
    </div>
  );
}

export function Empty({ text }) {
  return (
    <div className="rounded-xl border border-dashed border-dune bg-sand p-12 text-center">
      <p className="text-sm text-ink/60">{text}</p>
    </div>
  );
}
