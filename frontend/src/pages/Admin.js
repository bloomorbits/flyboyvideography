import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { supabase } from "../lib/supabase";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Btn, Card, Input, Label, PageHeader, StatusPill, fmtDate } from "../components/ui";

const DELIV_STATUSES = ["draft", "in_review", "revisions_requested", "approved", "final_delivered"];

const selectCls = "w-full rounded-md border border-line bg-raise px-4 py-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-accent/50";

export default function Admin() {
  const { profile } = useAuth();
  const [clients, setClients] = useState([]);
  const [selected, setSelected] = useState("");
  const [bookings, setBookings] = useState([]);
  const [subs, setSubs] = useState([]);
  const [delivs, setDelivs] = useState([]);
  const [tab, setTab] = useState("deliverable");
  const [form, setForm] = useState({});
  const [audit, setAudit] = useState([]);

  const isAdmin = profile?.role === "admin";

  const loadAudit = useCallback(() => {
    api.get("/admin/erasure-audit").then(({ data }) => setAudit(data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    api.get("/admin/clients").then(({ data }) => setClients(data)).catch(() => toast.error("Failed to load clients"));
    loadAudit();
  }, [isAdmin, loadAudit]);

  const loadClientData = useCallback(async (cid) => {
    if (!cid) return;
    const [b, s, d] = await Promise.all([
      supabase.from("bookings").select("*").eq("client_id", cid),
      supabase.from("retainer_subscriptions").select("*").eq("client_id", cid),
      supabase.from("deliverables").select("*").eq("client_id", cid).order("updated_at", { ascending: false }),
    ]);
    setBookings(b.data || []);
    setSubs(s.data || []);
    setDelivs(d.data || []);
  }, []);

  useEffect(() => { loadClientData(selected); }, [selected, loadClientData]);

  if (profile && !isAdmin) return <Navigate to="/" replace />;
  if (!profile) return null;

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (tab === "booking") {
        await api.post("/admin/bookings", { client_id: selected, title: form.title, shoot_type: form.shoot_type, shoot_date: form.shoot_date || null, location: form.location, status: form.status || "confirmed", budget: form.budget ? Number(form.budget) : null });
      } else if (tab === "subscription") {
        await api.post("/admin/subscriptions", { client_id: selected, package_name: form.package_name, monthly_price: Number(form.monthly_price || 0), videos_per_month: Number(form.videos_per_month || 1), renews_on: form.renews_on || null });
      } else if (tab === "deliverable") {
        await api.post("/admin/deliverables", { client_id: selected, title: form.title, booking_id: form.booking_id || null, subscription_id: form.subscription_id || null, status: form.status || "in_review", video_url: form.video_url, version: Number(form.version || 1), notes: form.notes });
      } else if (tab === "invoice") {
        await api.post("/admin/invoices", { client_id: selected, source_type: form.source_type, booking_id: form.source_type === "booking" ? form.booking_id : null, subscription_id: form.source_type === "subscription" ? form.subscription_id : null, invoice_number: form.invoice_number, amount: Number(form.amount || 0), status: form.inv_status || "sent", due_on: form.due_on || null });
      }
      toast.success("Created");
      setForm({});
      loadClientData(selected);
    } catch (err) {
      toast.error(typeof err.response?.data?.detail === "string" ? err.response.data.detail : "Create failed");
    }
  };

  const patchStatus = async (id, status) => {
    try {
      await api.patch(`/admin/deliverables/${id}`, { status });
      toast.success("Status updated");
      loadClientData(selected);
    } catch {
      toast.error("Update failed");
    }
  };

  const eraseClient = async () => {
    const c = clients.find((x) => x.id === selected);
    if (!window.confirm(`GDPR-erase ${c?.full_name || c?.email}? Personal data (name, email, contact) is anonymized and their login disabled. Bookings, deliverables and invoices are preserved as financial records. This cannot be undone.`)) return;
    try {
      const { data } = await api.post(`/admin/clients/${selected}/erase`);
      toast.success(`Erased. Preserved: ${data.preserved.bookings} bookings, ${data.preserved.deliverables} deliverables, ${data.preserved.invoices} invoices`);
      const res = await api.get("/admin/clients");
      setClients(res.data);
      loadAudit();
    } catch (err) {
      toast.error(typeof err.response?.data?.detail === "string" ? err.response.data.detail : "Erase failed");
    }
  };

  return (
    <div data-testid="admin-page">
      <PageHeader kicker="Studio internal" title="Admin console" />

      <Card className="mb-8 p-6">
        <Label>Managing client</Label>
        <div className="flex items-center gap-4">
          <select data-testid="admin-client-select" className={selectCls} value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="">Select a client…</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.full_name || c.email} {c.role === "admin" ? "(admin)" : ""}</option>
            ))}
          </select>
          {selected && (() => { const c = clients.find((x) => x.id === selected); return c?.role !== "admin" && !c?.email?.endsWith("@anonymized.invalid"); })() && (
            <Btn data-testid="admin-erase-client-btn" variant="danger" onClick={eraseClient} className="shrink-0">
              GDPR erase
            </Btn>
          )}
        </div>
        {selected && clients.find((x) => x.id === selected)?.email?.endsWith("@anonymized.invalid") && (
          <p className="mt-3 font-mono text-xs text-warn" data-testid="erased-client-note">
            This client has been GDPR-erased: personal data anonymized, login disabled, financial records retained.
          </p>
        )}
      </Card>

      {selected && (
        <>
          <Card className="mb-8">
            <div className="flex border-b border-line">
              {["deliverable", "booking", "subscription", "invoice"].map((t) => (
                <button
                  key={t}
                  data-testid={`admin-tab-${t}`}
                  onClick={() => { setTab(t); setForm({}); }}
                  className={`px-6 py-3 text-sm font-bold capitalize ${tab === t ? "border-b-2 border-accent text-accent" : "text-zinc-500 hover:text-white"}`}
                  style={{ transition: "color 0.15s ease" }}
                >
                  New {t}
                </button>
              ))}
            </div>
            <form onSubmit={submit} className="grid grid-cols-1 gap-5 p-6 md:grid-cols-2">
              {tab === "booking" && (
                <>
                  <div className="md:col-span-2"><Label>Title</Label><Input data-testid="admin-booking-title" value={form.title || ""} onChange={set("title")} required /></div>
                  <div><Label>Shoot type</Label><Input value={form.shoot_type || ""} onChange={set("shoot_type")} /></div>
                  <div><Label>Date</Label><Input type="date" value={form.shoot_date || ""} onChange={set("shoot_date")} /></div>
                  <div><Label>Location</Label><Input value={form.location || ""} onChange={set("location")} /></div>
                  <div><Label>Budget</Label><Input type="number" value={form.budget || ""} onChange={set("budget")} /></div>
                </>
              )}
              {tab === "subscription" && (
                <>
                  <div className="md:col-span-2"><Label>Package name</Label><Input data-testid="admin-sub-name" value={form.package_name || ""} onChange={set("package_name")} required /></div>
                  <div><Label>Monthly price</Label><Input type="number" value={form.monthly_price || ""} onChange={set("monthly_price")} required /></div>
                  <div><Label>Videos / month</Label><Input type="number" value={form.videos_per_month || ""} onChange={set("videos_per_month")} /></div>
                  <div><Label>Renews on</Label><Input type="date" value={form.renews_on || ""} onChange={set("renews_on")} /></div>
                </>
              )}
              {tab === "deliverable" && (
                <>
                  <div className="md:col-span-2"><Label>Title</Label><Input data-testid="admin-deliv-title" value={form.title || ""} onChange={set("title")} required /></div>
                  <div>
                    <Label>Link to booking</Label>
                    <select data-testid="admin-deliv-booking" className={selectCls} value={form.booking_id || ""} onChange={set("booking_id")}>
                      <option value="">—</option>
                      {bookings.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
                    </select>
                  </div>
                  <div>
                    <Label>Or link to retainer</Label>
                    <select data-testid="admin-deliv-sub" className={selectCls} value={form.subscription_id || ""} onChange={set("subscription_id")}>
                      <option value="">—</option>
                      {subs.map((s) => <option key={s.id} value={s.id}>{s.package_name}</option>)}
                    </select>
                  </div>
                  <div><Label>Video URL (embed)</Label><Input value={form.video_url || ""} onChange={set("video_url")} placeholder="https://player.vimeo.com/…" /></div>
                  <div><Label>Version</Label><Input type="number" value={form.version || ""} onChange={set("version")} placeholder="1" /></div>
                  <div className="md:col-span-2"><Label>Notes</Label><Input value={form.notes || ""} onChange={set("notes")} /></div>
                </>
              )}
              {tab === "invoice" && (
                <>
                  <div><Label>Invoice number</Label><Input data-testid="admin-invoice-number" value={form.invoice_number || ""} onChange={set("invoice_number")} placeholder="INV-1042" required /></div>
                  <div><Label>Amount</Label><Input type="number" value={form.amount || ""} onChange={set("amount")} required /></div>
                  <div>
                    <Label>Source type</Label>
                    <select data-testid="admin-invoice-source" className={selectCls} value={form.source_type || ""} onChange={set("source_type")} required>
                      <option value="">Choose…</option>
                      <option value="booking">Booking (one-off)</option>
                      <option value="subscription">Retainer (recurring)</option>
                    </select>
                  </div>
                  {form.source_type === "booking" && (
                    <div>
                      <Label>Booking</Label>
                      <select className={selectCls} value={form.booking_id || ""} onChange={set("booking_id")} required>
                        <option value="">Choose…</option>
                        {bookings.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
                      </select>
                    </div>
                  )}
                  {form.source_type === "subscription" && (
                    <div>
                      <Label>Subscription</Label>
                      <select className={selectCls} value={form.subscription_id || ""} onChange={set("subscription_id")} required>
                        <option value="">Choose…</option>
                        {subs.map((s) => <option key={s.id} value={s.id}>{s.package_name}</option>)}
                      </select>
                    </div>
                  )}
                  <div><Label>Due on</Label><Input type="date" value={form.due_on || ""} onChange={set("due_on")} /></div>
                </>
              )}
              <div className="md:col-span-2">
                <Btn data-testid="admin-create-btn" type="submit">Create {tab}</Btn>
              </div>
            </form>
          </Card>

          <h2 className="mb-4 font-display text-2xl font-semibold tracking-tight">Client deliverables</h2>
          <Card>
            {delivs.length === 0 && <p className="p-6 text-sm text-zinc-500">No deliverables for this client.</p>}
            {delivs.map((d, i) => (
              <div key={d.id} className={`flex items-center justify-between gap-4 px-6 py-4 ${i > 0 ? "border-t border-line" : ""}`} data-testid={`admin-deliv-row-${i}`}>
                <div>
                  <p className="font-semibold">{d.title}</p>
                  <p className="font-mono text-xs text-zinc-500">v{d.version}</p>
                </div>
                <div className="flex items-center gap-4">
                  <StatusPill status={d.status} />
                  <select
                    data-testid={`admin-deliv-status-select-${i}`}
                    className="rounded-md border border-line bg-raise px-3 py-1.5 text-xs text-white outline-none"
                    value={d.status}
                    onChange={(e) => patchStatus(d.id, e.target.value)}
                  >
                    {DELIV_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                  </select>
                </div>
              </div>
            ))}
          </Card>
        </>
      )}

      <div className="mt-12">
        <h2 className="mb-4 font-display text-2xl font-semibold tracking-tight">Erasure audit log</h2>
        <Card data-testid="erasure-audit-log">
          {audit.length === 0 && <p className="p-6 text-sm text-zinc-500">No erasures recorded.</p>}
          {audit.map((a, i) => (
            <div key={a.id} className={`px-6 py-4 ${i > 0 ? "border-t border-line" : ""}`} data-testid={`audit-entry-${i}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-mono text-sm font-bold text-warn">{a.anonymized_email}</p>
                <p className="font-mono text-xs text-zinc-500">{fmtDate(a.created_at?.slice(0, 10))}</p>
              </div>
              <p className="mt-1 text-sm text-zinc-400">
                Erased by <span className="text-zinc-200">{a.performed_by_email}</span> · client id <span className="font-mono text-xs">{a.erased_client_id}</span>
              </p>
              <p className="mt-1 font-mono text-xs text-zinc-500">
                preserved: {a.bookings_preserved} bookings · {a.deliverables_preserved} deliverables · {a.invoices_preserved} invoices
              </p>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
