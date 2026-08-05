import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { Btn, Card, Empty, Input, Label, PageHeader, StatusPill, fmtDate, fmtMoney } from "../components/ui";

export default function Bookings() {
  const { profile, schemaMissing } = useAuth();
  const [rows, setRows] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", shoot_type: "", shoot_date: "", location: "", notes: "" });

  const load = useCallback(async () => {
    if (schemaMissing) return;
    const { data } = await supabase.from("bookings").select("*").order("created_at", { ascending: false });
    setRows(data || []);
  }, [schemaMissing]);

  useEffect(() => { load(); }, [load]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    const { error } = await supabase.from("bookings").insert({
      client_id: profile.id,
      title: form.title,
      shoot_type: form.shoot_type || null,
      shoot_date: form.shoot_date || null,
      location: form.location || null,
      notes: form.notes || null,
      status: "inquiry",
    });
    if (error) return toast.error(error.message);
    toast.success("Shoot request submitted");
    setForm({ title: "", shoot_type: "", shoot_date: "", location: "", notes: "" });
    setShowForm(false);
    load();
  };

  return (
    <div data-testid="bookings-page">
      <PageHeader kicker="One-off shoots" title="Bookings">
        <Btn data-testid="new-booking-btn" onClick={() => setShowForm(!showForm)}>
          <span className="flex items-center gap-2"><Plus size={15} /> Request a shoot</span>
        </Btn>
      </PageHeader>

      {showForm && (
        <Card className="rise mb-8 p-6">
          <form onSubmit={submit} className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <div className="md:col-span-2">
              <Label>Project title</Label>
              <Input data-testid="booking-title-input" value={form.title} onChange={set("title")} placeholder="Brand film for spring launch" required />
            </div>
            <div>
              <Label>Shoot type</Label>
              <Input data-testid="booking-type-input" value={form.shoot_type} onChange={set("shoot_type")} placeholder="Brand Film / Product / Event" />
            </div>
            <div>
              <Label>Preferred date</Label>
              <Input data-testid="booking-date-input" type="date" value={form.shoot_date} onChange={set("shoot_date")} />
            </div>
            <div className="md:col-span-2">
              <Label>Location</Label>
              <Input data-testid="booking-location-input" value={form.location} onChange={set("location")} placeholder="Studio, on-site, remote…" />
            </div>
            <div className="md:col-span-2">
              <Label>Notes</Label>
              <Input data-testid="booking-notes-input" value={form.notes} onChange={set("notes")} placeholder="Anything we should know" />
            </div>
            <div>
              <Btn data-testid="booking-submit-btn" type="submit">Submit request</Btn>
            </div>
          </form>
        </Card>
      )}

      {rows.length === 0 ? (
        <Empty text="No bookings yet. Request your first shoot above." />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {rows.map((b, i) => (
            <Card key={b.id} className="card-hover rise p-6" style={{ animationDelay: `${i * 50}ms` }} data-testid={`booking-card-${i}`}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-display text-xl font-bold tracking-tight">{b.title}</p>
                  <p className="mt-1 font-mono text-xs uppercase tracking-widest text-zinc-500">{b.shoot_type || "Shoot"}</p>
                </div>
                <StatusPill status={b.status} />
              </div>
              <div className="mt-5 grid grid-cols-3 gap-4 border-t border-line pt-4 text-sm">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">Date</p>
                  <p className="mt-1 text-zinc-300">{fmtDate(b.shoot_date)}</p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">Location</p>
                  <p className="mt-1 truncate text-zinc-300">{b.location || "—"}</p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">Budget</p>
                  <p className="mt-1 text-zinc-300">{b.budget ? fmtMoney(b.budget) : "TBD"}</p>
                </div>
              </div>
              {b.notes && <p className="mt-4 text-sm text-zinc-400">{b.notes}</p>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
