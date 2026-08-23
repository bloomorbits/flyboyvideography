import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, NavLink } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

/*
 * AdminDashboard — Nathan's cockpit view.
 *
 * Two bands stacked:
 *   1) Attention  — enquiries, overdue invoices, balance actions, deliverables
 *                   in review, last cron run. Task-oriented; "what needs you now."
 *   2) Schedule   — next 7 days from /api/admin/calendar (shoots + invoices due).
 *
 * Both reuse the aggregators built in sessions 15:
 *   GET /api/admin/dashboard  → attention + cron
 *   GET /api/admin/calendar   → schedule band (limited to today..today+7)
 *
 * Same "back-of-house stays dark" theme as AdminPricing/AdminCalendar.
 * In-page sub-nav lets Nathan jump to Operate/Pricing/Calendar/Security
 * without touching the sidebar Layout.
 */

// ---------- Sub-nav ----------

const SUBNAV = [
  { to: "/admin",          label: "Dashboard", end: true },
  { to: "/admin/operate",  label: "Operate" },
  { to: "/admin/pricing",  label: "Pricing" },
  { to: "/admin/calendar", label: "Calendar" },
  { to: "/admin/security", label: "Security" },
];

function AdminSubNav() {
  return (
    <div className="mb-6 flex flex-wrap gap-1 border-b border-[#1a1a1d] pb-2" data-testid="admin-subnav">
      {SUBNAV.map(({ to, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `rounded-t px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors ${
              isActive ? "bg-[#00E5FF] text-black" : "text-zinc-400 hover:text-zinc-100 hover:bg-[#141416]"
            }`
          }
          data-testid={`admin-subnav-${label.toLowerCase()}`}
        >
          {label}
        </NavLink>
      ))}
    </div>
  );
}

// ---------- Small primitives ----------

const cardCls = "rounded-lg border border-[#27272a] bg-[#141416] p-4";
const tileHeadCls = "mb-3 flex items-baseline justify-between";
const tileTitleCls = "font-display text-base font-semibold text-zinc-100";
const countPillCls = "rounded-full bg-[#27272a] px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest";
const emptyCls = "text-xs italic text-zinc-500";
const rowCls = "flex items-baseline justify-between gap-2 border-t border-[#1a1a1d] py-2 first:border-t-0";
const primaryCls = "text-[13px] text-zinc-100";
const secondaryCls = "font-mono text-[10px] uppercase tracking-widest text-zinc-500";
const linkCls = "text-[11px] font-mono uppercase tracking-widest text-[#00E5FF] hover:underline";

function fmtGbp(n) { return `£${Number(n).toFixed(2)}`; }
function fmtDateShort(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}
function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

// ---------- Tiles ----------

