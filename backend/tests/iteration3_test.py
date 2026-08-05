"""Iteration 3 tests: Erasure audit log endpoint + RLS on erasure_audit_log +
end-to-end GDPR erase of a fresh throwaway client D + seed is_seed_data tagging.
"""
import os
import time
import requests
import pytest

BASE_URL = "https://db-bridge-5.preview.emergentagent.com"
API = f"{BASE_URL}/api"

SUPABASE_URL = "https://pnqqmzszasvfnvnnonvd.supabase.co"
SUPABASE_ANON = "sb_publishable_KhBYDE7Rl1aNrMf22lIJ7w_53HJF86f"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "REDACTED_FROM_HISTORY"

ADMIN_EMAIL = "flyboy.admin.demo@gmail.com"
ADMIN_PASSWORD = "AdminStudio#2026"
CLIENT_EMAIL = "demo.client.frameform@gmail.com"
CLIENT_PASSWORD = "DemoClient#2026"
KNOWN_ERASED_CID = "1c1be3fb-c6b8-48e3-a79a-1a0d9bd479f8"

CLIENT_D_EMAIL = "client.d@seed.flyboytest.com"
CLIENT_D_PASSWORD = "SeedTest#2026!"


def _login(email, password):
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    return r


@pytest.fixture(scope="module")
def admin_token():
    r = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def client_token():
    r = _login(CLIENT_EMAIL, CLIENT_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"client login failed {r.status_code}")
    return r.json()["access_token"]


# ---------- /api/admin/erasure-audit endpoint guards ----------
def test_erasure_audit_admin_returns_list_with_known_entry(admin_token):
    r = requests.get(f"{API}/admin/erasure-audit", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    match = [e for e in data if e.get("erased_client_id") == KNOWN_ERASED_CID]
    assert match, f"Expected audit entry for {KNOWN_ERASED_CID}"
    e = match[0]
    assert e["performed_by_email"] == ADMIN_EMAIL
    assert e["bookings_preserved"] >= 1
    assert e["invoices_preserved"] >= 1
    assert e["anonymized_email"].endswith("@anonymized.invalid")


def test_erasure_audit_client_token_403(client_token):
    r = requests.get(f"{API}/admin/erasure-audit", headers={"Authorization": f"Bearer {client_token}"}, timeout=15)
    assert r.status_code == 403


def test_erasure_audit_no_token_401():
    assert requests.get(f"{API}/admin/erasure-audit", timeout=10).status_code == 401


# ---------- RLS on erasure_audit_log (direct PostgREST) ----------
def _rest(path, method="GET", token=None, apikey=SUPABASE_ANON, json_body=None, params=None, extra_headers=None):
    headers = {"apikey": apikey}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    return requests.request(method, f"{SUPABASE_URL}/rest/v1/{path}", headers=headers, json=json_body, params=params, timeout=15)


def test_rls_client_cannot_read_audit(client_token):
    r = _rest("erasure_audit_log", "GET", token=client_token, params={"select": "id"})
    # Either empty list or forbidden — spec says returns []
    assert r.status_code == 200, r.text
    assert r.json() == [], f"Client should not see audit rows, got {r.json()}"


def test_rls_admin_can_read_audit_via_rest(admin_token):
    r = _rest("erasure_audit_log", "GET", token=admin_token, params={"select": "id,erased_client_id"})
    assert r.status_code == 200, r.text
    assert len(r.json()) >= 1


def test_rls_client_cannot_insert_audit(client_token):
    # Attempt to write a bogus audit row as a client — RLS must reject
    r = _rest(
        "erasure_audit_log",
        "POST",
        token=client_token,
        json_body={
            "erased_client_id": KNOWN_ERASED_CID,
            "erased_client_previous_role": "client",
            "anonymized_email": "hax@anonymized.invalid",
            "performed_by_client_id": KNOWN_ERASED_CID,
            "performed_by_email": "hax@evil.test",
            "bookings_preserved": 0,
            "deliverables_preserved": 0,
            "invoices_preserved": 0,
        },
        extra_headers={"Prefer": "return=representation"},
    )
    assert r.status_code in (401, 403), f"Expected RLS block, got {r.status_code} {r.text}"


# ---------- Client D end-to-end erase + audit ----------
def _admin_sb_headers():
    return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}


def _create_or_get_client_d_user():
    # Try to create via GoTrue admin API
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        headers=_admin_sb_headers(),
        json={"email": CLIENT_D_EMAIL, "password": CLIENT_D_PASSWORD, "email_confirm": True},
        timeout=20,
    )
    if r.status_code in (200, 201):
        return r.json()["id"]
    # If already exists, look them up
    if r.status_code in (409, 422, 400) or "already" in r.text.lower():
        lu = requests.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=_admin_sb_headers(),
            params={"filter": f"email.eq.{CLIENT_D_EMAIL}"},
            timeout=15,
        )
        if lu.status_code == 200:
            users = lu.json().get("users", [])
            if users:
                return users[0]["id"]
    pytest.skip(f"Cannot create/find client D auth user: {r.status_code} {r.text}")


