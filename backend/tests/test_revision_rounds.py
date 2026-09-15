"""Backend spot-checks for the request-changes / revision-rounds flow.

HERMETIC: the old version depended on a hand-seeded demo client
(demo.client.frameform@gmail.com) and specific seed deliverables ("Q3 Teaser",
"May Recap") that were purged in a later session, so the suite errored at
setup. It now self-provisions its own deliverable owned by the durable
`bunny.owner@seed` test client (see memory/test_credentials.md) and cleans up,
so it no longer depends on any human-seeded data.
"""
import os
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://db-bridge-5.preview.emergentagent.com").rstrip("/")
SUPABASE_URL = os.environ["SUPABASE_URL"]
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("REACT_APP_SUPABASE_ANON_KEY")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or pytest.skip(
    "SUPABASE_SERVICE_ROLE_KEY not set — export it from backend/.env before running",
    allow_module_level=True,
)
if not ANON_KEY:
    # fall back to the anon key from frontend/.env
    fe = Path(__file__).resolve().parent.parent.parent / "frontend" / ".env"
    for line in fe.read_text().splitlines() if fe.exists() else []:
        if line.startswith("REACT_APP_SUPABASE_ANON_KEY="):
            ANON_KEY = line.split("=", 1)[1].strip()
if not ANON_KEY:
    pytest.skip("anon key not found for sign-in", allow_module_level=True)

CLIENT_EMAIL = "bunny.owner@seed.flyboytest.com"
CLIENT_PASS = "SeedTest#2026!"


def _login(email, password):
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _user_id(token):
    r = requests.get(f"{SUPABASE_URL}/auth/v1/user",
                     headers={"apikey": ANON_KEY, "Authorization": f"Bearer {token}"}, timeout=15)
    r.raise_for_status()
    return r.json()["id"]


@pytest.fixture(scope="module")
def ctx():
    """Login + self-provision a final_delivered deliverable owned by the
    bunny.owner client. Cleaned up on teardown."""
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_KEY)
    token = _login(CLIENT_EMAIL, CLIENT_PASS)
    uid = _user_id(token)
    client = sb.table("clients").select("id").eq("user_id", uid).limit(1).execute().data
    assert client, f"no clients row for {CLIENT_EMAIL}"
    client_id = client[0]["id"]

    deliv = sb.table("deliverables").insert({
        "client_id": client_id,
        "title": "__revtest_final__",
        "status": "final_delivered",
        "included_revision_rounds": 2,
        "revision_rounds_used": 0,
        "is_seed_data": True,
    }).execute().data[0]

    yield {"token": token, "client_id": client_id, "deliv_id": deliv["id"]}

    # Teardown — remove any review_threads first (FK), then the deliverable.
    try:
        sb.table("review_threads").delete().eq("deliverable_id", deliv["id"]).execute()
    except Exception:
        pass
    sb.table("deliverables").delete().eq("id", deliv["id"]).execute()


# --- Spot-checks -------------------------------------------------------------

def test_request_changes_requires_token(ctx):
    r = requests.post(f"{BASE_URL}/api/deliverables/{ctx['deliv_id']}/request-changes",
                      json={"note": "no auth"}, timeout=15)
    assert r.status_code == 401, r.text


def test_request_changes_empty_note_returns_422(ctx):
    r = requests.post(
        f"{BASE_URL}/api/deliverables/{ctx['deliv_id']}/request-changes",
        headers={"Authorization": f"Bearer {ctx['token']}"},
        json={"note": "   "},
        timeout=15,
    )
    assert r.status_code == 422, r.text


def test_request_changes_on_final_delivered_returns_409(ctx):
    r = requests.post(
        f"{BASE_URL}/api/deliverables/{ctx['deliv_id']}/request-changes",
        headers={"Authorization": f"Bearer {ctx['token']}"},
        json={"note": "should be blocked — final delivered"},
        timeout=15,
    )
    assert r.status_code == 409, r.text
