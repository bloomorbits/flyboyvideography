import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

/*
 * AdminPricing — draft/publish editor for the pricing catalog stored in
 * pricing_catalog (Migration 013). Same "back-of-house stays dark" theme
 * convention as AdminSecurity: self-contained dark island with literal
 * hex values, escapes the cream/ink parent shell.
 *
 * Editing model:
 *   - GET  /api/admin/pricing/draft  → { draft, published, dirty }
 *   - PUT  /api/admin/pricing/draft  → persist the working copy
 *   - POST /api/admin/pricing/publish → atomic swap; 409 if removing a
 *     tier still referenced by a live booking (see backend/pricing.py
 *     _find_orphaned_refs). Force override with ?force=1 after manual
 *     reconciliation.
 *   - POST /api/admin/pricing/revert → discard draft, reset to published.
 *
 * UI trade-off: this favours function over polish. Arrays (tiers,
 * features, extras items) are edited with plain inputs + add/remove
 * buttons. No fancy drag-reorder. Nathan is the sole admin; simplicity
 * beats flexibility here.
 */

const cardCls = "rounded-lg border border-[#27272a] bg-[#141416] p-5";
const inputCls =
  "w-full rounded-md border border-[#27272a] bg-[#0b0b0d] px-3 py-2 text-sm text-zinc-100 " +
  "placeholder:text-zinc-600 focus:border-[#00E5FF] focus:outline-none";
const labelCls = "mb-1 block font-mono text-[10px] uppercase tracking-widest text-zinc-500";
const btnCls = "rounded-full border px-4 py-2 text-xs font-mono uppercase tracking-widest transition-colors";
const btnPrimary = `${btnCls} border-transparent bg-[#00E5FF] text-black hover:bg-[#00E5FF]/90`;
const btnDanger = `${btnCls} border-red-400/40 bg-red-400/10 text-red-400 hover:bg-red-400/20`;
const btnMuted = `${btnCls} border-[#27272a] bg-transparent text-zinc-300 hover:bg-[#27272a]`;

function TextInput({ label, value, onChange, type = "text", testId, step, min }) {
  return (
    <label className="block">
      {label && <span className={labelCls}>{label}</span>}
      <input
        data-testid={testId}
        type={type}
        step={step}
        min={min}
        value={value ?? ""}
        onChange={(e) => onChange(type === "number" ? Number(e.target.value) : e.target.value)}
        className={inputCls}
      />
    </label>
  );
}

function FeaturesEditor({ features, onChange, testId }) {
  // One feature per line — simple textarea. Parse on save (splits on newline,
  // trims, drops empties).
  const text = (features || []).join("\n");
  return (
    <label className="block">
      <span className={labelCls}>Features (one per line)</span>
      <textarea
        data-testid={testId}
        value={text}
        rows={Math.max(3, (features || []).length + 1)}
        onChange={(e) => {
          const lines = e.target.value.split("\n").map((l) => l.trimEnd());
          onChange(lines.length === 0 ? undefined : lines);
        }}
        className={`${inputCls} font-mono text-xs`}
      />
    </label>
  );
}

function TierEditor({ tier, hoursOnly, onChange, onRemove, testId }) {
  const set = (k) => (v) => onChange({ ...tier, [k]: v });
  const cleanEmpty = (v) => (v === "" || v === null || v === undefined ? undefined : v);
  return (
    <div className={`${cardCls} space-y-3`} data-testid={testId}>
      <div className="flex items-center justify-between">
        <p className="font-mono text-[11px] uppercase tracking-widest text-zinc-500">Tier</p>
        <button onClick={onRemove} className={btnDanger} data-testid={`${testId}-remove`}>Remove tier</button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <TextInput label="Name" value={tier.name} onChange={set("name")} testId={`${testId}-name`} />
        <TextInput label="Price (£)" value={tier.price} onChange={set("price")} type="number" step="0.01" min="0" testId={`${testId}-price`} />
      </div>
      <TextInput label="Coverage" value={tier.coverage} onChange={set("coverage")} testId={`${testId}-coverage`} />
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          data-testid={`${testId}-popular`}
          checked={!!tier.popular}
          onChange={(e) => set("popular")(e.target.checked || undefined)}
        />
        <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-400">Most popular badge</span>
      </label>
      {!hoursOnly && (
        <>
          <TextInput label="Lead-in (e.g. 'Everything in Basic, plus:')" value={tier.leadIn ?? ""} onChange={(v) => set("leadIn")(cleanEmpty(v))} testId={`${testId}-leadin`} />
          <FeaturesEditor features={tier.features} onChange={(f) => set("features")(f)} testId={`${testId}-features`} />
        </>
      )}
    </div>
  );
}

