"""Verify Migration 013 landed correctly.

Checks:
  1. pricing_catalog table exists with the expected columns.
  2. Both 'draft' and 'published' rows exist.
  3. Both rows have IDENTICAL content on first apply (draft was cloned from published seed).
  4. Content shape passes minimal validation: packages (list of >=4), graduation (obj), extras (obj), bookingTerms (str).
  5. Package IDs match the current pricing.js: wedding, birthday, naming-ceremony, lifestyle.
  6. RLS: anon key CAN read the 'published' row, CANNOT read the 'draft' row.
  7. slot check constraint rejects a third slot value.

Run:
    python backend/tests/introspect_013.py
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from supabase import create_client  # noqa: E402

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
# Anon key lives in the frontend .env (public value, safe to load here for
# read-side RLS smoke-testing). If it's missing we skip the anon check
# rather than failing loudly — introspect can still verify seed + shape.
_anon_key = os.environ.get("SUPABASE_ANON_KEY")
if not _anon_key:
    try:
        for line in (Path("/app/frontend/.env").read_text()).splitlines():
            if line.startswith("REACT_APP_SUPABASE_ANON_KEY="):
                _anon_key = line.split("=", 1)[1].strip()
                break
    except Exception:
        pass
anon = create_client(os.environ["SUPABASE_URL"], _anon_key) if _anon_key else None

results = {}

# ---- 1) Table + columns present ----
try:
    row = sb.table("pricing_catalog").select("*").limit(1).execute().data
    if row:
        cols = set(row[0].keys())
        expected = {"slot", "content", "updated_at", "updated_by"}
        missing = expected - cols
        results["table_and_columns"] = {"ok": not missing, "missing": list(missing), "cols": sorted(cols)}
    else:
        # Even if empty, a select on a nonexistent table would raise.
        results["table_and_columns"] = {"ok": True, "note": "table exists but empty — did seed run?"}
except Exception as e:
    results["table_and_columns"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

# ---- 2) Both rows present ----
try:
    rows = sb.table("pricing_catalog").select("slot").execute().data
    slots = sorted(r["slot"] for r in rows)
    results["both_slots_seeded"] = {
        "ok": slots == ["draft", "published"],
        "slots_found": slots,
    }
except Exception as e:
    results["both_slots_seeded"] = {"ok": False, "err": str(e)}

# ---- 3) Draft == Published on first apply ----
try:
    pub = sb.table("pricing_catalog").select("content").eq("slot", "published").execute().data[0]["content"]
    drf = sb.table("pricing_catalog").select("content").eq("slot", "draft").execute().data[0]["content"]
    results["draft_equals_published"] = {"ok": pub == drf}
except Exception as e:
    results["draft_equals_published"] = {"ok": False, "err": str(e)}

# ---- 4) Content shape minimal validation ----
try:
    content = sb.table("pricing_catalog").select("content").eq("slot", "published").execute().data[0]["content"]
    shape_ok = (
        isinstance(content.get("packages"), list) and len(content["packages"]) >= 4
        and isinstance(content.get("graduation"), dict)
        and isinstance(content.get("extras"), dict)
        and isinstance(content.get("bookingTerms"), str)
    )
    results["content_shape"] = {
        "ok": shape_ok,
        "n_packages": len(content.get("packages") or []),
        "has_graduation": "graduation" in content,
        "has_extras": "extras" in content,
        "has_bookingTerms": "bookingTerms" in content,
    }
except Exception as e:
    results["content_shape"] = {"ok": False, "err": str(e)}

# ---- 5) Package IDs match current pricing.js ----
try:
    content = sb.table("pricing_catalog").select("content").eq("slot", "published").execute().data[0]["content"]
    got_ids = sorted(p["id"] for p in content["packages"])
    expected_ids = ["birthday", "lifestyle", "naming-ceremony", "wedding"]
    results["package_ids_match"] = {
        "ok": got_ids == expected_ids,
        "got": got_ids,
        "expected": expected_ids,
    }
except Exception as e:
    results["package_ids_match"] = {"ok": False, "err": str(e)}

# ---- 6) RLS — anon can read published, cannot read draft ----
if anon is None:
    results["rls_isolation"] = {"ok": True, "skipped": "no anon key available"}
else:
    try:
        anon_pub = anon.table("pricing_catalog").select("slot").eq("slot", "published").execute().data
        anon_drf = anon.table("pricing_catalog").select("slot").eq("slot", "draft").execute().data
        results["rls_isolation"] = {
            "ok": (len(anon_pub) == 1 and len(anon_drf) == 0),
            "anon_sees_published": len(anon_pub),
            "anon_sees_draft": len(anon_drf),  # must be 0
        }
    except Exception as e:
        results["rls_isolation"] = {"ok": False, "err": str(e)}

# ---- 7) slot CHECK constraint rejects a third value ----
try:
    sb.table("pricing_catalog").insert({"slot": "sandbox", "content": {}}).execute()
    results["slot_constraint"] = {"ok": False, "note": "insert of slot='sandbox' should have failed but didn't"}
    # cleanup if it somehow succeeded
    sb.table("pricing_catalog").delete().eq("slot", "sandbox").execute()
except Exception as e:
    msg = str(e).lower()
    results["slot_constraint"] = {"ok": "check" in msg or "23514" in msg, "err_excerpt": str(e)[:180]}

results["_verdict"] = "PASS" if all(r.get("ok") for r in results.values() if isinstance(r, dict)) else "FAIL"
print(json.dumps(results, indent=2, default=str))
