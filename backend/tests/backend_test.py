"""Backend API tests for Flyboy Videography Client Portal (post-schema, seeded).

Covers: health, /api/me for client, admin-guard on /api/admin/clients (403 for client),
and the NEW GDPR erasure flow at POST /api/admin/clients/{id}/erase including:
  - 400 when erasing an admin
  - success anonymization of clients row
  - preservation of bookings/deliverables/invoices
  - login-disabled for erased client
  - 409 on second erase attempt
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

SUPABASE_URL = "https://pnqqmzszasvfnvnnonvd.supabase.co"
SUPABASE_ANON = "sb_publishable_KhBYDE7Rl1aNrMf22lIJ7w_53HJF86f"

DEMO_EMAIL = "demo.client.frameform@gmail.com"
DEMO_PASSWORD = "DemoClient#2026"
ADMIN_EMAIL = "flyboy.admin.demo@gmail.com"
ADMIN_PASSWORD = "AdminStudio#2026"
CLIENT_B_EMAIL = "client.b@seed.flyboytest.com"
CLIENT_B_PASSWORD = "SeedTest#2026!"
CLIENT_A_EMAIL = "client.a@seed.flyboytest.com"
CLIENT_A_PASSWORD = "SeedTest#2026!"


def _login(email, password):
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    return r


@pytest.fixture(scope="session")
def client_token():
    r = _login(DEMO_EMAIL, DEMO_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Demo client login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token():
    r = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


# ---------- Health ----------
def test_health():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["database"] == "supabase"


# ---------- Auth guards ----------
def test_ensure_no_token():
    assert requests.post(f"{API}/clients/ensure", json={}, timeout=10).status_code == 401


def test_admin_clients_no_token():
    assert requests.get(f"{API}/admin/clients", timeout=10).status_code == 401


# ---------- /api/me ----------
def test_me_client_returns_role_client(client_token):
    r = requests.get(f"{API}/me", headers={"Authorization": f"Bearer {client_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"].lower() == DEMO_EMAIL.lower()
    assert data["role"] == "client"


def test_me_admin_returns_role_admin(admin_token):
    r = requests.get(f"{API}/me", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"


# ---------- Admin-only guard ----------
def test_admin_clients_client_token_403(client_token):
    r = requests.get(f"{API}/admin/clients", headers={"Authorization": f"Bearer {client_token}"}, timeout=15)
    assert r.status_code == 403


def test_admin_clients_admin_ok(admin_token):
    r = requests.get(f"{API}/admin/clients", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1
    emails = [c["email"] for c in data]
    # At least the admin themselves should be present
    assert ADMIN_EMAIL in emails


# ---------- GDPR erase flow ----------
def _find_client(admin_token, email):
    r = requests.get(f"{API}/admin/clients", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    for c in r.json():
        if c["email"] == email:
            return c
    return None


def _sb_query(table, select_cols, filters, admin_token):
    """Direct PostgREST GET using admin bearer for verification reads."""
    params = {"select": select_cols, **filters}
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {admin_token}"},
        params=params,
        timeout=15,
    )
    return r


def test_erase_admin_returns_400(admin_token):
    admin = _find_client(admin_token, ADMIN_EMAIL)
    assert admin is not None
    r = requests.post(
        f"{API}/admin/clients/{admin['id']}/erase",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 400


def test_erase_client_b_full_flow(admin_token):
    """Full GDPR erasure of Client B: anonymize + preserve records + block login + idempotency 409."""
    client_b = _find_client(admin_token, CLIENT_B_EMAIL)
    if not client_b:
        pytest.skip("Client B not present — may have been erased in a previous run.")

    cb_id = client_b["id"]

    # Snapshot pre-erase counts for bookings / deliverables / invoices
    def _count(table):
        r = _sb_query(table, "id", {"client_id": f"eq.{cb_id}"}, admin_token)
        assert r.status_code == 200, f"{table} pre-count failed: {r.text}"
        return len(r.json())

    pre_bookings = _count("bookings")
    pre_delivs = _count("deliverables")
    pre_invoices = _count("invoices")

    # (a) Erase
    r = requests.post(
        f"{API}/admin/clients/{cb_id}/erase",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code == 200, f"erase failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["erased"] is True
    assert body["anonymized_email"].startswith("erased-")
    assert body["anonymized_email"].endswith("@anonymized.invalid")

    # Verify clients row anonymized
    updated = _find_client(admin_token, body["anonymized_email"])
    assert updated is not None, "Anonymized client row not found"
    assert updated["full_name"] == "Erased Client"
    assert updated["company"] is None

    # (b) Preserved records
    assert _count("bookings") == pre_bookings, "Bookings were deleted — must be preserved"
    assert _count("deliverables") == pre_delivs, "Deliverables were deleted — must be preserved"
    assert _count("invoices") == pre_invoices, "Invoices were deleted — must be preserved"

    # (c) Login with old creds must fail
    login_r = _login(CLIENT_B_EMAIL, CLIENT_B_PASSWORD)
    assert login_r.status_code != 200, f"Erased user should not be able to log in, got {login_r.status_code}"

    # (e) Second erase returns 409
    r2 = requests.post(
        f"{API}/admin/clients/{cb_id}/erase",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r2.status_code == 409, f"Expected 409 on re-erase, got {r2.status_code} {r2.text}"


# ---------- Client A control (must NOT be affected) ----------
def test_client_a_still_intact_after_b_erase(admin_token):
    a = _find_client(admin_token, CLIENT_A_EMAIL)
    if a is None:
        pytest.skip("Client A missing (control not available)")
    # Login with Client A must still work
    r = _login(CLIENT_A_EMAIL, CLIENT_A_PASSWORD)
    assert r.status_code == 200, f"Client A login broken: {r.status_code} {r.text}"
