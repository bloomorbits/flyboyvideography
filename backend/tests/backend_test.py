"""Backend API tests for Flyboy Videography Client Portal.
Supabase tables DO NOT EXIST yet (user must run supabase_schema.sql),
so schema-dependent endpoints should return 503 with a SCHEMA_HINT message.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://1365ac7b-1f03-493f-9c4b-0168958ed9ef.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPABASE_URL = "https://pnqqmzszasvfnvnnonvd.supabase.co"
SUPABASE_ANON = "sb_publishable_KhBYDE7Rl1aNrMf22lIJ7w_53HJF86f"
DEMO_EMAIL = "demo.client.frameform@gmail.com"
DEMO_PASSWORD = "DemoClient#2026"


@pytest.fixture(scope="session")
def client_token():
    """Log in demo client via Supabase auth and return access token."""
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON, "Content-Type": "application/json"},
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Supabase login failed: {r.status_code} {r.text}")
    return r.json().get("access_token")


# ---------- Health ----------
def test_health():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["database"] == "supabase"


# ---------- Auth guard on /api/clients/ensure ----------
def test_ensure_no_token():
    r = requests.post(f"{API}/clients/ensure", json={}, timeout=10)
    assert r.status_code == 401


def test_ensure_garbage_token():
    r = requests.post(
        f"{API}/clients/ensure",
        json={},
        headers={"Authorization": "Bearer garbage.token.here"},
        timeout=10,
    )
    assert r.status_code == 401


def test_ensure_valid_token_returns_503_schema_hint(client_token):
    r = requests.post(
        f"{API}/clients/ensure",
        json={},
        headers={"Authorization": f"Bearer {client_token}"},
        timeout=15,
    )
    assert r.status_code == 503, f"Expected 503, got {r.status_code}: {r.text}"
    detail = (r.json().get("detail") or "").lower()
    assert "supabase_schema.sql" in detail or "schema" in detail


# ---------- Admin guard ----------
def test_admin_clients_no_token():
    r = requests.get(f"{API}/admin/clients", timeout=10)
    assert r.status_code == 401


def test_admin_clients_garbage_token():
    r = requests.get(
        f"{API}/admin/clients",
        headers={"Authorization": "Bearer garbage"},
        timeout=10,
    )
    assert r.status_code == 401


# ---------- Static schema.sql verification ----------
def test_schema_review_update_uses_author_user_id():
    with open("/app/supabase_schema.sql") as f:
        sql = f.read()
    # Find review_update policy block
    idx = sql.find("create policy review_update")
    assert idx != -1, "review_update policy missing"
    block = sql[idx: idx + 400]
    assert "author_user_id = auth.uid()" in block
    # Ensure it's NOT still keyed on client_id in the update USING/WITH CHECK
    assert "client_id = public.current_client_id()" not in block


def test_schema_invoices_currency_gbp():
    with open("/app/supabase_schema.sql") as f:
        sql = f.read()
    assert "currency text not null default 'GBP'" in sql


def test_schema_invoices_client_id_restrict():
    with open("/app/supabase_schema.sql") as f:
        sql = f.read()
    # Look for invoices.client_id ON DELETE RESTRICT
    idx = sql.find("create table if not exists public.invoices")
    assert idx != -1
    block = sql[idx: idx + 1500]
    assert "on delete restrict" in block.lower()
