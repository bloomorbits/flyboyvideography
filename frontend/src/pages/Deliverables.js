import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Film } from "lucide-react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { Card, Empty, PageHeader, SourceBadge, StatusPill, fmtDate } from "../components/ui";

export default function Deliverables() {
  const { schemaMissing } = useAuth();
  const [rows, setRows] = useState([]);

  useEffect(() => {
    if (schemaMissing) return;
    supabase.from("deliverables").select("*").order("updated_at", { ascending: false })
      .then(({ data }) => setRows(data || []));
  }, [schemaMissing]);

  return (
    <div data-testid="deliverables-page">
      <PageHeader kicker="Draft cuts & finals" title="Deliverables" />
      {rows.length === 0 ? (
        <Empty text="No deliverables yet. Draft cuts land here when your editor uploads them." />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
          {rows.map((d, i) => (
            <Link key={d.id} to={`/deliverables/${d.id}`} data-testid={`deliverable-card-${i}`}>
              <Card className="card-hover rise h-full p-6" style={{ animationDelay: `${i * 50}ms` }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent/10">
                    <Film size={18} className="text-accent" />
                  </div>
                  <SourceBadge type={d.booking_id ? "booking" : "subscription"} />
                </div>
                <p className="mt-4 font-display text-lg font-bold tracking-tight">{d.title}</p>
                <p className="mt-1 font-mono text-xs text-ink/50">Version {d.version} · {fmtDate(d.updated_at?.slice(0, 10))}</p>
                <div className="mt-5 border-t border-dune pt-4">
                  <StatusPill status={d.status} />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