function PackageEditor({ pkg, onChange, onRemove }) {
  const set = (k) => (v) => onChange({ ...pkg, [k]: v });
  const updateTier = (i, next) => {
    const tiers = [...pkg.tiers];
    tiers[i] = next;
    set("tiers")(tiers);
  };
  const removeTier = (i) => set("tiers")(pkg.tiers.filter((_, x) => x !== i));
  const addTier = () => set("tiers")([...pkg.tiers, { name: "New tier", price: 0, coverage: "1 hour coverage" }]);

  return (
    <section className={`${cardCls} space-y-4`} data-testid={`pkg-${pkg.id}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg font-semibold text-zinc-100">{pkg.title || "(untitled package)"}</h3>
        <button onClick={onRemove} className={btnDanger} data-testid={`pkg-${pkg.id}-remove`}>Remove package</button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <TextInput label="ID (lowercase, kebab-case)" value={pkg.id} onChange={set("id")} testId={`pkg-${pkg.id}-id`} />
        <TextInput label="Title" value={pkg.title} onChange={set("title")} testId={`pkg-${pkg.id}-title`} />
      </div>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          data-testid={`pkg-${pkg.id}-hoursonly`}
          checked={!!pkg.hoursOnly}
          onChange={(e) => set("hoursOnly")(e.target.checked || undefined)}
        />
        <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-400">Hours-only (no feature bullets)</span>
      </label>
      <div className="space-y-3">
        {pkg.tiers.map((t, i) => (
          <TierEditor
            key={i}
            tier={t}
            hoursOnly={pkg.hoursOnly}
            onChange={(next) => updateTier(i, next)}
            onRemove={() => removeTier(i)}
            testId={`pkg-${pkg.id}-tier-${i}`}
          />
        ))}
        <button onClick={addTier} className={btnMuted} data-testid={`pkg-${pkg.id}-add-tier`}>+ Add tier</button>
      </div>
    </section>
  );
}

function ExtrasEditor({ extras, onChange }) {
  const set = (k) => (v) => onChange({ ...extras, [k]: v });
  const updateItem = (i, patch) => {
    const items = [...extras.items];
    items[i] = { ...items[i], ...patch };
    set("items")(items);
  };
  const removeItem = (i) => set("items")(extras.items.filter((_, x) => x !== i));
  const addItem = () => set("items")([...extras.items, { label: "New reel", price: 0 }]);
  return (
    <section className={`${cardCls} space-y-4`} data-testid="section-extras">
      <h3 className="font-display text-lg font-semibold text-zinc-100">Extras</h3>
      <div className="grid grid-cols-2 gap-3">
        <TextInput label="Title" value={extras.title} onChange={set("title")} testId="extras-title" />
        <TextInput label="Subtitle" value={extras.subtitle} onChange={set("subtitle")} testId="extras-subtitle" />
      </div>
      <div className="space-y-2">
        {extras.items.map((it, i) => (
          <div key={i} className="grid grid-cols-[1fr_120px_auto] gap-2 items-end" data-testid={`extras-item-${i}`}>
            <TextInput label="Label" value={it.label} onChange={(v) => updateItem(i, { label: v })} testId={`extras-item-${i}-label`} />
            <TextInput label="Price (£)" value={it.price} onChange={(v) => updateItem(i, { price: v })} type="number" step="0.01" min="0" testId={`extras-item-${i}-price`} />
            <button onClick={() => removeItem(i)} className={btnDanger} data-testid={`extras-item-${i}-remove`}>Remove</button>
          </div>
        ))}
        <button onClick={addItem} className={btnMuted} data-testid="extras-add">+ Add item</button>
      </div>
    </section>
  );
}

function GraduationEditor({ graduation, onChange }) {
  const set = (k) => (v) => onChange({ ...graduation, [k]: v });
  return (
    <section className={`${cardCls} space-y-4`} data-testid="section-graduation">
      <h3 className="font-display text-lg font-semibold text-zinc-100">Graduation Reels (single tier)</h3>
      <div className="grid grid-cols-2 gap-3">
        <TextInput label="ID" value={graduation.id} onChange={set("id")} testId="grad-id" />
        <TextInput label="Title" value={graduation.title} onChange={set("title")} testId="grad-title" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <TextInput label="Price (£)" value={graduation.price} onChange={set("price")} type="number" step="0.01" min="0" testId="grad-price" />
        <TextInput label="Coverage" value={graduation.coverage} onChange={set("coverage")} testId="grad-coverage" />
      </div>
      <FeaturesEditor features={graduation.features} onChange={(f) => set("features")(f)} testId="grad-features" />
    </section>
  );
}

// -------- Orphan-block modal (409 on publish) --------

function OrphanBlockModal({ report, onCancel, onForce }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6" data-testid="orphan-modal">
      <div className="max-w-2xl rounded-lg border border-red-400/40 bg-[#141416] p-6">
        <h3 className="font-display text-lg font-semibold text-red-400">Publish blocked — live bookings still reference this tier</h3>
        <p className="mt-2 text-sm text-zinc-300">{report.message}</p>
        <div className="mt-4 max-h-64 space-y-2 overflow-y-auto">
          {report.orphaned_refs.map((o, i) => (
            <div key={i} className="rounded border border-[#27272a] bg-[#0b0b0d] p-3 text-xs" data-testid={`orphan-${i}`}>
              <p className="font-mono text-zinc-100">
                <span className="text-[#FFB020]">{o.package_id}</span>
                {o.tier_name ? <> · <span className="text-[#00E5FF]">{o.tier_name}</span></> : ""}
              </p>
              <p className="mt-1 text-zinc-400">
                {o.confirmed_booking_count} confirmed booking(s), {o.in_flight_intent_count} in-flight intent(s)
              </p>
              {o.sample_booking_ids?.length ? (
                <p className="mt-1 font-mono text-[10px] text-zinc-500">
                  Sample bookings: {o.sample_booking_ids.join(", ")}
                </p>
              ) : null}
            </div>
          ))}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onCancel} className={btnMuted} data-testid="orphan-cancel">Cancel — I&apos;ll reconcile first</button>
          <button onClick={onForce} className={btnDanger} data-testid="orphan-force">Force publish anyway</button>
        </div>
      </div>
    </div>
  );
}

// -------- Main page --------

export default function AdminPricing() {
  const { profile } = useAuth();
  const [state, setState] = useState({ loading: true, draft: null, published: null, dirty: false });
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [orphanReport, setOrphanReport] = useState(null);

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }));
    try {
      const { data } = await api.get("/admin/pricing/draft");
      setState({ loading: false, draft: data.draft, published: data.published, dirty: data.dirty });
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || "Failed to load pricing");
      setState((s) => ({ ...s, loading: false }));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (profile && profile.role !== "admin") return <Navigate to="/" replace />;

  const draft = state.draft;
  const updateDraft = (patch) => setState((s) => ({ ...s, draft: { ...s.draft, ...patch }, dirty: true }));
  const updatePackage = (i, next) => {
    const pkgs = [...draft.packages];
    pkgs[i] = next;
    updateDraft({ packages: pkgs });
  };
  const removePackage = (i) => updateDraft({ packages: draft.packages.filter((_, x) => x !== i) });
  const addPackage = () => updateDraft({
    packages: [
      ...draft.packages,
      { id: `new-package-${Date.now()}`, title: "New package", tiers: [{ name: "Basic", price: 100, coverage: "1 hour coverage" }] },
    ],
  });

  const saveDraft = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/admin/pricing/draft", draft);
      toast.success("Draft saved");
      setState((s) => ({ ...s, dirty: data.dirty }));
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => `${d.loc?.slice(1).join(".") || "?"}: ${d.msg}`).join("\n")
        : (typeof detail === "string" ? detail : (err.message || "Save failed"));
      toast.error(`Save failed:\n${msg}`, { duration: 10000 });
    } finally { setSaving(false); }
  };

  const publish = async (force = false) => {
    setPublishing(true);
    try {
      const url = force ? "/admin/pricing/publish?force=1" : "/admin/pricing/publish";
      const { data } = await api.post(url);
      toast.success(data.forced ? "Published (force-override) — live now" : "Published — live within 60s");
      setOrphanReport(null);
      await load();
    } catch (err) {
      if (err.response?.status === 409) {
        setOrphanReport(err.response.data.detail);
      } else {
        toast.error(err.response?.data?.detail || err.message || "Publish failed");
      }
    } finally { setPublishing(false); }
  };

  const revert = async () => {
    if (!window.confirm("Discard all unsaved draft changes and reset to the currently published catalog?")) return;
    try {
      await api.post("/admin/pricing/revert");
      toast.success("Draft reverted to published");
      await load();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || "Revert failed");
    }
  };

  if (state.loading || !draft) {
    return (
      <div className="-m-6 min-h-[calc(100vh-2rem)] bg-[#0b0b0d] p-6 text-zinc-100">
        <p className="font-mono text-xs uppercase tracking-widest text-zinc-500">Loading pricing catalog…</p>
      </div>
    );
  }

  return (
    <div className="-m-6 min-h-[calc(100vh-2rem)] bg-[#0b0b0d] p-6 text-zinc-100" data-testid="admin-pricing-page">
      {/* Sticky action bar */}
      <div className="sticky top-0 z-40 -mx-6 mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-[#27272a] bg-[#0b0b0d]/95 px-6 py-4 backdrop-blur">
        <div>
          <h1 className="font-display text-2xl font-semibold">Pricing catalog</h1>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
            {state.dirty ? <span className="text-[#FFB020]">Draft has unpublished changes</span> : <span className="text-zinc-500">No changes to publish</span>}
          </p>
        </div>
        <div className="flex gap-2" data-testid="pricing-action-bar">
          <button onClick={revert} disabled={!state.dirty} className={btnMuted} data-testid="pricing-revert">Revert draft</button>
          <button onClick={saveDraft} disabled={saving || !state.dirty} className={btnMuted} data-testid="pricing-save">{saving ? "Saving…" : "Save draft"}</button>
          <button onClick={() => publish(false)} disabled={publishing || !state.dirty} className={btnPrimary} data-testid="pricing-publish">{publishing ? "Publishing…" : "Publish live"}</button>
        </div>
      </div>

      <div className="mx-auto max-w-4xl space-y-6">
        <p className="text-sm text-zinc-400">
          Edit prices, coverage, features and lead-in copy for every package. Changes stay in <span className="text-zinc-100">draft</span> until
          you press <span className="text-[#00E5FF]">Publish live</span>. The public site refreshes within 60 seconds of publish.
        </p>

        {/* Packages */}
        {draft.packages.map((p, i) => (
          <PackageEditor
            key={p.id + i}
            pkg={p}
            onChange={(next) => updatePackage(i, next)}
            onRemove={() => removePackage(i)}
          />
        ))}
        <button onClick={addPackage} className={btnMuted} data-testid="pricing-add-package">+ Add package</button>

        {/* Graduation */}
        <GraduationEditor graduation={draft.graduation} onChange={(g) => updateDraft({ graduation: g })} />

        {/* Extras */}
        <ExtrasEditor extras={draft.extras} onChange={(e) => updateDraft({ extras: e })} />

        {/* Booking terms */}
        <section className={`${cardCls} space-y-3`} data-testid="section-booking-terms">
          <h3 className="font-display text-lg font-semibold">Booking terms footer</h3>
          <TextInput label="Booking terms text" value={draft.bookingTerms} onChange={(v) => updateDraft({ bookingTerms: v })} testId="booking-terms" />
        </section>
      </div>

      {orphanReport && (
        <OrphanBlockModal
          report={orphanReport}
          onCancel={() => setOrphanReport(null)}
          onForce={() => publish(true)}
        />
      )}
    </div>
  );
}
