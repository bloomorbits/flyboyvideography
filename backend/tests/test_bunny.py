"""Bunny Phase 1 backend — real-infrastructure tests (no mocks).

Runs against the LIVE backend (localhost:8001 by default) + REAL Supabase.
Creates real deliverables + a real second client, exercises the endpoints
over real HTTP, cleans up afterwards.

Coverage runnable without Bunny assets (real Supabase + real HTTP):
  - entitlement guard negative (client B → 403 on client A's deliverable)
  - entitlement guard positive path reaches Bunny step (own deliverable)
  - missing bunny_video_guid → 409
  - download state gate: draft → 409 not_downloadable_state;
    approved (no storage object) → 409 no-backup (proves the gate opened)
  - webhook: bad/missing signature → 401
  - signing-algorithm correctness (reproduces the documented Bunny formula)

Coverage that REQUIRES real Bunny assets (set these env vars to enable):
  - BUNNY_STREAM_TOKEN_KEY + TEST_BUNNY_VIDEO_GUID → real HEAD against
    iframe.mediadelivery.net proving the signed URL is accepted (200) and a
    tampered token is rejected (403)
  - BUNNY_STREAM_READ_ONLY_KEY → webhook valid-signature 200 path
  - TEST_BUNNY_STORAGE_OBJECT → download-url real 200 presigned S3 GET

Run:  ALLOW_ATTACK_SIM=1 SUPABASE_ANON_KEY=<anon> python backend/tests/test_bunny.py
"""
import hashlib
import hmac
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

BASE = os.environ.get("BUNNY_TEST_BASE", "http://localhost:8001")
SUPA = os.environ["SUPABASE_URL"]
SERVICE = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ANON = os.environ.get("SUPABASE_ANON_KEY") or ""
if not ANON:
    for line in (Path("/app/frontend/.env").read_text()).splitlines():
        if line.startswith("REACT_APP_SUPABASE_ANON_KEY="):
            ANON = line.split("=", 1)[1].strip()

from supabase import create_client  # noqa: E402
sb = create_client(SUPA, SERVICE)

results = {}
created = {"deliverables": [], "auth_users": [], "clients": []}


