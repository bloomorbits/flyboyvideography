import { useCallback, useEffect, useRef, useState } from "react";
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

  // Homepage hero videos (site_settings, Migration 019) — weighted, reorderable
  // queue + an uploaded poster, DB-backed, live in 60s. Rotation runs client-side.
  const [heroRows, setHeroRows] = useState([{ url: "", weight: 1, id: "" }]);
  const [heroPoster, setHeroPoster] = useState("");
  const [heroBusy, setHeroBusy] = useState(false);
  const [posterBusy, setPosterBusy] = useState(false);
  const posterFileRef = useRef(null);
  const dragIndexRef = useRef(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  const loadHero = useCallback(async () => {
    try {
      const { data } = await api.get("/site-settings/hero-video");
      const vids = data.videos || [];
      setHeroRows(vids.length
        ? vids.map((v) => ({ url: `https://youtu.be/${v.id}`, weight: v.weight || 1, id: v.id }))
        : [{ url: "", weight: 1, id: "" }]);
      setHeroPoster(data.poster_url || "");
    } catch {
      /* non-fatal — the public site falls back to the default video */
    }
  }, []);

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
  useEffect(() => { if (isAdmin) loadHero(); }, [isAdmin, loadHero]);

  const setHeroRowField = (i, field, val) =>
    setHeroRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, [field]: val } : r)));
  const addHeroRow = () => setHeroRows((p) => [...p, { url: "", weight: 1, id: "" }]);
  const removeHeroRow = (i) => setHeroRows((prev) => (prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev));

  // Drag-to-reorder the hero queue (native HTML5 DnD; order persists on Save).
  const moveHeroRow = (from, to) => {
    if (from == null || to == null || from === to) return;
    setHeroRows((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  };

  const persistHero = async (posterUrl) => {
    const videos = heroRows
      .map((r) => ({ youtube: r.url.trim(), weight: Math.max(1, Math.min(10, Number(r.weight) || 1)) }))
      .filter((v) => v.youtube);
    if (!videos.length) { toast.error("Add at least one YouTube URL or video ID"); return null; }
    const { data } = await api.put("/admin/site-settings/hero-video", { videos, poster_url: posterUrl ?? null });
    const vids = data.videos || [];
    setHeroRows(vids.length
      ? vids.map((v) => ({ url: `https://youtu.be/${v.id}`, weight: v.weight || 1, id: v.id }))
      : [{ url: "", weight: 1, id: "" }]);
    return data;
  };

  const saveHero = async (e) => {
    e.preventDefault();
    setHeroBusy(true);
    try {
      const data = await persistHero(heroPoster.trim() || null);
      if (data) toast.success(`Hero updated — ${(data.videos || []).length} video(s), live within 60s`);
    } catch (err) {
      toast.error(errMsg(err, "Could not update hero videos"));
    } finally {
      setHeroBusy(false);
    }
  };

  const uploadPoster = async (fileList) => {
    const file = fileList && fileList[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { toast.error("Poster must be an image file"); return; }
    setPosterBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/admin/site-settings/hero-poster", fd);
      setHeroPoster(data.poster_url);
      toast.success("Poster uploaded — live within 60s");
    } catch (err) {
      toast.error(errMsg(err, "Poster upload failed"));
    } finally {
      setPosterBusy(false);
      if (posterFileRef.current) posterFileRef.current.value = "";
    }
  };

  const removePoster = async () => {
    setPosterBusy(true);
    try {
      await persistHero(null);
      setHeroPoster("");
      toast.success("Poster removed");
    } catch (err) {
      toast.error(errMsg(err, "Could not remove poster"));
    } finally {
      setPosterBusy(false);
    }
  };

  if (profile && !isAdmin) return <Navigate to="/" replace />;
  if (!profile) return null;

  const catIds = Object.keys(categories).length ? Object.keys(categories) : ["weddings", "birthdays", "naming", "lifestyle", "corporate"];
  const featuredCount = videos.filter((v) => v.is_featured && v.is_active).length;

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
        {/* Homepage hero videos — queue + poster */}
        <form onSubmit={saveHero} className={cardCls} data-testid="hero-video-form">
          <h2 className="mb-1 font-display text-lg">Homepage hero videos</h2>
          <p className="mb-4 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
            The autoplaying video behind the homepage headline. Add several — the homepage rotates to a different one each visit. Live within 60s.
          </p>

          <div className="space-y-3" data-testid="hero-video-queue">
            {heroRows.map((row, i) => (
              <div
                key={i}
                onDragOver={(e) => { e.preventDefault(); if (dragOverIndex !== i) setDragOverIndex(i); }}
                onDrop={(e) => { e.preventDefault(); moveHeroRow(dragIndexRef.current, i); dragIndexRef.current = null; setDragOverIndex(null); }}
                data-testid={`hero-video-row-${i}`}
                className={`flex items-center gap-3 rounded-md transition-colors ${dragOverIndex === i ? "bg-[#00E5FF]/10 ring-1 ring-[#00E5FF]/40" : ""}`}
              >
                <span
                  draggable
                  onDragStart={() => { dragIndexRef.current = i; }}
                  onDragEnd={() => { dragIndexRef.current = null; setDragOverIndex(null); }}
                  aria-label="Drag to reorder"
                  title="Drag to reorder"
                  data-testid={`hero-video-drag-${i}`}
                  className="flex h-9 w-6 shrink-0 cursor-grab items-center justify-center text-zinc-500 hover:text-zinc-200 active:cursor-grabbing"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <circle cx="9" cy="6" r="1.6" /><circle cx="15" cy="6" r="1.6" />
                    <circle cx="9" cy="12" r="1.6" /><circle cx="15" cy="12" r="1.6" />
                    <circle cx="9" cy="18" r="1.6" /><circle cx="15" cy="18" r="1.6" />
                  </svg>
                </span>
                {row.id && (
                  <img
                    src={`https://i.ytimg.com/vi/${row.id}/hqdefault.jpg`}
                    alt=""
                    className="hidden h-12 w-20 shrink-0 rounded object-cover sm:block"
                    data-testid={`hero-video-thumb-${i}`}
                  />
                )}
                <input
                  data-testid={`hero-video-input-${i}`}
                  value={row.url}
                  onChange={(e) => setHeroRowField(i, "url", e.target.value)}
                  placeholder="https://youtu.be/… or dQw4w9WgXcQ"
                  className={inputCls}
                />
                <div className="flex shrink-0 flex-col">
                  <span className="mb-1 font-mono text-[9px] uppercase tracking-widest text-zinc-500">Weight</span>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    data-testid={`hero-video-weight-${i}`}
                    value={row.weight ?? 1}
                    onChange={(e) => setHeroRowField(i, "weight", e.target.value)}
                    title="Higher = appears more often in the rotation"
                    className={`${inputCls} w-16`}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => removeHeroRow(i)}
                  disabled={heroRows.length <= 1}
                  aria-label="Remove video"
                  data-testid={`hero-video-remove-${i}`}
                  className={`${btnMuted} shrink-0 self-end`}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <button type="button" onClick={addHeroRow} className={`${btnMuted} mt-3`} data-testid="hero-video-add-url">
            + Add another video
          </button>

          <div className="mt-5">
            <span className={labelCls}>Poster image — shown instantly while the video loads (optional)</span>
            <div
              data-testid="hero-poster-dropzone"
              onClick={() => posterFileRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); uploadPoster(e.dataTransfer.files); }}
              className="mt-1 flex cursor-pointer items-center gap-4 rounded-md border border-dashed border-[#3f3f46] bg-[#0b0b0d] p-4 transition-colors hover:border-[#00E5FF]"
            >
              {heroPoster ? (
                <img
                  src={heroPoster}
                  alt="Poster"
                  className="h-20 w-36 shrink-0 rounded object-cover"
                  data-testid="hero-poster-preview"
                  onError={(e) => { e.currentTarget.style.visibility = "hidden"; }}
                />
              ) : (
                <div className="flex h-20 w-36 shrink-0 items-center justify-center rounded bg-[#141416] text-zinc-600">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="9" cy="9" r="2" /><path d="m21 15-5-5L5 21" />
                  </svg>
                </div>
              )}
              <div className="min-w-0 text-sm text-zinc-400">
                {posterBusy ? "Uploading…" : (
                  <>
                    <span className="text-zinc-200">Drop an image here</span> or click to choose.
                    <br />
                    <span className="text-[11px] text-zinc-500">JPEG, PNG, WebP, GIF or AVIF · max 5MB · blank uses the video thumbnail</span>
                  </>
                )}
              </div>
              <input
                ref={posterFileRef}
                type="file"
                accept="image/*"
                className="hidden"
                data-testid="hero-poster-file"
                onChange={(e) => uploadPoster(e.target.files)}
              />
            </div>
            {heroPoster && (
              <button type="button" onClick={removePoster} disabled={posterBusy} className={`${btnMuted} mt-2`} data-testid="hero-poster-remove">
                Remove poster
              </button>
            )}
          </div>

          <div className="mt-5">
            <button type="submit" disabled={heroBusy} className={btnPrimary} data-testid="hero-video-save">
              {heroBusy ? "Saving…" : "Save hero videos"}
            </button>
          </div>
        </form>

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
          <>
            <div className={`${cardCls} flex items-center justify-between`} data-testid="featured-summary">
              <div>
                <h2 className="font-display text-lg">Homepage “Recent Work”</h2>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
                  Shows the 4 featured projects below, lowest featured-order first. Star a project and set its order.
                </p>
              </div>
              <span
                data-testid="featured-count"
                className={`shrink-0 rounded-full px-3 py-1 font-mono text-[10px] uppercase tracking-widest ${featuredCount === 4 ? "bg-[#00E5FF]/15 text-[#00E5FF]" : "bg-amber-400/10 text-amber-400"}`}
              >
                {featuredCount} featured{featuredCount === 4 ? "" : " · homepage wants 4"}
              </span>
            </div>
            {catIds.map((cid) => {
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
                        <label className="flex items-center gap-1 text-[10px] font-mono uppercase text-zinc-500">
                          Feat. order
                          <input
                            type="number"
                            defaultValue={v.featured_order ?? 0}
                            data-testid={`portfolio-featured-order-${v.id}`}
                            disabled={!v.is_featured}
                            onBlur={(e) => { const n = Number(e.target.value); if (n !== (v.featured_order ?? 0)) patchVideo(v.id, { featured_order: n }, "Featured order updated"); }}
                            className={`${inputCls} w-16 px-2 py-1 disabled:opacity-40`}
                          />
                        </label>
                        <button
                          onClick={() => patchVideo(v.id, { is_featured: !v.is_featured }, v.is_featured ? "Unfeatured" : "Featured on homepage")}
                          className={v.is_featured ? btnPrimary : btnMuted}
                          data-testid={`portfolio-feature-${v.id}`}
                          title="Show in the homepage Recent Work section"
                        >
                          {v.is_featured ? "★ Featured" : "☆ Feature"}
                        </button>
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
            })}
          </>
        )}
      </div>
    </div>
  );
}
