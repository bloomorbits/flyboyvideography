import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { Card, Empty, PageHeader, SourceBadge, StatusPill, fmtDate, fmtMoney } from "../components/ui";

export default function Invoices() {
  const { schemaMissing } = useAuth();
  const [rows, setRows] = useState([]);

  useEffect(() => {
    if (schemaMissing) return;
    supabase.from("invoices").select("*").order("issued_on", { ascending: false })
      .then(({ data }) => setRows(data || []));
  }, [schemaMissing]);

  return (
    <div data-testid="invoices-page">
      <PageHeader kicker="Billing" title="Invoices" />
      {rows.length === 0 ? (
        <Empty text="No invoices yet." />
      ) : (
        <Card>
          <div className="grid grid-cols-12 gap-4 border-b border-line px-6 py-3 font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-500">
            <span className="col-span-3">Invoice</span>
            <span className="col-span-2">Source</span>
            <span className="col-span-2">Amount</span>
            <span className="col-span-2">Issued</span>
            <span className="col-span-2">Due</span>
            <span className="col-span-1 text-right">Status</span>
          </div>
          {rows.map((inv, i) => (
            <div key={inv.id} className="rise grid grid-cols-12 items-center gap-4 border-b border-line px-6 py-4 last:border-b-0 hover:bg-raise" style={{ animationDelay: `${i * 40}ms`, transition: "background-color 0.15s ease" }} data-testid={`invoice-row-${i}`}>
              <span className="col-span-3 font-mono text-sm font-bold text-white">{inv.invoice_number}</span>
              <span className="col-span-2"><SourceBadge type={inv.source_type} /></span>
              <span className="col-span-2 font-display text-lg font-bold tracking-tight">{fmtMoney(inv.amount, inv.currency)}</span>
              <span className="col-span-2 text-sm text-zinc-400">{fmtDate(inv.issued_on)}</span>
              <span className="col-span-2 text-sm text-zinc-400">{fmtDate(inv.due_on)}</span>
              <span className="col-span-1 text-right"><StatusPill status={inv.status} /></span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
