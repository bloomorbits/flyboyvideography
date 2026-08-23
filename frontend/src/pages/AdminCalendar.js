import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

/*
 * AdminCalendar — single-view aggregator over shoots + invoice due dates.
 * Reads `GET /api/admin/calendar?from=&to=` (see admin_calendar.py).
 *
 * Design:
 *   - Standard month grid, 7 cols. Fetches events for the FULL visible
 *     grid range (first-of-week that shows any day of the month → last-of-week
 *     that shows any day of the month), so leading/trailing days from
 *     adjacent months still show their events.
 *   - Event chips are color-coded by kind via a small KIND_STYLES map.
 *     Unknown kinds fall back to a neutral pill so future _load_X sources
 *     (deliverable_expiry, reminder, …) render sensibly without a UI change.
 *   - Click a chip → navigate to its `link`. Portal deep-links.
 *
 * Same "back-of-house stays dark" theme convention as AdminPricing/AdminSecurity.
 */

const KIND_STYLES = {
  shoot:            { color: "#00E5FF", bg: "rgba(0,229,255,0.12)",  label: "Shoot" },
  invoice_deposit:  { color: "#FFB020", bg: "rgba(255,176,32,0.14)", label: "Deposit" },
  invoice_balance:  { color: "#FF6B6B", bg: "rgba(255,107,107,0.14)", label: "Balance" },
  // Future kinds render with fallback styling automatically — see chipStyle().
};

// Fallback for any unrecognised kind. Additive-safe: new backend kinds
// don't break the UI, they just render with neutral colors until
// someone adds a KIND_STYLES entry.
const FALLBACK_STYLE = { color: "#a1a1aa", bg: "rgba(161,161,170,0.12)", label: "Event" };

function chipStyle(kind) {
  return KIND_STYLES[kind] || FALLBACK_STYLE;
}

// ---------- Date helpers (all UTC-agnostic, calendar semantics) ----------

const iso = (d) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
};

const addDays = (d, n) => {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
};

const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
const endOfMonth = (d) => new Date(d.getFullYear(), d.getMonth() + 1, 0);

// Monday-start week: Mon = 0, Sun = 6
const startOfWeekMon = (d) => addDays(d, -((d.getDay() + 6) % 7));

function fmtMonth(d) {
  return d.toLocaleString("en-GB", { month: "long", year: "numeric" });
}

// ---------- Event chip ----------

function EventChip({ event }) {
  const s = chipStyle(event.kind);
  const inner = (
    <span
      data-testid={`calendar-event-${event.id}`}
      className="block truncate rounded px-1.5 py-0.5 text-[11px] leading-tight"
      style={{ color: s.color, backgroundColor: s.bg, borderLeft: `2px solid ${s.color}` }}
      title={`${s.label}: ${event.title}${event.amount_gbp ? ` — £${event.amount_gbp.toFixed(2)}` : ""}`}
    >
      <span className="font-mono uppercase tracking-wider mr-1" style={{ fontSize: 9, opacity: 0.75 }}>{s.label}</span>
      {event.title}
    </span>
  );
  return event.link ? (
    <Link to={event.link} className="block hover:opacity-80">{inner}</Link>
  ) : (
    inner
  );
}

// ---------- Cell ----------

const MAX_CHIPS = 3;

function DayCell({ dayDate, inMonth, events, isToday }) {
  return (
    <div
      data-testid={`calendar-day-${iso(dayDate)}`}
      className={`min-h-[110px] border border-[#1a1a1d] p-1.5 ${
        inMonth ? "bg-[#0f0f11]" : "bg-[#08080a]"
      }`}
    >
      <div className="mb-1 flex items-baseline justify-between">
        <span
          className={`font-mono text-[11px] ${
            isToday
              ? "rounded bg-[#00E5FF] px-1.5 text-black"
              : inMonth ? "text-zinc-300" : "text-zinc-600"
          }`}
        >
          {dayDate.getDate()}
        </span>
      </div>
      <div className="space-y-0.5">
        {events.slice(0, MAX_CHIPS).map((e) => (
          <EventChip key={e.id} event={e} />
        ))}
        {events.length > MAX_CHIPS && (
          <span
            data-testid={`calendar-more-${iso(dayDate)}`}
            className="block px-1 text-[10px] font-mono uppercase tracking-wider text-zinc-500"
          >
            +{events.length - MAX_CHIPS} more
          </span>
        )}
      </div>
    </div>
  );
}

// ---------- Main page ----------

