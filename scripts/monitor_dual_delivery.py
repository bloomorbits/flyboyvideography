"""Dual-delivery observation dashboard for the Railway cutover.

Reads webhook_deliveries_audit and reports per-pod delivery health for the
observation window. Designed to be run periodically (cron-friendly) or
one-off. Output is human-readable + JSON summary at the end.

Usage:
    python scripts/monitor_dual_delivery.py                  # last 24h
    python scripts/monitor_dual_delivery.py --hours 6         # custom window
    python scripts/monitor_dual_delivery.py --since 2026-08-21T20:00:00Z

Health signals per pod:
  - deliveries_total
  - deliveries_2xx / deliveries_error
  - avg / p95 processing_ms
  - avg / p95 delivery_latency_ms  (received_at - stripe_created_at)
  - event_type distribution

Attribution signal (cross-pod):
  - events seen by BOTH pods (expected in dual-delivery window)
  - events seen by ONLY railway (post-cutover expected state)
  - events seen by ONLY preview (would indicate Railway missing deliveries)
  - events seen by NEITHER (would indicate audit table drift)
"""
import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

parser = argparse.ArgumentParser()
parser.add_argument("--hours", type=float, default=24.0)
parser.add_argument("--since", type=str, default=None, help="ISO 8601 timestamp")
args = parser.parse_args()

if args.since:
    since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
else:
    since = datetime.now(tz=timezone.utc) - timedelta(hours=args.hours)
since_iso = since.isoformat()

now = datetime.now(tz=timezone.utc)
window_hours = (now - since).total_seconds() / 3600.0

print("=" * 90)
print(f"Dual-delivery observation window")
print("=" * 90)
print(f"  since : {since_iso}")
print(f"  now   : {now.isoformat()}")
print(f"  span  : {window_hours:.2f} h")
print()

rows = sb.table("webhook_deliveries_audit").select("*").gte("received_at", since_iso).order("received_at", desc=False).execute().data

if not rows:
    print("  NO ROWS in window. Either no webhook traffic, or the audit table wasn't wired up in time.")
    raise SystemExit(0)

# Per-pod health
by_pod = defaultdict(list)
for r in rows:
    by_pod[r["pod_source"]].append(r)

print("-" * 90)
print("PER-POD DELIVERY HEALTH")
print("-" * 90)
pod_summary = {}
for pod, entries in sorted(by_pod.items()):
    total = len(entries)
    ok = sum(1 for e in entries if e["response_status"] == 200)
    err = total - ok
    proc_times = [e["processing_ms"] for e in entries if e.get("processing_ms") is not None]

    def latency(e):
        if not e.get("stripe_created_at"):
            return None
        try:
            sc = datetime.fromisoformat(e["stripe_created_at"].replace("Z", "+00:00"))
            rc = datetime.fromisoformat(e["received_at"].replace("Z", "+00:00"))
            return int((rc - sc).total_seconds() * 1000)
        except Exception:
            return None
    latencies = [x for x in (latency(e) for e in entries) if x is not None]

    def p(xs, q):
        if not xs:
            return None
        xs_sorted = sorted(xs)
        idx = min(len(xs_sorted) - 1, int(q * len(xs_sorted)))
        return xs_sorted[idx]

    types = defaultdict(int)
    for e in entries:
        types[e["event_type"]] += 1
    outcomes = defaultdict(int)
    for e in entries:
        outcomes[e.get("finalise_outcome") or "n/a"] += 1

    # Break out processing_ms by path — finalisation is the "expensive"
    # path (booking insert, email, auth-link) and is what actually matters
    # for latency. Skips/replays touch far fewer queries.
    proc_by_path = defaultdict(list)
    lat_by_path = defaultdict(list)
    for e in entries:
        outcome = e.get("finalise_outcome") or "n/a"
        if outcome == "finalised":
            path = "finalised"
        elif outcome.startswith("skipped_"):
            path = "skip_or_replay"
        elif outcome in ("refunded_race",):
            path = outcome
        elif outcome in ("expired", "async_payment_failed"):
            path = outcome
        elif outcome == "error":
            path = "error"
        else:
            path = "other"
        if e.get("processing_ms") is not None:
            proc_by_path[path].append(e["processing_ms"])
        l = latency(e)
        if l is not None:
            lat_by_path[path].append(l)

    print(f"\n  pod_source = {pod!r}")
    print(f"    deliveries_total : {total}")
    print(f"    2xx / errors     : {ok} / {err}")
    print(f"    processing_ms    : avg={int(mean(proc_times)) if proc_times else '?':>4}  p95={p(proc_times, 0.95) if proc_times else '?'}  (all paths mixed)")
    print(f"    latency_ms       : avg={int(mean(latencies)) if latencies else '?':>4}  p95={p(latencies, 0.95) if latencies else '?'}  (received_at - stripe_created_at)")
    print(f"    event_type_dist  : {dict(types)}")
    print(f"    outcome_dist     : {dict(outcomes)}")

    # Per-path breakdown — critical for spotting real regressions on the
    # finalisation path vs noise from cheap skip paths.
    if proc_by_path:
        print(f"    processing_ms BY PATH:")
        for path in sorted(proc_by_path):
            xs = proc_by_path[path]
            xs_lat = lat_by_path.get(path, [])
            proc_str = f"n={len(xs):<3} avg={int(mean(xs)):<5} p50={p(xs, 0.50)} p95={p(xs, 0.95)} max={max(xs)}"
            lat_str = (
                f"  latency: avg={int(mean(xs_lat))} p95={p(xs_lat, 0.95)}"
                if xs_lat else ""
            )
            print(f"      {path:22s} {proc_str}{lat_str}")
    pod_summary[pod] = {
        "total": total,
        "ok": ok,
        "err": err,
        "processing_ms_finalised": {
            "n": len(proc_by_path.get("finalised", [])),
            "avg": int(mean(proc_by_path["finalised"])) if proc_by_path.get("finalised") else None,
            "p95": p(proc_by_path.get("finalised", []), 0.95),
            "max": max(proc_by_path["finalised"]) if proc_by_path.get("finalised") else None,
        },
        "latency_ms_finalised": {
            "n": len(lat_by_path.get("finalised", [])),
            "avg": int(mean(lat_by_path["finalised"])) if lat_by_path.get("finalised") else None,
            "p95": p(lat_by_path.get("finalised", []), 0.95),
        },
    }

