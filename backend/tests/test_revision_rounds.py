"""Backend spot-checks for revision rounds / request-changes flow."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://db-bridge-5.preview.emergentagent.com").rstrip("/")
SUPABASE_URL = "https://pnqqmzszasvfnvnnonvd.supabase.co"
ANON_KEY = "sb_publishable_KhBYDE7Rl1aNrMf22lIJ7w_53HJF86f"
SERVICE_KEY = "REDACTED_FROM_HISTORY"

CLIENT_EMAIL = "demo.client.frameform@gmail.com"
CLIENT_PASS = "DemoClient#2026"


def _login(email, password):
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def client_token():
    return _login(CLIENT_EMAIL, CLIENT_PASS)


@pytest.fixture(scope="module")
def deliverables(client_token):
    # Read deliverables via supabase service key (bypass RLS to be safe)
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/deliverables?select=*",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _find(delivs, title_substr):
    for d in delivs:
        if title_substr.lower() in (d.get("title") or "").lower():
            return d
    return None


# --- Spot-checks -------------------------------------------------------------

def test_request_changes_requires_token(deliverables):
    d = _find(deliverables, "Q3 Teaser") or deliverables[0]
    r = requests.post(f"{BASE_URL}/api/deliverables/{d['id']}/request-changes",
                      json={"note": "no auth"}, timeout=15)
    assert r.status_code == 401, r.text


def test_request_changes_empty_note_returns_422(client_token, deliverables):
    d = _find(deliverables, "Q3 Teaser")
    assert d, "Q3 Teaser deliverable missing from seed"
    r = requests.post(
        f"{BASE_URL}/api/deliverables/{d['id']}/request-changes",
        headers={"Authorization": f"Bearer {client_token}"},
        json={"note": "   "},
        timeout=15,
    )
    assert r.status_code == 422, r.text


def test_request_changes_on_final_delivered_returns_409(client_token, deliverables):
    d = _find(deliverables, "May Recap")
    assert d, "May Recap deliverable missing"
    assert d["status"] == "final_delivered", f"unexpected status {d['status']}"
    r = requests.post(
        f"{BASE_URL}/api/deliverables/{d['id']}/request-changes",
        headers={"Authorization": f"Bearer {client_token}"},
        json={"note": "should be blocked"},
        timeout=15,
    )
    assert r.status_code == 409, r.text


def test_seed_state(deliverables):
    """Sanity: seed data expected state."""
    q3 = _find(deliverables, "Q3 Teaser")
    june = _find(deliverables, "June Social")
    may = _find(deliverables, "May Recap")
    assert q3 and june and may, "missing seeded deliverables"
    # Q3 Teaser starts fresh in_review 0/2
    print("Q3 Teaser:", q3["status"], q3.get("revision_rounds_used"), "/", q3.get("included_revision_rounds"))
    print("June Social:", june["status"], june.get("revision_rounds_used"), "/", june.get("included_revision_rounds"))
    print("May Recap:", may["status"], may.get("revision_rounds_used"), "/", may.get("included_revision_rounds"))
    assert may["status"] == "final_delivered"
