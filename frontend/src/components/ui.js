export const fmtMoney = (n, cur = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n || 0);

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

export const STATUS_STYLES = {
  inquiry: "text-zinc-400 border-zinc-600",
  confirmed: "text-[#00E5FF] border-[#00E5FF]/40",
  shot: "text-[#FFB020] border-[#FFB020]/40",
  in_post: "text-[#FFB020] border-[#FFB020]/40",
  delivered: "text-[#00D26A] border-[#00D26A]/40",
  cancelled: "text-red-400 border-red-400/40",
  draft: "text-zinc-400 border-zinc-600",
  in_review: "text-[#00E5FF] border-[#00E5FF]/40",
  revisions_requested: "text-[#FFB020] border-[#FFB020]/40",
  approved: "text-[#00D26A] border-[#00D26A]/40",
  final_delivered: "text-[#00D26A] border-[#00D26A]/40",
  active: "text-[#00D26A] border-[#00D26A]/40",
  paused: "text-[#FFB020] border-[#FFB020]/40",
  sent: "text-[#00E5FF] border-[#00E5FF]/40",
  paid: "text-[#00D26A] border-[#00D26A]/40",
  overdue: "text-red-400 border-red-400/40",
  void: "text-zinc-500 border-zinc-700",
};

export function StatusPill({ status, testId }) {
  return (
    <span
      data-testid={testId || `status-${status}`}
      className={`inline-block rounded-full border px-3 py-0.5 font-mono text-[11px] uppercase tracking-widest ${STATUS_STYLES[status] || "text-zinc-400 border-zinc-600"}`}
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
      className={`inline-block px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-widest ${
        isBooking ? "bg-[#00E5FF]/10 text-[#00E5FF]" : "bg-[#FFB020]/10 text-[#FFB020]"
      }`}
    >
      {isBooking ? "Booking" : "Retainer"}
    </span>
  );
}

export function Card({ children, className = "", ...props }) {
  return (
    <div className={`rounded-md border border-line bg-surface ${className}`} {...props}>
      {children}
    </div>
  );
}

export function Btn({ children, variant = "primary", className = "", ...props }) {
  const styles =
    variant === "primary"
      ? "bg-accent text-black hover:bg-[#33EAFF]"
      : variant === "danger"
      ? "border border-red-400/40 text-red-400 hover:bg-red-400/10"
      : "border border-line text-white hover:bg-raise";
  return (
    <button
      className={`rounded-md px-5 py-2.5 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-40 ${styles} ${className}`}
      style={{ transition: "transform 0.15s ease, background-color 0.15s ease" }}
      onMouseDown={(e) => (e.currentTarget.style.transform = "scale(0.97)")}
      onMouseUp={(e) => (e.currentTarget.style.transform = "scale(1)")}
      onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
      {...props}
    >
      {children}
    </button>
  );
}

export function Input({ className = "", ...props }) {
  return (
    <input
      className={`w-full rounded-md border border-line bg-raise px-4 py-2.5 text-sm text-white placeholder-zinc-600 outline-none focus:ring-2 focus:ring-accent/50 ${className}`}
      {...props}
    />
  );
}

export function Label({ children }) {
  return <label className="mb-1.5 block font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-zinc-500">{children}</label>;
}

export function PageHeader({ kicker, title, children }) {
  return (
    <div className="rise mb-10 flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="mb-2 font-mono text-[11px] font-bold uppercase tracking-[0.3em] text-accent">{kicker}</p>
        <h1 className="font-display text-4xl font-bold tracking-tighter sm:text-5xl">{title}</h1>
      </div>
      {children}
    </div>
  );
}

export function Empty({ text }) {
  return (
    <Card className="p-12 text-center">
      <p className="text-zinc-500">{text}</p>
    </Card>
  );
}
