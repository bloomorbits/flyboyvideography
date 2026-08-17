import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

/*
 * AdminSecurity — deliberately kept in a DARK theme even after the 2026-02
 * portal-restyle (user directive c2: back-of-house tooling stays dark). To
 * keep this decision robust to future token changes on the rest of the
 * portal, this page renders as a self-contained dark island using LITERAL
 * hex values, not the cream/ink theme tokens the shared UI components now
 * ship. The negative margins bleed over the parent <main>'s cream padding
 * so the dark surface fills the visible frame.
 */

const REASON_LABELS = {
  per_email: "Booking · per-email rate",
  per_ip: "Booking · per-IP rate",
  global_attempts: "Booking · global rate",
  locks_per_email: "Booking · per-email locks",
  locks_per_ip: "Booking · per-IP locks",
  locks_global: "Booking · global locks",
  contact_per_email: "Contact · per-email rate",
  contact_per_ip: "Contact · per-IP rate",
  contact_global_attempts: "Contact · global rate",
};

const REASON_TONE = {
  global_attempts: "text-red-400 border-red-400/40",
  locks_global: "text-red-400 border-red-400/40",
  contact_global_attempts: "text-red-400 border-red-400/40",
  per_email: "text-[#FFB020] border-[#FFB020]/40",
  per_ip: "text-[#FFB020] border-[#FFB020]/40",
  locks_per_email: "text-[#FFB020] border-[#FFB020]/40",
  locks_per_ip: "text-[#FFB020] border-[#FFB020]/40",
  contact_per_email: "text-[#00E5FF] border-[#00E5FF]/40",
  contact_per_ip: "text-[#00E5FF] border-[#00E5FF]/40",
};

const fmtTime = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

function ReasonPill({ reason }) {
  const label = REASON_LABELS[reason] || reason;
  const tone = REASON_TONE[reason] || "text-zinc-400 border-zinc-600";
  return (
    <span
      data-testid={`rl-reason-${reason}`}
      className={`inline-block rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest ${tone}`}
    >
      {label}
    </span>
  );
}

function EventsTable({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-[#27272a] bg-[#141416] p-10 text-center text-sm text-zinc-500">
        No rate-limit events in this window.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-sm">
        <thead>
          <tr className="border-b border-[#27272a] text-left font-mono text-[10px] uppercase tracking-widest text-zinc-500">
            <th className="py-2 pr-4">When</th>
            <th className="py-2 pr-4">Reason</th>
            <th className="py-2 pr-4">Email hash</th>
            <th className="py-2 pr-4">IP</th>
            <th className="py-2 pr-4">X-Forwarded-For</th>
            <th className="py-2">User-agent</th>
          </tr>
        </thead>
        <tbody data-testid="rl-events-tbody">
          {events.map((e) => (
            <tr key={e.id} className="border-b border-[#27272a]/50 align-top">
              <td className="py-2 pr-4 text-zinc-300">{fmtTime(e.created_at)}</td>
              <td className="py-2 pr-4"><ReasonPill reason={e.reason} /></td>
              <td className="py-2 pr-4 font-mono text-xs text-zinc-300">{e.email_hash || "—"}</td>
              <td className="py-2 pr-4 font-mono text-xs text-zinc-300">{e.ip || "—"}</td>
              <td className="py-2 pr-4 font-mono text-[10px] text-zinc-500">{e.x_forwarded_for || "—"}</td>
              <td className="py-2 font-mono text-[10px] text-zinc-500">{(e.user_agent || "—").slice(0, 60)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminSecurity() {
  const { profile } = useAuth();
  const isAdmin = profile?.role === "admin";

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchEmail, setSearchEmail] = useState("");
  const [searchResult, setSearchResult] = useState(null);
  const [searching, setSearching] = useState(false);

  const loadRecent = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/rate-limit-events?limit=100");
      setEvents(data.events || []);
      if (data.note) toast.info(data.note);
    } catch (err) {
      toast.error("Failed to load rate-limit events");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) loadRecent();
  }, [isAdmin, loadRecent]);

  const search = async (e) => {
    e.preventDefault();
    if (!searchEmail.trim()) return;
    setSearching(true);
    setSearchResult(null);
    try {
      const { data } = await api.post("/admin/rate-limit-events/search", { email: searchEmail.trim() });
      setSearchResult(data);
      // Deliberately do NOT retain the plaintext email locally after the request
      // resolves — the API returned only the hash, which is what we display.
      setSearchEmail("");
    } catch (err) {
      toast.error("Search failed");
    } finally {
      setSearching(false);
    }
  };

  if (profile && !isAdmin) return <Navigate to="/" replace />;
  if (!profile) return null;

  const cardCls = "rounded-lg border border-[#27272a] bg-[#121214]";
  const inputCls =
    "w-full rounded-md border border-[#27272a] bg-[#0a0a0a] px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:ring-2 focus:ring-[#00E5FF]/50";
  const btnPrimary =
    "rounded-md bg-[#00E5FF] px-5 py-2.5 text-sm font-bold text-black transition-transform hover:bg-[#33EAFF] disabled:cursor-not-allowed disabled:opacity-40";
  const btnSecondary =
    "rounded-md border border-[#27272a] bg-[#18181b] px-5 py-2.5 text-sm font-bold text-zinc-100 hover:bg-[#27272a] disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <div
      data-testid="admin-security-page"
      className="-m-10 min-h-screen bg-[#0a0a0a] p-10 text-zinc-200"
    >
      <div className="rise mb-10">
        <p className="mb-2 font-mono text-[11px] font-bold uppercase tracking-[0.3em] text-[#00E5FF]">Studio internal · security</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-zinc-100 sm:text-4xl">Rate-limit events</h1>
        <p className="mt-3 max-w-2xl text-sm text-zinc-400">
          The last 100 429s the layered rate limiter has fired. Emails are hashed
          (SHA-256[:16]) — paste an email into the search box to see every event
          the same person triggered. Rows are auto-purged after 30 days.
        </p>
      </div>

      <div className={`${cardCls} mb-8 p-6`}>
        <label className="mb-1.5 block font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-zinc-500">
          Search by email
        </label>
        <form onSubmit={search} className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            data-testid="rl-search-email"
            type="email"
            required
            placeholder="suspect@example.com"
            value={searchEmail}
            onChange={(e) => setSearchEmail(e.target.value)}
            className={`${inputCls} flex-1`}
          />
          <button data-testid="rl-search-submit" type="submit" disabled={searching} className={`${btnPrimary} shrink-0`}>
            {searching ? "Searching…" : "Search"}
          </button>
        </form>
        {searchResult && (
          <div className="mt-4" data-testid="rl-search-result">
            <p className="font-mono text-xs uppercase tracking-widest text-zinc-500">
              {searchResult.count} event{searchResult.count === 1 ? "" : "s"} for hash
              <span className="ml-2 text-zinc-300">{searchResult.email_hash}</span>
            </p>
            <div className="mt-3">
              <EventsTable events={searchResult.events} />
            </div>
          </div>
        )}
      </div>

      <div className={`${cardCls} p-6`}>
        <div className="mb-4 flex items-center justify-between">
          <label className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-zinc-500">
            Last 100 events
          </label>
          <button data-testid="rl-refresh" onClick={loadRecent} disabled={loading} className={btnSecondary}>
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
        <EventsTable events={events} />
      </div>
    </div>
  );
}