export default function AdminCalendar() {
  const { profile } = useAuth();
  const [cursor, setCursor] = useState(() => startOfMonth(new Date()));
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  // Build the visible 6-row grid range [firstMon, lastSun]. Fetch events
  // across the FULL grid, not just the month, so trailing/leading days
  // still show their content.
  const { firstMon, lastSun, weeks } = useMemo(() => {
    const s = startOfMonth(cursor);
    const e = endOfMonth(cursor);
    const firstMonD = startOfWeekMon(s);
    // Always render 6 weeks (42 cells) — stable grid regardless of month.
    const lastSunD = addDays(firstMonD, 41);
    const weeksArr = [];
    let d = firstMonD;
    while (d <= lastSunD) {
      const row = [];
      for (let i = 0; i < 7; i++) {
        row.push(new Date(d));
        d = addDays(d, 1);
      }
      weeksArr.push(row);
    }
    return { firstMon: firstMonD, lastSun: lastSunD, weeks: weeksArr };
  }, [cursor]);

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const { data } = await api.get("/admin/calendar", {
        params: { from: iso(firstMon), to: iso(lastSun) },
      });
      setEvents(data.events || []);
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || "Failed to load calendar";
      setErr(msg); toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [firstMon, lastSun]);

  useEffect(() => { load(); }, [load]);

  // Index events by date for O(1) cell lookup
  const eventsByDate = useMemo(() => {
    const idx = {};
    for (const e of events) {
      (idx[e.date] = idx[e.date] || []).push(e);
    }
    return idx;
  }, [events]);

  // Counters for the header pill row — quick "what am I looking at" glance
  const counts = useMemo(() => {
    const c = {};
    for (const e of events) c[e.kind] = (c[e.kind] || 0) + 1;
    return c;
  }, [events]);

  // Admin gate — placed AFTER all hooks so hook order stays stable
  // across renders (React's rules-of-hooks).
  if (profile && profile.role !== "admin") return <Navigate to="/" replace />;

  const today = iso(new Date());
  const currentMonth = cursor.getMonth();

  return (
    <div
      className="-m-6 min-h-[calc(100vh-2rem)] bg-[#0b0b0d] p-6 text-zinc-100"
      data-testid="admin-calendar-page"
    >
      <div className="mx-auto max-w-6xl">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-semibold">Calendar</h1>
            <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
              Shoots · Deposit invoices · Balance invoices
            </p>
          </div>
          <div className="flex items-center gap-2" data-testid="calendar-nav">
            <button
              onClick={() => setCursor((c) => new Date(c.getFullYear(), c.getMonth() - 1, 1))}
              className="rounded-full border border-[#27272a] bg-transparent px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-zinc-300 hover:bg-[#27272a]"
              data-testid="calendar-prev"
            >← Prev</button>
            <button
              onClick={() => setCursor(startOfMonth(new Date()))}
              className="rounded-full border border-[#27272a] bg-transparent px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-zinc-300 hover:bg-[#27272a]"
              data-testid="calendar-today"
            >Today</button>
            <button
              onClick={() => setCursor((c) => new Date(c.getFullYear(), c.getMonth() + 1, 1))}
              className="rounded-full border border-[#27272a] bg-transparent px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-zinc-300 hover:bg-[#27272a]"
              data-testid="calendar-next"
            >Next →</button>
          </div>
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-3">
          <p className="font-display text-lg" data-testid="calendar-month-label">{fmtMonth(cursor)}</p>
          {Object.entries(counts).map(([kind, n]) => {
            const s = chipStyle(kind);
            return (
              <span
                key={kind}
                className="rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest"
                style={{ color: s.color, borderColor: `${s.color}55` }}
                data-testid={`calendar-count-${kind}`}
              >
                {s.label} · {n}
              </span>
            );
          })}
          {loading && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">Loading…</span>
          )}
          {err && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-red-400" data-testid="calendar-error">
              {err}
            </span>
          )}
        </div>

        {/* Weekday header */}
        <div className="grid grid-cols-7 border-b border-[#1a1a1d]">
          {["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d) => (
            <div key={d} className="p-2 text-center font-mono text-[10px] uppercase tracking-widest text-zinc-500">{d}</div>
          ))}
        </div>

        {/* Grid */}
        <div className="grid grid-cols-7" data-testid="calendar-grid">
          {weeks.flat().map((d) => (
            <DayCell
              key={iso(d)}
              dayDate={d}
              inMonth={d.getMonth() === currentMonth}
              events={eventsByDate[iso(d)] || []}
              isToday={iso(d) === today}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
