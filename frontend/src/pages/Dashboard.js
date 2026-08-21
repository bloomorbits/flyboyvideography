import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import { supabase } from "../lib/supabase";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Btn, Card, Empty, PageHeader, StatusPill, fmtDate } from "../components/ui";

export default function Dashboard() {
  const { profile, schemaMissing } = useAuth();
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState([]);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    if (!profile || schemaMissing) return;
    const count = (t, filters = (q) => q) =>
      filters(supabase.from(t).select("id", { count: "exact", head: true })).then((r) => r.count || 0);
    const [bookings, inReview, subs, unpaid] = await Promise.all([
      count("bookings", (q) => q.not("status", "in", '("delivered","cancelled")')),
      count("deliverables", (q) => q.in("status", ["in_review", "revisions_requested"])),
      count("retainer_subscriptions", (q) => q.eq("status", "active")),
      count("invoices", (q) => q.in("status", ["sent", "overdue"])),
    ]);
    setStats({ bookings, inReview, subs, unpaid });
    const { data } = await supabase.from("deliverables").select("*").order("updated_at", { ascending: false }).limit(5);
    setRecent(data || []);
  }, [profile, schemaMissing]);

  useEffect(() => { load(); }, [load]);

  const seed = async () => {
    setSeeding(true);
    try {
      await api.post("/demo/seed");
      toast.success("Demo project loaded");
      await load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Seeding failed");
    } finally {
      setSeeding(false);
    }
  };

  const isEmpty = stats && stats.bookings + stats.inReview + stats.subs + stats.unpaid === 0 && recent.length === 0;

  const cards = [
    { label: "Active Bookings", value: stats?.bookings, id: "stat-bookings" },
    { label: "Cuts In Review", value: stats?.inReview, id: "stat-in-review" },
    { label: "Active Retainers", value: stats?.subs, id: "stat-retainers" },
    { label: "Open Invoices", value: stats?.unpaid, id: "stat-invoices" },
  ];

  return (
    <div data-testid="dashboard-page">
      <PageHeader kicker="Overview" title={`Welcome back${profile?.full_name ? ", " + profile.full_name.split(" ")[0] : ""}`}>
        {isEmpty && !schemaMissing && (
          <Btn data-testid="seed-demo-btn" onClick={seed} disabled={seeding}>
            <span className="flex items-center gap-2"><Sparkles size={15} /> {seeding ? "Loading…" : "Load demo project"}</span>
          </Btn>
        )}
      </PageHeader>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {cards.map((c, i) => (
          <Card key={c.label} className="card-hover rise p-6" style={{ animationDelay: `${i * 60}ms` }} data-testid={c.id}>
            <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-ink/70">{c.label}</p>
            <p className="mt-3 font-display text-5xl font-extrabold tracking-tighter text-ink">{c.value ?? "—"}</p>
          </Card>
        ))}
      </div>

      <div className="mt-12">
        <h2 className="mb-5 font-display text-2xl font-semibold tracking-tight">Latest deliverables</h2>
        {recent.length === 0 ? (
          <Empty text={schemaMissing ? "Waiting for database setup." : "No deliverables yet. Your draft cuts will land here."} />
        ) : (
          <Card>
            {recent.map((d, i) => (
              <Link
                key={d.id}
                to={`/deliverables/${d.id}`}
                data-testid={`recent-deliverable-${i}`}
                className={`flex items-center justify-between px-6 py-4 hover:bg-sand ${i > 0 ? "border-t border-dune" : ""}`}
                style={{ transition: "background-color 0.15s ease" }}
              >
                <div>
                  <p className="font-semibold">{d.title}</p>
                  <p className="mt-0.5 font-mono text-xs text-ink/70">v{d.version} · updated {fmtDate(d.updated_at?.slice(0, 10))}</p>
                </div>
                <StatusPill status={d.status} />
              </Link>
            ))}
          </Card>
        )}
      </div>
    </div>
  );
}
