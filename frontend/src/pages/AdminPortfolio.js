import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

/*
 * AdminPortfolio — direct-edit manager for the YouTube portfolio
 * (portfolio_videos, Migration 016). No draft/publish: each row is edited in
 * place and the public /portfolio picks it up within 60s (ISR). Same dark
 * "back-of-house" island theme as AdminPricing/AdminSecurity.
 *
 *   GET    /api/admin/portfolio        → { videos, categories }
 *   POST   /api/admin/portfolio        → { category, youtube, title?, display_order?, is_active? }
 *   PATCH  /api/admin/portfolio/{id}   → partial update
 *   DELETE /api/admin/portfolio/{id}
 *
 * Validation is server-side: the backend normalizes a pasted URL → 11-char id
 * and rejects bad input (422); oEmbed fills the real title + thumbnail.
 */

const cardCls = "rounded-lg border border-[#27272a] bg-[#141416] p-5";
const inputCls =
  "w-full rounded-md border border-[#27272a] bg-[#0b0b0d] px-3 py-2 text-sm text-zinc-100 " +
  "placeholder:text-zinc-600 focus:border-[#00E5FF] focus:outline-none";
const labelCls = "mb-1 block font-mono text-[10px] uppercase tracking-widest text-zinc-500";
const btnCls = "rounded-full border px-4 py-2 text-xs font-mono uppercase tracking-widest transition-colors disabled:opacity-40";
const btnPrimary = `${btnCls} border-transparent bg-[#00E5FF] text-black hover:bg-[#00E5FF]/90`;
const btnDanger = `${btnCls} border-red-400/40 bg-red-400/10 text-red-400 hover:bg-red-400/20`;
const btnMuted = `${btnCls} border-[#27272a] bg-transparent text-zinc-300 hover:bg-[#27272a]`;