def _login(email, password):
    r = httpx.post(f"{SUPA}/auth/v1/token?grant_type=password",
                   headers={"apikey": ANON, "Content-Type": "application/json"},
                   json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def _ensure_client(email, password, role="client"):
    """Create (idempotent) a confirmed auth user + clients row."""
    uid = None
    try:
        u = sb.auth.admin.create_user({"email": email, "password": password,
                                       "email_confirm": True})
        uid = u.user.id
        created["auth_users"].append(uid)
    except Exception:
        # already exists — find it
        page = sb.auth.admin.list_users()
        users = page if isinstance(page, list) else getattr(page, "users", [])
        for usr in users:
            if getattr(usr, "email", None) == email:
                uid = usr.id
                break
    row = sb.table("clients").select("*").eq("user_id", uid).limit(1).execute().data
    if not row:
        row = [sb.table("clients").insert({
            "user_id": uid, "email": email, "full_name": "Bunny Test",
            "role": role, "is_seed_data": True}).execute().data[0]]
        created["clients"].append(row[0]["id"])
    return row[0], _login(email, password)


def check(name, cond, detail=""):
    results[name] = {"ok": bool(cond), "detail": detail}
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# ---------------------------------------------------------------------------
# Setup: two real clients (A = owner, B = interloper) + a deliverable
# ---------------------------------------------------------------------------
client_a, tok_a = _ensure_client("bunny.owner@seed.flyboytest.com", "SeedTest#2026!")
client_b, tok_b = _ensure_client("bunny.other@seed.flyboytest.com", "SeedTest#2026!")

deliv = sb.table("deliverables").insert({
    "client_id": client_a["id"], "title": "TEST_BUNNY_DELIV",
    "status": "draft", "is_seed_data": True,
}).execute().data[0]
created["deliverables"].append(deliv["id"])
DID = deliv["id"]
HA = {"Authorization": f"Bearer {tok_a}"}
HB = {"Authorization": f"Bearer {tok_b}"}


def post(path, headers, json=None):
    return httpx.post(f"{BASE}{path}", headers=headers, json=json or {}, timeout=30)


# ---------------------------------------------------------------------------
# 3. Entitlement guard NEGATIVE — client B on client A's deliverable → 403
# ---------------------------------------------------------------------------
r = post(f"/api/deliverables/{DID}/playback-token", HB)
check("entitlement_negative_403", r.status_code == 403, f"status={r.status_code}")
# and the denial was logged as an event
ev = sb.table("deliverable_access_events").select("*").eq("deliverable_id", DID)\
    .eq("event_type", "entitlement_denied").execute().data
check("entitlement_denied_logged", len(ev) >= 1, f"events={len(ev)}")

# ---------------------------------------------------------------------------
# 5. Missing GUID — owner requests playback but no bunny_video_guid → 409
# ---------------------------------------------------------------------------
r = post(f"/api/deliverables/{DID}/playback-token", HA)
check("missing_guid_409", r.status_code == 409, f"status={r.status_code}")

# ---------------------------------------------------------------------------
# 6b. Download state gate — draft → 409 not_downloadable_state
# ---------------------------------------------------------------------------
r = post(f"/api/deliverables/{DID}/download-url", HA)
gate_draft = r.status_code == 409 and "approved for download" in r.text
check("download_gate_draft_409", gate_draft, f"status={r.status_code} body={r.text[:80]}")

# flip to approved (no storage object) → gate opens, next block is "no backup"
sb.table("deliverables").update({"status": "approved"}).eq("id", DID).execute()
r = post(f"/api/deliverables/{DID}/download-url", HA)
gate_open = r.status_code == 409 and "backup" in r.text.lower()
check("download_gate_approved_opens", gate_open,
      f"status={r.status_code} body={r.text[:80]} (409 no-backup proves state gate passed)")

# If a real storage object is provided, prove the true 200 presigned path
test_obj = os.environ.get("TEST_BUNNY_STORAGE_OBJECT")
if test_obj and os.environ.get("BUNNY_STORAGE_PASSWORD"):
    sb.table("deliverables").update({"bunny_storage_object": test_obj}).eq("id", DID).execute()
    r = post(f"/api/deliverables/{DID}/download-url", HA)
    ok = r.status_code == 200 and "X-Amz-Signature" in r.json().get("url", "")
    check("download_real_presigned_200", ok, f"status={r.status_code}")
else:
    print("[SKIP] download_real_presigned_200 — set TEST_BUNNY_STORAGE_OBJECT + creds to enable")

# ---------------------------------------------------------------------------
# 1. Signing algorithm correctness (reproduce documented Bunny formula)
# ---------------------------------------------------------------------------
import bunny as B  # noqa: E402
if B.STREAM_TOKEN_KEY and B.STREAM_LIBRARY_ID:
    expires = int(time.time()) + 1800
    url = B._sign_embed_url("test-guid-1234", expires)
    expected = hashlib.sha256((B.STREAM_TOKEN_KEY + "test-guid-1234" + str(expires)).encode()).hexdigest()
    check("signing_algorithm_matches_bunny_spec", f"token={expected}" in url and
          "iframe.mediadelivery.net/embed/" in url, "sha256(key+guid+expires) hex, iframe host")

    guid = os.environ.get("TEST_BUNNY_VIDEO_GUID")
    if guid:
        exp = int(time.time()) + 1800
        good = B._sign_embed_url(guid, exp)
        hr = httpx.head(good, timeout=30, follow_redirects=True)
        check("bunny_accepts_valid_token", hr.status_code == 200, f"HEAD status={hr.status_code}")
        # Clean tamper: bump expires without re-signing → signature no longer
        # matches the (key+guid+expires) material → Bunny must reject.
        bad = good.replace(f"expires={exp}", f"expires={exp + 1}")
        hr2 = httpx.head(bad, timeout=30, follow_redirects=True)
        check("bunny_rejects_tampered_token", hr2.status_code in (403, 401), f"HEAD status={hr2.status_code}")
    else:
        print("[SKIP] bunny_accepts_valid_token — set TEST_BUNNY_VIDEO_GUID (real uploaded video) to enable")
else:
    print("[SKIP] signing tests — BUNNY_STREAM_TOKEN_KEY not in this env (Railway-only). Deploy + run there, or set locally.")

# ---------------------------------------------------------------------------
# 9. Webhook signature verification (real HMAC)
# ---------------------------------------------------------------------------
ro_key = os.environ.get("BUNNY_STREAM_READ_ONLY_KEY")
lib = os.environ.get("BUNNY_STREAM_LIBRARY_ID", "1")
body = ('{"VideoLibraryId":' + str(lib) + ',"VideoGuid":"nonexistent-guid","Status":3}').encode()
# bad signature always → 401
r = httpx.post(f"{BASE}/api/bunny/webhook", content=body,
               headers={"Content-Type": "application/json",
                        "X-BunnyStream-Signature-Version": "v1",
                        "X-BunnyStream-Signature-Algorithm": "hmac-sha256",
                        "X-BunnyStream-Signature": "0" * 64}, timeout=30)
check("webhook_bad_signature_401", r.status_code == 401, f"status={r.status_code}")
# missing headers → 401
r = httpx.post(f"{BASE}/api/bunny/webhook", content=body,
               headers={"Content-Type": "application/json"}, timeout=30)
check("webhook_missing_headers_401", r.status_code == 401, f"status={r.status_code}")
if ro_key:
    sig = hmac.new(ro_key.encode(), body, hashlib.sha256).hexdigest()
    r = httpx.post(f"{BASE}/api/bunny/webhook", content=body,
                   headers={"Content-Type": "application/json",
                            "X-BunnyStream-Signature-Version": "v1",
                            "X-BunnyStream-Signature-Algorithm": "hmac-sha256",
                            "X-BunnyStream-Signature": sig}, timeout=30)
    # valid sig, orphan guid → 200 matched:false (proves signature accepted + orphan-safe)
    ok = r.status_code == 200 and r.json().get("matched") is False
    check("webhook_valid_sig_orphan_200", ok, f"status={r.status_code} body={r.text[:80]}")
else:
    print("[SKIP] webhook_valid_sig_orphan_200 — BUNNY_STREAM_READ_ONLY_KEY not in this env (Railway-only)")

# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------
for did in created["deliverables"]:
    sb.table("deliverable_access_events").delete().eq("deliverable_id", did).execute()
    sb.table("deliverables").delete().eq("id", did).execute()
for cid in created["clients"]:
    sb.table("clients").delete().eq("id", cid).execute()
for uid in created["auth_users"]:
    try:
        sb.auth.admin.delete_user(uid)
    except Exception:
        pass

ran = [v for v in results.values()]
passed = sum(1 for v in ran if v["ok"])
print(f"\n=== {passed}/{len(ran)} runnable checks PASSED ===")
sys.exit(0 if passed == len(ran) else 1)
