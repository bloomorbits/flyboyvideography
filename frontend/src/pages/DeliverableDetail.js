import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, Circle, Download } from "lucide-react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { Btn, Card, Input, Label, SourceBadge, StatusPill, fmtDate, parseTimecode, secondsToTimecode } from "../components/ui";

export default function DeliverableDetail() {
  const { id } = useParams();
  const { profile } = useAuth();
  const [deliv, setDeliv] = useState(null);
  const [comments, setComments] = useState([]);
  const [form, setForm] = useState({ timecode: "", comment: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [{ data: d }, { data: c }] = await Promise.all([
      supabase.from("deliverables").select("*").eq("id", id).single(),
      supabase.from("review_threads").select("*").eq("deliverable_id", id).order("timestamp_seconds", { ascending: true, nullsFirst: false }),
    ]);
    setDeliv(d);
    setComments(c || []);
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const addComment = async (e) => {
    e.preventDefault();
    setBusy(true);
    const seconds = parseTimecode(form.timecode);
    const { error } = await supabase.from("review_threads").insert({
      deliverable_id: id,
      client_id: deliv.client_id,
      author_user_id: profile.user_id,
      author_name: profile.full_name || profile.email,
      author_role: profile.role,
      version: deliv.version,
      timestamp_seconds: seconds,
      comment: form.comment,
    });
    setBusy(false);
    if (error) return toast.error(error.message);
    toast.success("Note added to the review thread");
    setForm({ timecode: "", comment: "" });
    load();
  };

  const toggleResolved = async (c) => {
    const { error } = await supabase.from("review_threads").update({ resolved: !c.resolved }).eq("id", c.id);
    if (error) return toast.error(error.message);
    load();
  };

  if (!deliv) return <p className="font-mono text-xs uppercase tracking-[0.3em] text-zinc-500">Loading…</p>;

  return (
    <div data-testid="deliverable-detail-page">
      <Link to="/deliverables" data-testid="back-to-deliverables" className="mb-6 inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-accent" style={{ transition: "color 0.15s ease" }}>
        <ArrowLeft size={15} /> All deliverables
      </Link>

      <div className="rise mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <SourceBadge type={deliv.booking_id ? "booking" : "subscription"} />
            <span className="font-mono text-xs text-zinc-500">VERSION {deliv.version}</span>
          </div>
          <h1 className="font-display text-4xl font-bold tracking-tighter">{deliv.title}</h1>
        </div>
        <StatusPill status={deliv.status} testId="deliverable-status" />
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <Card className="overflow-hidden">
            {deliv.video_url ? (
              <div className="aspect-video">
                <iframe title={deliv.title} src={deliv.video_url} className="h-full w-full" allowFullScreen frameBorder="0" />
              </div>
            ) : (
              <div className="flex aspect-video items-center justify-center bg-raise">
                <p className="font-mono text-xs uppercase tracking-[0.3em] text-zinc-600">No preview uploaded</p>
              </div>
            )}
            <div className="flex items-center justify-between border-t border-line px-6 py-4">
              <p className="text-sm text-zinc-400">{deliv.notes || "No editor notes for this cut."}</p>
              {deliv.final_file_url && (
                <a
                  href={deliv.final_file_url}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="final-file-link"
                  className="flex shrink-0 items-center gap-2 rounded-md bg-ok/10 px-4 py-2 text-sm font-bold text-ok hover:bg-ok/20"
                  style={{ transition: "background-color 0.15s ease" }}
                >
                  <Download size={15} /> Final files
                </a>
              )}
            </div>
          </Card>
        </div>

        <div>
          <h2 className="mb-4 font-display text-xl font-semibold tracking-tight">Review thread</h2>
          <Card className="p-5">
            <form onSubmit={addComment} className="space-y-4 border-b border-line pb-5">
              <div className="flex gap-3">
                <div className="w-28 shrink-0">
                  <Label>Timecode</Label>
                  <Input data-testid="comment-timecode-input" value={form.timecode} onChange={(e) => setForm({ ...form, timecode: e.target.value })} placeholder="01:24" className="font-mono" />
                </div>
                <div className="flex-1">
                  <Label>Note</Label>
                  <Input data-testid="comment-text-input" value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} placeholder="Push the logo back a beat…" required />
                </div>
              </div>
              <Btn data-testid="comment-submit-btn" type="submit" disabled={busy} className="w-full">
                {busy ? "Posting…" : "Add note"}
              </Btn>
            </form>

            <div className="mt-5 space-y-4" data-testid="review-thread-list">
              {comments.length === 0 && <p className="text-sm text-zinc-500">No notes yet on this version.</p>}
              {comments.map((c, i) => (
                <div key={c.id} className={`rise rounded-md border border-line p-4 ${c.resolved ? "opacity-50" : ""}`} data-testid={`review-comment-${i}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {c.timestamp_seconds !== null && (
                        <span className="rounded bg-accent/10 px-2 py-0.5 font-mono text-xs font-bold text-accent">
                          {secondsToTimecode(Number(c.timestamp_seconds))}
                        </span>
                      )}
                      <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">v{c.version}</span>
                    </div>
                    <button
                      data-testid={`comment-resolve-btn-${i}`}
                      onClick={() => toggleResolved(c)}
                      className={`flex items-center gap-1 text-xs font-bold ${c.resolved ? "text-ok" : "text-zinc-500 hover:text-ok"}`}
                      style={{ transition: "color 0.15s ease" }}
                    >
                      {c.resolved ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                      {c.resolved ? "Resolved" : "Resolve"}
                    </button>
                  </div>
                  <p className="mt-2 text-sm text-zinc-200">{c.comment}</p>
                  <p className="mt-2 text-xs text-zinc-500">
                    {c.author_name} {c.author_role === "admin" && <span className="text-warn">· studio</span>} · {fmtDate(c.created_at?.slice(0, 10))}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
