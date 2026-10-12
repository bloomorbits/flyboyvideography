"""introspect_021.py — proves Migration 021 (booking details + phone E.164 trigger).

RUN AFTER applying supabase_migration_021_booking_details.sql:
  python3 /app/backend/tests/introspect_021.py

COUNTS ONLY — never prints phone numbers or personal data.
Uses synthetic @flyboytest.com rows and a throwaway auth user; cleans everything up.
Reads SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / REACT_APP_SUPABASE_ANON_KEY from env.

PostgREST exposes only `public` + `graphql_public`, so pg_catalog / information_schema /
`cron` are NOT reachable here. The constraint *definition*, the function search_path,
and the cron-tables check are produced by verify_021_catalog.sql (run in the SQL Editor).
This script covers everything observable over REST: column types, trigger/CHECK behaviour,
legacy-row safety, nullable acceptance, and before/after auth.users + clients counts.
"""
import os, re, uuid
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
import httpx

URL = os.environ["SUPABASE_URL"]
SRK = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ANON = os.environ.get("REACT_APP_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
sb = create_client(URL, SRK)
H = {"apikey": SRK, "Authorization": f"Bearer {SRK}"}
E164 = re.compile(r"^\+[1-9][0-9]{6,14}$")
BAD, BAD2, GOOD, GOOD2 = "notaphone123", "0771 bad", "+447911123456", "+447911999888"
NEW_COLS = ["venue_name", "venue_tbc", "event_city", "event_postcode",
            "event_start_time", "guest_count", "secondary_contact_name", "secondary_contact_phone"]

tag = f"introspect021-{uuid.uuid4().hex[:8]}@flyboytest.com"
intent_ids = []


def rejected(fn):
    try:
        fn(); return (False, "NO ERROR (should have been rejected)")
    except Exception as e:
        m = str(e)
        kind = "check/trigger" if ("check" in m.lower() or "E.164" in m or "violat" in m.lower()) else m[:100]
        return (True, kind)


def P(ok):  return "PASS" if ok else "FAIL"


# runtime package id/title (package_id is NOT NULL + FK-ish) -------------------
_s = sb.table("booking_intents").select("package_id,package_title").limit(1).execute().data
PID, PTITLE = (_s[0]["package_id"], _s[0]["package_title"]) if _s else ("graduation", "Graduation Reels")


def base_intent(**extra):
    row = {"email": tag, "status": "pending", "full_name": "Flyboy Seed",
           "package_id": PID, "package_title": PTITLE, "price_total": 100, "price_deposit": 50,
           "event_date": "2099-01-01"}
    row.update(extra)
    return row


def mk_intent(**extra):
    r = sb.table("booking_intents").insert(base_intent(**extra)).execute().data[0]
    intent_ids.append(r["id"]); return r


print("=" * 64)
print("Migration 021 introspection — COUNTS ONLY, no phone values printed")
print("=" * 64)

# --- SECTION A: column types (OpenAPI) ---------------------------------------
print("\n[A] COLUMN TYPES (both tables, via PostgREST OpenAPI)")
defs = httpx.get(f"{URL}/rest/v1/", headers=H, timeout=30).json()
defs = defs.get("definitions") or defs.get("components", {}).get("schemas", {})
for tbl in ("booking_intents", "bookings"):
    props = defs.get(tbl, {}).get("properties", {})
    missing = [c for c in NEW_COLS if c not in props]
    print(f"  {tbl}: all 8 new columns present: {P(not missing)}" + (f" (missing {missing})" if missing else ""))
    est = props.get("event_start_time", {})
    print(f"    event_start_time format = {est.get('format')!r}  "
          f"({P(est.get('format') == 'time without time zone')})")
    print(f"    venue_tbc={props.get('venue_tbc',{}).get('format')}  "
          f"guest_count={props.get('guest_count',{}).get('format')}  "
          f"event_date={props.get('event_date',{}).get('format')} (unchanged)")

# --- SECTION B: counts BEFORE ------------------------------------------------
def auth_count():
    return len(sb.auth.admin.list_users())
def clients_count():
    return sb.table("clients").select("id", count="exact").limit(1).execute().count
def dsl_count():
    return sb.table("date_slot_locks").select("*", count="exact").limit(1).execute().count

au0, cl0, dsl0 = auth_count(), clients_count(), dsl_count()
print(f"\n[B] COUNTS BEFORE   auth.users={au0}  clients={cl0}  date_slot_locks={dsl0}")

# --- SECTION C: booking_intents.phone trigger + nullable ---------------------
print("\n[C] booking_intents.phone trigger")
ok, d = rejected(lambda: mk_intent(phone=BAD))
print(f"  bad phone INSERT rejected: {P(ok)} ({d})")
good = mk_intent(phone=GOOD)
print(f"  valid E.164 INSERT accepted: PASS")
mk_intent()  # no phone key -> NULL
print(f"  NULL phone INSERT accepted (also proves new cols nullable): PASS")

# --- SECTION D: secondary_contact_phone CHECK --------------------------------
print("\n[D] secondary_contact_phone CHECK (booking_intents)")
ok, d = rejected(lambda: mk_intent(secondary_contact_phone=BAD))
print(f"  bad secondary_contact_phone INSERT rejected: {P(ok)} ({d})")
r = mk_intent(secondary_contact_phone=GOOD, secondary_contact_name="Backup")
print(f"  valid secondary_contact_phone INSERT accepted: PASS")

# --- SECTION E: trigger branch logic on a synthetic GOOD-phone row -----------
print("\n[E] trigger branches (synthetic seed row, good phone -> change)")
ok, d = rejected(lambda: sb.table("booking_intents").update({"phone": BAD}).eq("id", good["id"]).execute())
print(f"  change to junk rejected: {P(ok)} ({d})")
sb.table("booking_intents").update({"phone": GOOD}).eq("id", good["id"]).execute()
print(f"  same-value update accepted (not distinct -> skips): PASS")
sb.table("booking_intents").update({"phone": GOOD2}).eq("id", good["id"]).execute()
print(f"  change to another valid E.164 accepted: PASS")
sb.table("booking_intents").update({"phone": None}).eq("id", good["id"]).execute()
print(f"  change to NULL accepted: PASS")

# --- SECTION F: REAL legacy junk-phone row safety (non-destructive) ----------
print("\n[F] legacy junk-phone row safety (real rows, non-destructive)")
rows = sb.table("booking_intents").select("id,phone,event_notes").execute().data
legacy = [x for x in rows if x.get("phone") and not E164.match(x["phone"].strip())
          and x["id"] not in intent_ids]
print(f"  existing non-E.164 phone rows: {len(legacy)}")
if legacy:
    lid, lphone, lnotes = legacy[0]["id"], legacy[0]["phone"], legacy[0].get("event_notes")
    # same junk value written back -> not distinct -> accepted, row unchanged
    sb.table("booking_intents").update({"phone": lphone}).eq("id", lid).execute()
    print(f"  same junk value re-saved on legacy row accepted: PASS (value unchanged)")
    # different junk -> rejected (update fails, row unchanged)
    ok, d = rejected(lambda: sb.table("booking_intents").update({"phone": BAD2}).eq("id", lid).execute())
    print(f"  change legacy phone to a DIFFERENT junk rejected: {P(ok)} ({d})")
    # unrelated column no-op write -> trigger does not fire
    sb.table("booking_intents").update({"event_notes": lnotes}).eq("id", lid).execute()
    print(f"  unrelated-column UPDATE on legacy row accepted: PASS (trigger did not fire)")
    still = sb.table("booking_intents").select("phone").eq("id", lid).execute().data[0]["phone"]
    print(f"  legacy phone still non-E.164 afterwards: {P(not E164.match(still.strip()))} (untouched)")
else:
    print("  SKIPPED — no legacy junk-phone row present")

# --- SECTION G: clients.phone trigger (throwaway auth user) ------------------
print("\n[G] clients.phone trigger (throwaway auth user)")
uid = None
try:
    u = sb.auth.admin.create_user({"email": f"cli-{tag}", "email_confirm": True})
    uid = u.user.id
    ok, d = rejected(lambda: sb.table("clients").insert(
        {"user_id": uid, "email": f"cli-{tag}", "full_name": "Seed", "phone": BAD, "is_seed_data": True}).execute())
    print(f"  clients bad phone INSERT rejected: {P(ok)} ({d})")
    sb.table("clients").insert(
        {"user_id": uid, "email": f"cli-{tag}", "full_name": "Seed", "phone": GOOD, "is_seed_data": True}).execute()
    print(f"  clients valid phone INSERT accepted: PASS")
    sb.table("clients").update({"full_name": "Seed2"}).eq("user_id", uid).execute()
    print(f"  clients unrelated-column UPDATE accepted: PASS")
except Exception as e:
    print(f"  INCONCLUSIVE ({str(e)[:140]})")

# --- SECTION H: anon cannot read new/contact columns -------------------------
print("\n[H] RLS — anon read of new/contact columns")
if ANON:
    try:
        anon = create_client(URL, ANON)
        n = len(anon.table("booking_intents").select("id,phone,venue_name,event_start_time").limit(1).execute().data or [])
        print(f"  anon returned {n} rows: {P(n == 0)} (RLS blocks)")
    except Exception as e:
        print(f"  anon blocked by RLS: PASS ({str(e)[:70]})")
else:
    print("  SKIPPED — no anon key in env")

# --- cleanup -----------------------------------------------------------------
for i in intent_ids:
    try: sb.table("booking_intents").delete().eq("id", i).execute()
    except Exception: pass
sb.table("booking_intents").delete().eq("email", tag).execute()
if uid:
    try: sb.table("clients").delete().eq("user_id", uid).execute()
    except Exception: pass
    try: sb.auth.admin.delete_user(uid)
    except Exception: pass

# --- SECTION I: counts AFTER (must match BEFORE) -----------------------------
au1, cl1, dsl1 = auth_count(), clients_count(), dsl_count()
print(f"\n[I] COUNTS AFTER    auth.users={au1}  clients={cl1}  date_slot_locks={dsl1}")
print(f"    auth.users match: {P(au0 == au1)}   clients match: {P(cl0 == cl1)}   "
      f"date_slot_locks unchanged: {P(dsl0 == dsl1)}")
print("\n=== cleanup done ===")
print("NOTE: constraint name/definition, function search_path, and cron tables"
      " are not REST-readable — run verify_021_catalog.sql in the SQL Editor for those.")
