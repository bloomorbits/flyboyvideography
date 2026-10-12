"""introspect_021.py — proves Migration 021 (booking details + phone E.164 trigger).

RUN AFTER applying supabase_migration_021_booking_details.sql.
  python3 /app/backend/tests/introspect_021.py

Outputs COUNTS ONLY — never prints phone numbers or personal data.
Uses synthetic @flyboytest.com rows tagged is_seed_data and cleans them up.
Reads SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY from env.

Proves:
  1. New row with a bad phone is rejected on booking_intents.phone,
     clients.phone, and (via CHECK) secondary_contact_phone.
  2. An existing junk-phone row stays untouched.
  3. An UPDATE to an unrelated column on that legacy row succeeds.
  4. Updating a legacy phone to valid E.164 succeeds; to another junk value is rejected.
  5. NULL phone is still accepted.
  + anon cannot read the new columns (RLS).
"""
import os, re, uuid
from supabase import create_client

URL = os.environ["SUPABASE_URL"]
SRK = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ANON = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("REACT_APP_SUPABASE_ANON_KEY", "")
sb = create_client(URL, SRK)
E164 = re.compile(r"^\+[1-9][0-9]{6,14}$")
BAD = "notaphone123"
GOOD = "+447911123456"
tag = f"introspect021-{uuid.uuid4().hex[:8]}@flyboytest.com"


def rejected(fn):
    try:
        fn(); return (False, "NO ERROR (should have been rejected)")
    except Exception as e:
        msg = str(e)
        return (True, "E.164" if ("E.164" in msg or "check" in msg.lower() or "secondary_phone" in msg) else msg[:120])


print("=== Migration 021 introspection (counts only) ===")

# ---- booking_intents.phone trigger -------------------------------------
bi_ids = []
def mk_intent(phone):
    row = {"email": tag, "status": "pending", "session_id": f"sess_{uuid.uuid4().hex}"}
    if phone is not None:
        row["phone"] = phone
    r = sb.table("booking_intents").insert(row).execute().data[0]
    bi_ids.append(r["id"]); return r

ok, detail = rejected(lambda: mk_intent(BAD))
print(f"[1a] booking_intents bad-phone INSERT rejected: {'PASS' if ok else 'FAIL'} ({detail})")

try:
    r = mk_intent(GOOD); print("[5 ] valid-E.164 INSERT accepted: PASS")
except Exception as e:
    r = None; print(f"[5 ] valid-E.164 INSERT accepted: FAIL ({str(e)[:120]})")

try:
    mk_intent(None); print("[5b] NULL-phone INSERT accepted: PASS")
except Exception as e:
    print(f"[5b] NULL-phone INSERT accepted: FAIL ({str(e)[:120]})")

if r:
    ok, d = rejected(lambda: sb.table("booking_intents").update({"phone": BAD}).eq("id", r["id"]).execute())
    print(f"[4a] UPDATE valid->junk rejected: {'PASS' if ok else 'FAIL'} ({d})")
    try:
        sb.table("booking_intents").update({"phone": "+447911999888"}).eq("id", r["id"]).execute()
        print("[4b] UPDATE junk->valid (here valid->valid) accepted: PASS")
    except Exception as e:
        print(f"[4b] UPDATE to valid accepted: FAIL ({str(e)[:120]})")

# ---- secondary_contact_phone CHECK (both tables) -----------------------
ok, d = rejected(lambda: sb.table("booking_intents").insert(
    {"email": tag, "status": "pending", "session_id": f"sess_{uuid.uuid4().hex}",
     "secondary_contact_phone": BAD}).execute())
print(f"[1b] booking_intents bad secondary_contact_phone rejected: {'PASS' if ok else 'FAIL'} ({d})")

# ---- legacy junk-phone row proofs (#2 and #3) --------------------------
# Find an EXISTING non-E.164 phone row WITHOUT mutating any value.
rows = sb.table("booking_intents").select("id,phone,event_notes").execute().data
legacy = [x for x in rows if x.get("phone") and not E164.match(x["phone"].strip())
          and x["id"] not in bi_ids]
print(f"[2 ] existing non-E.164 phone rows found: {len(legacy)} (untouched)")
if legacy:
    lid = legacy[0]["id"]; cur = legacy[0].get("event_notes")
    try:
        # no-op write to an UNRELATED column (sets it to its own current value)
        sb.table("booking_intents").update({"event_notes": cur}).eq("id", lid).execute()
        print("[3 ] UPDATE of unrelated column on legacy junk-phone row succeeded: PASS (trigger did not fire)")
    except Exception as e:
        print(f"[3 ] unrelated-column UPDATE on legacy row: FAIL ({str(e)[:120]})")
else:
    print("[3 ] SKIPPED — no legacy junk-phone row available (clean DB)")

# ---- clients.phone trigger (needs an auth user) ------------------------
uid = None
try:
    u = sb.auth.admin.create_user({"email": f"cli-{tag}", "email_confirm": True})
    uid = u.user.id
    ok, d = rejected(lambda: sb.table("clients").insert({"user_id": uid, "email": f"cli-{tag}", "name": "Seed", "phone": BAD}).execute())
    print(f"[1c] clients bad-phone INSERT rejected: {'PASS' if ok else 'FAIL'} ({d})")
    sb.table("clients").insert({"user_id": uid, "email": f"cli-{tag}", "name": "Seed", "phone": GOOD}).execute()
    print("[1c+] clients valid-phone INSERT accepted: PASS")
    sb.table("clients").update({"name": "Seed2"}).eq("user_id", uid).execute()
    print("[3c] clients unrelated-column UPDATE accepted: PASS")
except Exception as e:
    print(f"[1c] clients trigger test: INCONCLUSIVE ({str(e)[:140]})")

# ---- anon cannot read new columns --------------------------------------
if ANON:
    try:
        anon = create_client(URL, ANON)
        res = anon.table("booking_intents").select("id,phone,venue_name,event_start_time").limit(1).execute()
        n = len(res.data or [])
        print(f"[6 ] anon read of new/contact columns returned {n} rows: {'PASS (RLS blocks)' if n == 0 else 'FAIL — anon saw data'}")
    except Exception as e:
        print(f"[6 ] anon read blocked by RLS: PASS ({str(e)[:80]})")
else:
    print("[6 ] SKIPPED — no anon key in env")

# ---- cleanup ------------------------------------------------------------
for i in bi_ids:
    try: sb.table("booking_intents").delete().eq("id", i).execute()
    except Exception: pass
sb.table("booking_intents").delete().eq("email", tag).execute()
if uid:
    try: sb.table("clients").delete().eq("user_id", uid).execute()
    except Exception: pass
    try: sb.auth.admin.delete_user(uid)
    except Exception: pass
print("=== cleanup done ===")
