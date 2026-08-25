import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, Circle, Download, Play, ThumbsUp, Undo2 } from "lucide-react";
import { supabase } from "../lib/supabase";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Btn, Card, Input, Label, SourceBadge, StatusPill, fmtDate, parseTimecode, secondsToTimecode } from "../components/ui";

export default function DeliverableDetail() {
  const { id } = useParams();
  const { profile } = useAuth();
  const [deliv, setDeliv] = useState(null);
  const [comments, setComments] = useState([]);
  const [form, setForm] = useState({ timecode: "", comment: "" });
  const [busy, setBusy] = useState(false);
  const [approving, setApproving] = useState(false);
  const [showChanges, setShowChanges] = useState(false);
  const [changeForm, setChangeForm] = useState({ timecode: "", note: "" });
  const [requesting, setRequesting] = useState(false);
  const [playback, setPlayback] = useState(null); // { embed_url, overlay_code, expires }
  const [loadingPlay, setLoadingPlay] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const heartbeatRef = useRef(null);

  const load = useCallback(async () => {
    const [{ data: d }, { data: c }] = await Promise.all([
      supabase.from("deliverables").select("*").eq("id", id).single(),
      supabase.from("review_threads").select("*").eq("deliverable_id", id).order("timestamp_seconds", { ascending: true, nullsFirst: false }),
    ]);
    setDeliv(d);
    setComments(c || []);
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const sendPlayEvent = useCallback((event) => {
    api.post(`/deliverables/${id}/play-event`, { event }).catch(() => {});
  }, [id]);

  const watchFilm = async () => {
    setLoadingPlay(true);
    try {
      const { data } = await api.post(`/deliverables/${id}/playback-token`);
      setPlayback(data);
      sendPlayEvent("play");
    } catch (err) {
      toast.error(typeof err.response?.data?.detail === "string" ? err.response.data.detail : "Couldn't start playback");
    } finally {
      setLoadingPlay(false);
    }
  };

  const downloadOriginal = async () => {
    setDownloading(true);
    try {
      const { data } = await api.post(`/deliverables/${id}/download-url`);
      window.location.href = data.url;
    } catch (err) {
      toast.error(typeof err.response?.data?.detail === "string" ? err.response.data.detail : "Download not available");
    } finally {
      setDownloading(false);
    }
  };

  // Heartbeat while the player is mounted (best-effort, rate-limited server-side).
  useEffect(() => {
    if (!playback) return;
    heartbeatRef.current = setInterval(() => sendPlayEvent("player_heartbeat"), 30000);
    return () => clearInterval(heartbeatRef.current);
  }, [playback, sendPlayEvent]);

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

  const approveCut = async () => {
    setApproving(true);
    try {
      await api.post(`/deliverables/${id}/approve`);
      toast.success("Cut approved — your editor has been notified in the portal");
      await load();
    } catch (err) {
      toast.error(typeof err.response?.data?.detail === "string" ? err.response.data.detail : "Approval failed");
    } finally {
      setApproving(false);
    }
  };

  const requestChanges = async (e) => {
    e.preventDefault();
    setRequesting(true);
    try {
      const { data } = await api.post(`/deliverables/${id}/request-changes`, {
        note: changeForm.note,
        timestamp_seconds: parseTimecode(changeForm.timecode),
      });
      if (data.extra_round) {
        toast.warning(`Revision round ${data.revision_rounds_used} exceeds the ${data.included_revision_rounds} included rounds — this round may be billed as an extra.`);
      } else {
        toast.success(`Changes requested — revision round ${data.revision_rounds_used} of ${data.included_revision_rounds} included`);
      }
      setChangeForm({ timecode: "", note: "" });
      setShowChanges(false);
      await load();
    } catch (err) {
      toast.error(typeof err.response?.data?.detail === "string" ? err.response.data.detail : "Request failed");
    } finally {
      setRequesting(false);
    }
  };

  if (!deliv) return <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/70">Loading…</p>;

  const roundsUsed = deliv.revision_rounds_used ?? 0;
  const roundsIncluded = deliv.included_revision_rounds ?? 0;

  return (
    <div data-testid="deliverable-detail-page">
      <Link to="/deliverables" data-testid="back-to-deliverables" className="mb-6 inline-flex items-center gap-2 text-sm text-ink/60 hover:text-accent" style={{ transition: "color 0.15s ease" }}>
        <ArrowLeft size={15} /> All deliverables
      </Link>

      <div className="rise mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <SourceBadge type={deliv.booking_id ? "booking" : "subscription"} />
            <span className="font-mono text-xs text-ink/70">VERSION {deliv.version}</span>
            <span data-testid="revision-rounds-chip" className={`rounded px-2 py-0.5 font-mono text-[11px] font-bold ${roundsUsed >= roundsIncluded ? "bg-[#B45309]/15 text-[#B45309]" : "bg-sand text-ink/60"}`}>
              REVISIONS {roundsUsed}/{roundsIncluded} INCLUDED
            </span>
          </div>
          <h1 className="font-display text-4xl font-bold tracking-tighter">{deliv.title}</h1>
          {deliv.approved_at && (
            <p data-testid="approval-record" className="mt-2 flex items-center gap-2 text-sm text-[#15803D]">
              <CheckCircle2 size={15} /> Approved by {deliv.approved_by_name} · {fmtDate(deliv.approved_at.slice(0, 10))}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4">
          {["in_review", "revisions_requested"].includes(deliv.status) && (
            <Btn data-testid="approve-cut-btn" onClick={approveCut} disabled={approving}>
              <span className="flex items-center gap-2">
                <ThumbsUp size={15} /> {approving ? "Approving…" : "Approve this cut"}
              </span>
            </Btn>
          )}
          {["in_review", "approved"].includes(deliv.status) && (
            <Btn data-testid="request-changes-btn" variant="danger" onClick={() => setShowChanges(!showChanges)}>
              <span className="flex items-center gap-2">
                <Undo2 size={15} /> Request changes
              </span>
            </Btn>
          )}
          <StatusPill status={deliv.status} testId="deliverable-status" />
        </div>
      </div>

      {showChanges && (
        <div className="rise mb-8 rounded-md border border-[#B45309]/40 bg-[#B45309]/5 p-6">
          {roundsUsed >= roundsIncluded && (
            <p data-testid="extra-round-warning" className="mb-4 font-mono text-xs font-bold uppercase tracking-widest text-[#B45309]">
              Heads up: all {roundsIncluded} included revision rounds are used — this round may be billed as an extra.
            </p>
          )}
          <form onSubmit={requestChanges} className="flex flex-wrap items-end gap-4">
            <div className="w-28">
              <Label>Timecode</Label>
              <Input data-testid="changes-timecode-input" value={changeForm.timecode} onChange={(e) => setChangeForm({ ...changeForm, timecode: e.target.value })} placeholder="01:24" className="font-mono" />
            </div>
            <div className="min-w-64 flex-1">
              <Label>What needs to change?</Label>
              <Input data-testid="changes-note-input" value={changeForm.note} onChange={(e) => setChangeForm({ ...changeForm, note: e.target.value })} placeholder="Describe the revisions you need…" required />
            </div>
            <Btn data-testid="changes-submit-btn" type="submit" disabled={requesting}>
              {requesting ? "Sending…" : "Send revision request"}
            </Btn>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <Card className="overflow-hidden">
            {playback ? (
              <div className="relative aspect-video bg-black" data-testid="deliverable-player">
                <iframe
                  title={deliv.title}
                  src={playback.embed_url}
                  className="h-full w-full"
                  allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;"
                  allowFullScreen
                  frameBorder="0"
                />
                {playback.overlay_code && (
                  <div
                    data-testid="playback-overlay-code"
                    className="pointer-events-none absolute right-3 top-3 rounded bg-black/45 px-2.5 py-1 font-mono text-[11px] font-semibold tracking-widest text-white/90 backdrop-blur-sm"
                  >
                    {playback.overlay_code}
                  </div>
                )}
              </div>
            ) : deliv.bunny_video_guid ? (
              <div className="flex aspect-video flex-col items-center justify-center gap-4 bg-sand" data-testid="deliverable-poster">
                <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/40">
                  {deliv.bunny_status && !["Finished", "ResolutionFinished"].includes(deliv.bunny_status)
                    ? `Preparing your film… (${deliv.bunny_status})`
                    : "Your film is ready"}
                </p>
                <Btn data-testid="watch-film-btn" onClick={watchFilm} disabled={loadingPlay}>
                  <span className="flex items-center gap-2">
                    <Play size={15} /> {loadingPlay ? "Loading…" : "Watch film"}
                  </span>
                </Btn>
              </div>
            ) : (
              <div className="flex aspect-video items-center justify-center bg-sand">
                <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/40">No preview uploaded</p>
              </div>
            )}
            <div className="flex items-center justify-between gap-4 border-t border-dune px-6 py-4">
              <p className="text-sm text-ink/60">{deliv.notes || "No editor notes for this cut."}</p>
              {["approved", "final_delivered"].includes(deliv.status) && deliv.bunny_storage_object && (
                <button
                  onClick={downloadOriginal}
                  disabled={downloading}
                  data-testid="download-original-btn"
                  className="flex shrink-0 items-center gap-2 rounded-md bg-[#15803D]/10 px-4 py-2 text-sm font-bold text-[#15803D] hover:bg-[#15803D]/20 disabled:opacity-60"
                  style={{ transition: "background-color 0.15s ease" }}
                >
                  <Download size={15} /> {downloading ? "Preparing…" : "Download original"}
                </button>
              )}
            </div>
          </Card>
        </div>

        <div>
          <h2 className="mb-4 font-display text-xl font-semibold tracking-tight">Review thread</h2>
          <Card className="p-5">
            <form onSubmit={addComment} className="space-y-4 border-b border-dune pb-5">
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
              {comments.length === 0 && <p className="text-sm text-ink/70">No notes yet on this version.</p>}
              {comments.map((c, i) => (
                <div key={c.id} className={`rise rounded-md border border-dune p-4 ${c.resolved ? "opacity-50" : ""}`} data-testid={`review-comment-${i}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {c.timestamp_seconds !== null && (
                        <span className="rounded bg-accent/10 px-2 py-0.5 font-mono text-xs font-bold text-accent">
                          {secondsToTimecode(Number(c.timestamp_seconds))}
                        </span>
                      )}
                      <span className="font-mono text-[10px] uppercase tracking-widest text-ink/70">v{c.version}</span>
                    </div>
                    {(profile?.role === "admin" || profile?.user_id === c.author_user_id) && (
                    <button
                      data-testid={`comment-resolve-btn-${i}`}
                      onClick={() => toggleResolved(c)}
                      className={`flex items-center gap-1 text-xs font-bold ${c.resolved ? "text-[#15803D]" : "text-ink/70 hover:text-[#15803D]"}`}
                      style={{ transition: "color 0.15s ease" }}
                    >
                      {c.resolved ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                      {c.resolved ? "Resolved" : "Resolve"}
                    </button>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-ink">{c.comment}</p>
                  <p className="mt-2 text-xs text-ink/70">
                    {c.author_name} {c.author_role === "admin" && <span className="text-[#B45309]">· studio</span>} · {fmtDate(c.created_at?.slice(0, 10))}
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