@pytest.fixture(scope="module")
def client_d_state(admin_token):
    """Create throwaway client D, ensure profile, tag is_seed_data=true, give one booking."""
    user_id = _create_or_get_client_d_user()

    # Login as client D to obtain JWT
    lr = _login(CLIENT_D_EMAIL, CLIENT_D_PASSWORD)
    if lr.status_code != 200:
        # user may have been erased; try rotate password via admin
        requests.put(
            f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers=_admin_sb_headers(),
            json={"password": CLIENT_D_PASSWORD, "email": CLIENT_D_EMAIL, "email_confirm": True, "ban_duration": "none"},
            timeout=15,
        )
        lr = _login(CLIENT_D_EMAIL, CLIENT_D_PASSWORD)
    if lr.status_code != 200:
        pytest.skip(f"cannot login client D: {lr.status_code} {lr.text}")
    d_token = lr.json()["access_token"]

    # Ensure profile via backend
    er = requests.post(
        f"{API}/clients/ensure",
        headers={"Authorization": f"Bearer {d_token}"},
        json={"full_name": "Client D Seed", "company": "SeedCo"},
        timeout=20,
    )
    assert er.status_code == 200, er.text
    client_row = er.json()
    cid = client_row["id"]

    # Tag clients row is_seed_data=true via service key
    upd = _rest(
        "clients",
        "PATCH",
        apikey=SERVICE_KEY,
        token=SERVICE_KEY,
        json_body={"is_seed_data": True},
        params={"id": f"eq.{cid}"},
        extra_headers={"Prefer": "return=representation"},
    )
    assert upd.status_code in (200, 204), f"tag failed: {upd.status_code} {upd.text}"

    # Insert one booking (is_seed_data=true) via service key
    br = _rest(
        "bookings",
        "POST",
        apikey=SERVICE_KEY,
        token=SERVICE_KEY,
        json_body={
            "client_id": cid,
            "title": "TEST_ClientD Seed Booking",
            "shoot_type": "Test",
            "status": "confirmed",
            "is_seed_data": True,
        },
        extra_headers={"Prefer": "return=representation"},
    )
    assert br.status_code in (200, 201), f"booking insert failed: {br.status_code} {br.text}"
    booking = br.json()[0] if isinstance(br.json(), list) else br.json()
    return {"user_id": user_id, "client_id": cid, "booking_id": booking["id"], "token": d_token}


def test_erase_client_d_full_flow(admin_token, client_d_state):
    cid = client_d_state["client_id"]
    booking_id = client_d_state["booking_id"]

    # Get pre-audit count
    pre = requests.get(f"{API}/admin/erasure-audit", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15).json()
    pre_count = len(pre)

    r = requests.post(
        f"{API}/admin/clients/{cid}/erase",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["erased"] is True
    assert body["audit_logged"] is True
    assert body["preserved"]["bookings"] >= 1

    # Audit list has NEW entry for client D
    time.sleep(0.5)
    post = requests.get(f"{API}/admin/erasure-audit", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15).json()
    assert len(post) == pre_count + 1
    new_entries = [e for e in post if e["erased_client_id"] == cid]
    assert new_entries, "audit entry for client D missing"
    assert new_entries[0]["performed_by_email"] == ADMIN_EMAIL

    # Client D login fails
    lr = _login(CLIENT_D_EMAIL, CLIENT_D_PASSWORD)
    assert lr.status_code != 200

    # Booking still exists
    bq = _rest("bookings", "GET", apikey=SERVICE_KEY, token=SERVICE_KEY, params={"id": f"eq.{booking_id}", "select": "id,is_seed_data"})
    assert bq.status_code == 200
    rows = bq.json()
    assert len(rows) == 1
    assert rows[0]["is_seed_data"] is True


def test_erase_client_d_idempotent_409(admin_token, client_d_state):
    cid = client_d_state["client_id"]
    r = requests.post(f"{API}/admin/clients/{cid}/erase", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 409, f"expected 409, got {r.status_code} {r.text}"


def test_erase_admin_self_returns_400(admin_token):
    # Find admin id
    r = requests.get(f"{API}/admin/clients", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    admin_row = next(c for c in r.json() if c["email"] == ADMIN_EMAIL)
    r2 = requests.post(f"{API}/admin/clients/{admin_row['id']}/erase", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r2.status_code == 400


# ---------- Seed is_seed_data verification ----------
def test_seeded_rows_have_is_seed_data_true():
    """Verify seed_demo code path tags rows is_seed_data=true. Check demo client's existing seeded rows via service key."""
    # Query bookings for the demo client — the second booking in seed_demo has is_seed_data=True
    # Look up demo client id
    lr = _login(CLIENT_EMAIL, CLIENT_PASSWORD)
    assert lr.status_code == 200
    tok = lr.json()["access_token"]
    me = requests.get(f"{API}/me", headers={"Authorization": f"Bearer {tok}"}, timeout=15).json()
    cid = me["id"]
    r = _rest("bookings", "GET", apikey=SERVICE_KEY, token=SERVICE_KEY,
              params={"client_id": f"eq.{cid}", "select": "id,title,is_seed_data"})
    assert r.status_code == 200
    seeded_bookings = [b for b in r.json() if b.get("is_seed_data") is True]
    assert len(seeded_bookings) >= 1, "expected at least one is_seed_data=true booking for demo client"