# Cross-pod attribution
print()
print("-" * 90)
print("CROSS-POD ATTRIBUTION (checkout.session.completed only)")
print("-" * 90)
completed_by_event = defaultdict(set)
for e in rows:
    if e["event_type"] == "checkout.session.completed":
        completed_by_event[e["stripe_event_id"]].add(e["pod_source"])

seen_by_both = [ev for ev, pods in completed_by_event.items() if {"railway", "preview"}.issubset(pods)]
railway_only = [ev for ev, pods in completed_by_event.items() if pods == {"railway"}]
preview_only = [ev for ev, pods in completed_by_event.items() if pods == {"preview"}]
other        = [ev for ev, pods in completed_by_event.items() if pods and not ({"railway", "preview"} & pods)]

print(f"  completed events in window : {len(completed_by_event)}")
print(f"  seen by BOTH railway+preview: {len(seen_by_both)}   <-- expected in dual-delivery window")
print(f"  seen by railway ONLY        : {len(railway_only)}   <-- expected post-cutover")
print(f"  seen by preview ONLY        : {len(preview_only)}   <-- RED FLAG if > 0 during dual window")
print(f"  seen by other/unknown pod   : {len(other)}          <-- audit misconfig")

if preview_only:
    print("\n  preview-only event IDs (first 10):")
    for ev in preview_only[:10]:
        print(f"    {ev}")

# Overall health verdict
print()
print("-" * 90)
print("VERDICT")
print("-" * 90)
if not by_pod:
    verdict = "NO DATA"
elif "railway" not in by_pod:
    verdict = "🛑 Railway pod has written ZERO audit rows in this window. Check POD_SOURCE_LABEL env var on Railway and that redeploy picked it up."
elif preview_only:
    verdict = f"⚠️  Railway missed {len(preview_only)} events that preview received. Dual-delivery is NOT healthy — do NOT retire preview."
elif seen_by_both and not preview_only:
    verdict = f"✅ Dual-delivery healthy: {len(seen_by_both)}/{len(completed_by_event)} completed events received by both pods. Preview retirement is safe once you're satisfied with the observation length."
else:
    verdict = "ℹ️  Not enough completed events yet to judge. Trigger a few test checkouts."
print(f"  {verdict}")

# JSON summary at end for scripting
print()
print("=" * 90)
print("JSON SUMMARY")
print("=" * 90)
print(json.dumps({
    "window": {"since": since_iso, "now": now.isoformat(), "hours": round(window_hours, 2)},
    "by_pod": pod_summary,
    "completed_events": {
        "total_unique": len(completed_by_event),
        "seen_by_both": len(seen_by_both),
        "railway_only": len(railway_only),
        "preview_only": len(preview_only),
        "other": len(other),
    },
    "verdict": verdict,
}, indent=2))