function errMsg(err, fallback) {
  const d = err.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

export default function AdminPortfolio() {
  const { profile } = useAuth();
  const isAdmin = profile?.role === "admin";

  const [videos, setVideos] = useState([]);
  const [categories, setCategories] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ category: "weddings", youtube: "", title: "", display_order: 0, is_active: true });

  const reload = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/portfolio");
      setVideos(data.videos || []);
      setCategories(data.categories || {});
    } catch (err) {
      toast.error(errMsg(err, "Failed to load portfolio (is Migration 016 applied?)"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (isAdmin) reload(); }, [isAdmin, reload]);

  if (profile && !isAdmin) return <Navigate to="/" replace />;
  if (!profile) return null;

  const catIds = Object.keys(categories).length ? Object.keys(categories) : ["weddings", "birthdays", "naming", "lifestyle", "corporate"];

  const addVideo = async (e) => {
    e.preventDefault();
    if (!form.youtube.trim()) { toast.error("Paste a YouTube URL or video ID"); return; }
    setBusy(true);
    try {
      await api.post("/admin/portfolio", {
        category: form.category,
        youtube: form.youtube.trim(),
        title: form.title.trim() || undefined,
        display_order: Number(form.display_order) || 0,
        is_active: form.is_active,
      });
      toast.success("Video added — live within 60s");
      setForm({ ...form, youtube: "", title: "", display_order: 0 });
      reload();
    } catch (err) {
      toast.error(errMsg(err, "Could not add video"));
    } finally {
      setBusy(false);
    }
  };

  const patchVideo = async (id, patch, successMsg) => {
    try {
      await api.patch(`/admin/portfolio/${id}`, patch);
      if (successMsg) toast.success(successMsg);
      reload();
    } catch (err) {
      toast.error(errMsg(err, "Update failed"));
    }
  };

  const deleteVideo = async (id, title) => {
    if (!window.confirm(`Delete "${title}"? This can't be undone.`)) return;
    try {
      await api.delete(`/admin/portfolio/${id}`);
      toast.success("Video removed");
      reload();
    } catch (err) {
      toast.error(errMsg(err, "Delete failed"));
    }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="-m-6 min-h-[calc(100vh-2rem)] bg-[#0b0b0d] p-6 text-zinc-100" data-testid="admin-portfolio-page">
      <div className="sticky top-0 z-40 -mx-6 mb-6 border-b border-[#27272a] bg-[#0b0b0d]/95 px-6 py-4 backdrop-blur">
        <h1 className="font-display text-2xl font-semibold">Portfolio</h1>
        <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
          Paste a YouTube link, save, it's live — no code, no redeploy. Public site refreshes within 60s.
        </p>
      </div>

      <div className="mx-auto max-w-4xl space-y-6">
        {/* Add form */}
        <form onSubmit={addVideo} className={cardCls} data-testid="portfolio-add-form">
          <h2 className="mb-4 font-display text-lg">Add a video</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="block">
              <span className={labelCls}>Category</span>
              <select data-testid="portfolio-add-category" value={form.category} onChange={set("category")} className={inputCls}>
                {catIds.map((id) => <option key={id} value={id}>{categories[id] || id}</option>)}
              </select>
            </label>
            <label className="block">
              <span className={labelCls}>Display order (lower = first)</span>
              <input data-testid="portfolio-add-order" type="number" value={form.display_order} onChange={set("display_order")} className={inputCls} />
            </label>
            <label className="block md:col-span-2">
              <span className={labelCls}>YouTube URL or 11-char video ID</span>
              <input data-testid="portfolio-add-youtube" value={form.youtube} onChange={set("youtube")} placeholder="https://youtu.be/… or dQw4w9WgXcQ" className={inputCls} />
            </label>
            <label className="block md:col-span-2">
              <span className={labelCls}>Title override (optional — leave blank to use the real YouTube title)</span>
              <input data-testid="portfolio-add-title" value={form.title} onChange={set("title")} placeholder="Auto-filled from YouTube" className={inputCls} />
            </label>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-zinc-300">
              <input data-testid="portfolio-add-active" type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              Active (visible on the public site)
            </label>
            <button type="submit" disabled={busy} className={btnPrimary} data-testid="portfolio-add-submit">{busy ? "Adding…" : "Add video"}</button>
          </div>
        </form>

        {loading ? (
          <p className="font-mono text-xs uppercase tracking-widest text-zinc-500">Loading…</p>
        ) : (
          catIds.map((cid) => {
            const rows = videos.filter((v) => v.category === cid).sort((a, b) => a.display_order - b.display_order);
            const activeCount = rows.filter((r) => r.is_active).length;
            return (
              <div key={cid} className={cardCls} data-testid={`portfolio-cat-${cid}`}>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-display text-lg">{categories[cid] || cid}</h2>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">
                    {rows.length} video{rows.length !== 1 ? "s" : ""} · {activeCount} active
                  </span>
                </div>
                {rows.length === 0 ? (
                  <p className="rounded border border-dashed border-[#27272a] px-3 py-4 text-xs text-zinc-500" data-testid={`portfolio-empty-${cid}`}>
                    No videos — the public site shows the honest “Placeholder” tile for this category.
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {rows.map((v) => (
                      <li key={v.id} className="flex flex-col gap-3 rounded border border-[#27272a] bg-[#0b0b0d] p-3 md:flex-row md:items-center" data-testid={`portfolio-row-${v.id}`}>
                        {v.thumbnail_url
                          ? <img src={v.thumbnail_url} alt="" className="h-14 w-24 shrink-0 rounded object-cover" />
                          : <div className="h-14 w-24 shrink-0 rounded bg-[#27272a]" />}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm text-zinc-100" data-testid={`portfolio-title-${v.id}`}>{v.title}</p>
                          <p className="font-mono text-[10px] text-zinc-500">{v.youtube_video_id}</p>
                        </div>
                        <label className="flex items-center gap-1 text-[10px] font-mono uppercase text-zinc-500">
                          Order
                          <input
                            type="number"
                            defaultValue={v.display_order}
                            data-testid={`portfolio-order-${v.id}`}
                            onBlur={(e) => { const n = Number(e.target.value); if (n !== v.display_order) patchVideo(v.id, { display_order: n }, "Order updated"); }}
                            className={`${inputCls} w-16 px-2 py-1`}
                          />
                        </label>
                        <button
                          onClick={() => patchVideo(v.id, { is_active: !v.is_active }, v.is_active ? "Hidden" : "Now live")}
                          className={v.is_active ? btnPrimary : btnMuted}
                          data-testid={`portfolio-toggle-${v.id}`}
                        >
                          {v.is_active ? "Active" : "Hidden"}
                        </button>
                        <button onClick={() => deleteVideo(v.id, v.title)} className={btnDanger} data-testid={`portfolio-delete-${v.id}`}>Delete</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
