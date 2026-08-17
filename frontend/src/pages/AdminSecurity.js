import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Btn, Card, Input, Label, PageHeader, Empty, fmtDate } from "../components/ui";

// Human labels for the `reason` values written by booking.py / contact.py.
// Anything unmapped falls back to the raw reason (forward-compat).
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
  if (!events || events.length === 0) return <Empty text="No rate-limit events in this window." />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-sm">
        <thead>
          <tr className="border-b border-line text-left font-mono text-[10px] uppercase tracking-widest text-zinc-500">
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
            <tr key={e.id} className="border-b border-line/40 align-top">
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

  return (
    <div data-testid="admin-security-page">
      <PageHeader
        kicker="Studio internal · security"
        title="Rate-limit events"
      >
        <p className="text-sm text-zinc-400">
          The last 100 429s the layered rate limiter has fired. Emails are hashed
          (SHA-256[:16]) — paste an email into the search box to see every event
          the same person triggered. Rows are auto-purged after 30 days.
        </p>
      </PageHeader>

      <Card className="mb-8 p-6">
        <Label>Search by email</Label>
        <form onSubmit={search} className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Input
            data-testid="rl-search-email"
            type="email"
            required
            placeholder="suspect@example.com"
            value={searchEmail}
            onChange={(e) => setSearchEmail(e.target.value)}
            className="flex-1"
          />
          <Btn data-testid="rl-search-submit" type="submit" disabled={searching} className="shrink-0">
            {searching ? "Searching…" : "Search"}
          </Btn>
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
      </Card>

      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <Label>Last 100 events</Label>
          <Btn data-testid="rl-refresh" variant="secondary" onClick={loadRecent} disabled={loading}>
            {loading ? "Loading…" : "Refresh"}
          </Btn>
        </div>
        <EventsTable events={events} />
      </Card>
    </div>
  );
}
