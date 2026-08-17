import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { Card, Empty, PageHeader, StatusPill, fmtDate, fmtMoney } from "../components/ui";

export default function Retainers() {
  const { schemaMissing } = useAuth();
  const [rows, setRows] = useState([]);

  useEffect(() => {
    if (schemaMissing) return;
    supabase.from("retainer_subscriptions").select("*").order("created_at", { ascending: false })
      .then(({ data }) => setRows(data || []));
  }, [schemaMissing]);

  return (
    <div data-testid="retainers-page">
      <PageHeader kicker="Recurring packages" title="Retainers" />
      {rows.length === 0 ? (
        <Empty text="No retainer subscriptions yet." />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {rows.map((s, i) => (
            <Card key={s.id} className="card-hover rise p-7" style={{ animationDelay: `${i * 50}ms` }} data-testid={`retainer-card-${i}`}>
              <div className="flex items-start justify-between">
                <p className="font-display text-2xl font-bold tracking-tight">{s.package_name}</p>
                <StatusPill status={s.status} />
              </div>
              <p className="mt-4 font-display text-4xl font-extrabold tracking-tighter text-accent">
                {fmtMoney(s.monthly_price)}<span className="text-base font-medium text-ink/50">/mo</span>
              </p>
              <div className="mt-6 grid grid-cols-3 gap-4 border-t border-dune pt-5 text-sm">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-ink/50">Videos / mo</p>
                  <p className="mt-1 text-ink/70">{s.videos_per_month}</p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-ink/50">Started</p>
                  <p className="mt-1 text-ink/70">{fmtDate(s.started_on)}</p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-ink/50">Renews</p>
                  <p className="mt-1 text-ink/70">{fmtDate(s.renews_on)}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