function EnquiriesTile({ tile, onMark }) {
  return (
    <section className={cardCls} data-testid="tile-enquiries">
      <div className={tileHeadCls}>
        <h3 className={tileTitleCls}>New enquiries</h3>
        <span className={countPillCls} style={{ color: tile.count > 0 ? "#00E5FF" : undefined }}>{tile.count}</span>
      </div>
      {tile.items.length === 0 ? (
        <p className={emptyCls}>Nothing waiting on a reply.</p>
      ) : (
        <ul>
          {tile.items.map((e) => (
            <li key={e.id} className={rowCls} data-testid={`enquiry-${e.id}`}>
              <div className="min-w-0 flex-1">
                <p className={primaryCls}>
                  <span className="font-medium">{e.name}</span>
                  <span className="text-zinc-500"> · {e.email}</span>
                </p>
                <p className="mt-0.5 truncate text-[11px] text-zinc-400">{e.message_preview}</p>
                <p className={`mt-0.5 ${secondaryCls}`}>
                  {fmtDateShort(e.created_at)}
                  {e.package_id ? ` · ${e.package_id}` : ""}
                  {e.event_date ? ` · event ${fmtDateShort(e.event_date)}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 flex-col gap-1">
                <button
                  onClick={() => onMark(e.id, "replied")}
                  className={linkCls}
                  data-testid={`enquiry-${e.id}-mark-replied`}
                >
                  Mark replied →
                </button>
                <button
                  onClick={() => onMark(e.id, "archived")}
                  className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 hover:text-zinc-300"
                  data-testid={`enquiry-${e.id}-archive`}
                >
                  Archive
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function OverdueInvoicesTile({ tile }) {
  return (
    <section className={cardCls} data-testid="tile-overdue-invoices">
      <div className={tileHeadCls}>
        <h3 className={tileTitleCls}>Overdue invoices</h3>
        <span className={countPillCls} style={{ color: tile.count > 0 ? "#FF6B6B" : undefined }}>
          {tile.count}{tile.count > 0 ? ` · ${fmtGbp(tile.total_gbp || 0)}` : ""}
        </span>
      </div>
      {tile.items.length === 0 ? (
        <p className={emptyCls}>Nothing overdue.</p>
      ) : (
        <>
          <ul>
            {tile.items.map((i) => (
              <li key={i.id} className={rowCls}>
                <div className="min-w-0 flex-1">
                  <p className={primaryCls}>{i.client_name || "—"}<span className="text-zinc-500"> · {i.invoice_number || i.id.slice(0,8)}</span></p>
                  <p className={`mt-0.5 ${secondaryCls}`}>Due {fmtDateShort(i.due_on)} · {i.purpose}</p>
                </div>
                <p className="text-[13px] font-medium text-zinc-100">{fmtGbp(i.amount_gbp)}</p>
              </li>
            ))}
          </ul>
          <Link to="/invoices" className={`mt-3 inline-block ${linkCls}`} data-testid="overdue-see-all">See all invoices →</Link>
        </>
      )}
    </section>
  );
}

function BalanceActionsTile({ tile }) {
  return (
    <section className={cardCls} data-testid="tile-balance-actions">
      <div className={tileHeadCls}>
        <h3 className={tileTitleCls}>Balance actions</h3>
        <span className={countPillCls} style={{ color: tile.count > 0 ? "#FFB020" : undefined }}>{tile.count}</span>
      </div>
      {tile.items.length === 0 ? (
        <p className={emptyCls}>No balance invoices due in the next week.</p>
      ) : (
        <ul>
          {tile.items.map((i) => (
            <li key={i.id} className={rowCls} data-testid={`balance-${i.id}`}>
              <div className="min-w-0 flex-1">
                <p className={primaryCls}>
                  {i.client_name || "—"}
                  <span className="text-zinc-500"> · {i.invoice_number || i.id.slice(0,8)}</span>
                </p>
                <p className={`mt-0.5 ${secondaryCls}`}>
                  Due {fmtDateShort(i.due_on)} · status {i.status}
                  {i.reminder_queued && (
                    <span className="ml-2 rounded bg-[#FFB020]/15 px-1.5 py-0.5 text-[9px] font-bold text-[#FFB020]" data-testid={`balance-${i.id}-reminder-queued`}>
                      REMINDER QUEUED
                    </span>
                  )}
                  {i.reminder_sent_at && (
                    <span className="ml-2 text-zinc-600">· reminder sent {fmtDateShort(i.reminder_sent_at)}</span>
                  )}
                </p>
              </div>
              <p className="text-[13px] font-medium text-zinc-100">{fmtGbp(i.amount_gbp)}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DeliverablesTile({ tile }) {
  return (
    <section className={cardCls} data-testid="tile-deliverables-in-review">
      <div className={tileHeadCls}>
        <h3 className={tileTitleCls}>Deliverables awaiting you</h3>
        <span className={countPillCls} style={{ color: tile.count > 0 ? "#B08CFF" : undefined }}>{tile.count}</span>
      </div>
      {tile.items.length === 0 ? (
        <p className={emptyCls}>Nothing in review.</p>
      ) : (
        <ul>
          {tile.items.map((d) => (
            <li key={d.id} className={rowCls}>
              <div className="min-w-0 flex-1">
                <p className={primaryCls}>{d.title}<span className="text-zinc-500"> · {d.client_name || "—"}</span></p>
                <p className={`mt-0.5 ${secondaryCls}`}>{d.status.replaceAll("_", " ")} · updated {fmtDateShort(d.updated_at)}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CronTile({ cron }) {
  const daily = cron?.daily_invoicing;
  return (
    <section className={cardCls} data-testid="tile-cron">
      <div className={tileHeadCls}>
        <h3 className={tileTitleCls}>Daily-invoicing cron</h3>
        {daily && (
          <span className={countPillCls} style={{ color: daily.ok ? "#7ED957" : "#FF6B6B" }}>
            {daily.ok ? "OK" : `${daily.error_count} error(s)`}
          </span>
        )}
      </div>
      {!daily ? (
        <p className={emptyCls}>No runs recorded yet — the cron hasn&apos;t fired since Migration 014 was applied.</p>
      ) : (
        <>
          <p className={secondaryCls}>Last run · {fmtDateTime(daily.started_at)} → {fmtDateTime(daily.finished_at)}</p>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px]">
            <span className="text-zinc-500">Invoices created</span>
            <span className="text-zinc-100">{daily.summary?.invoices_created?.length ?? 0}</span>
            <span className="text-zinc-500">Reminders sent</span>
            <span className="text-zinc-100">{daily.summary?.reminders_sent?.length ?? 0}</span>
            <span className="text-zinc-500">Skipped (already invoiced)</span>
            <span className="text-zinc-100">{daily.summary?.invoices_skipped_already_exists?.length ?? 0}</span>
            <span className="text-zinc-500">Skipped (zero balance)</span>
            <span className="text-zinc-100">{daily.summary?.invoices_skipped_zero_balance?.length ?? 0}</span>
            <span className="text-zinc-500">Reminders suppressed (paid manually)</span>
            <span className="text-zinc-100">{daily.summary?.reminders_skipped_paid_manually?.length ?? 0}</span>
          </div>
          {daily.summary?.dry_run && (
            <p className="mt-2 text-[10px] font-mono uppercase tracking-widest text-[#FFB020]">Dry-run</p>
          )}
          {daily.summary?.errors?.length > 0 && (
            <details className="mt-2" data-testid="cron-errors">
              <summary className="cursor-pointer text-[11px] text-red-400">Show errors ({daily.summary.errors.length})</summary>
              <pre className="mt-1 max-h-48 overflow-auto rounded bg-[#0b0b0d] p-2 font-mono text-[10px] text-red-300">
                {JSON.stringify(daily.summary.errors, null, 2)}
              </pre>
            </details>
          )}
        </>
      )}
    </section>
  );
}

// ---------- Schedule band ----------

const KIND_STYLES = {
  shoot:           { color: "#00E5FF", label: "Shoot" },
  invoice_deposit: { color: "#FFB020", label: "Deposit" },
  invoice_balance: { color: "#FF6B6B", label: "Balance" },
};
const FALLBACK_STYLE = { color: "#a1a1aa", label: "Event" };

function ScheduleBand({ events, loading }) {
  const grouped = useMemo(() => {
    const map = new Map();
    for (const e of events) (map.get(e.date) || map.set(e.date, []).get(e.date)).push(e);
    return Array.from(map.entries()).sort(([a],[b]) => a.localeCompare(b));
  }, [events]);

  if (loading) return <p className={emptyCls}>Loading schedule…</p>;
  if (grouped.length === 0) return <p className={emptyCls}>Nothing in the next 7 days.</p>;

  return (
    <div className={cardCls} data-testid="schedule-band">
      <div className={tileHeadCls}>
        <h3 className={tileTitleCls}>Next 7 days</h3>
        <span className={countPillCls}>{events.length} event{events.length === 1 ? "" : "s"}</span>
      </div>
      <ul className="space-y-3">
        {grouped.map(([date, evts]) => (
          <li key={date} data-testid={`schedule-date-${date}`}>
            <p className={`${secondaryCls} mb-1`}>{fmtDateShort(date)} · {new Date(date).toLocaleDateString("en-GB", { weekday: "long" })}</p>
            <ul className="space-y-1">
              {evts.map((e) => {
                const s = KIND_STYLES[e.kind] || FALLBACK_STYLE;
                const inner = (
                  <div className="flex items-center gap-2 rounded border-l-2 bg-[#0b0b0d] px-2 py-1" style={{ borderColor: s.color }}>
                    <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: s.color }}>{s.label}</span>
                    <span className="min-w-0 flex-1 truncate text-[12px] text-zinc-100">{e.title}</span>
                    {e.amount_gbp != null && <span className="text-[11px] font-medium text-zinc-300">{fmtGbp(e.amount_gbp)}</span>}
                  </div>
                );
                return (
                  <li key={e.id} data-testid={`schedule-event-${e.id}`}>
                    {e.link ? <Link to={e.link} className="block hover:opacity-80">{inner}</Link> : inner}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------- Main ----------

function iso(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

export default function AdminDashboard() {
  const { profile } = useAuth();
  const [data, setData] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingEvents, setLoadingEvents] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/dashboard");
      setData(data);
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || "Failed to load dashboard");
    } finally { setLoading(false); }
  }, []);

  const loadSchedule = useCallback(async () => {
    setLoadingEvents(true);
    try {
      const today = new Date();
      const to = new Date(today); to.setDate(to.getDate() + 7);
      const { data } = await api.get("/admin/calendar", { params: { from: iso(today), to: iso(to) } });
      setEvents(data.events || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || "Failed to load schedule");
    } finally { setLoadingEvents(false); }
  }, []);

  useEffect(() => { load(); loadSchedule(); }, [load, loadSchedule]);

  const markEnquiry = useCallback(async (id, status) => {
    try {
      await api.patch(`/admin/enquiries/${id}`, { status });
      toast.success(`Marked ${status}`);
      load(); // refresh the tile counts + top-5
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || "Update failed");
    }
  }, [load]);

  // Admin gate AFTER hooks so rules-of-hooks stays clean
  if (profile && profile.role !== "admin") return <Navigate to="/" replace />;

  return (
    <div className="-m-6 min-h-[calc(100vh-2rem)] bg-[#0b0b0d] p-6 text-zinc-100" data-testid="admin-dashboard-page">
      <div className="mx-auto max-w-6xl">
        <div className="mb-4">
          <h1 className="font-display text-2xl font-semibold">Admin</h1>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
            {profile?.full_name || profile?.email || "…"} · cockpit view
          </p>
        </div>

        <AdminSubNav />

        <section className="mb-6" data-testid="attention-band">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-zinc-500">Needs attention</p>
          {loading || !data ? (
            <p className={emptyCls}>Loading…</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <EnquiriesTile tile={data.attention.enquiries} onMark={markEnquiry} />
              <OverdueInvoicesTile tile={data.attention.overdue_invoices} />
              <BalanceActionsTile tile={data.attention.balance_actions} />
              <DeliverablesTile tile={data.attention.deliverables_in_review} />
              <div className="md:col-span-2">
                <CronTile cron={data.cron} />
              </div>
            </div>
          )}
        </section>

        <section data-testid="schedule-band-wrap">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-zinc-500">Schedule</p>
          <ScheduleBand events={events} loading={loadingEvents} />
        </section>
      </div>
    </div>
  );
}
