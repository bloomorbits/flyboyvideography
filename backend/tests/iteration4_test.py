"""Iteration 4 tests: purge-seed-data guard + erasure audit backfilled entry.
CRITICAL: Never send confirmation='PURGE' — it would destroy fresh demo data.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
# Fallback: read frontend/.env
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

SUPABASE_URL = None
SUPABASE_ANON = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_SUPABASE_URL="):
            SUPABASE_URL = line.split("=", 1)[1].strip()
        elif line.startswith("REACT_APP_SUPABASE_ANON_KEY="):
            SUPABASE_ANON = line.split("=", 1)[1].strip()

ADMIN_EMAIL = "flyboy.admin.demo@gmail.com"
ADMIN_PASS = "AdminStudio#2026"
CLIENT_EMAIL = "demo.client.frameform@gmail.com"
CLIENT_PASS = "DemoClient#2026"


def _login(email, password):
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def client_token():
    return _login(CLIENT_EMAIL, CLIENT_PASS)


# ---- Purge guard ----
class TestPurgeGuard:
    def test_no_token(self):
        r = requests.post(f"{BASE_URL}/api/admin/purge-seed-data", json={"confirmation": "PURGE"})
        assert r.status_code == 401

    def test_client_token_forbidden(self, client_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/purge-seed-data",
            json={"confirmation": "PURGE"},
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert r.status_code == 403

    def test_admin_lowercase_rejected(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/purge-seed-data",
            json={"confirmation": "purge"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_admin_wrong_text_rejected(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/purge-seed-data",
            json={"confirmation": "nope"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_admin_missing_field_rejected(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/purge-seed-data",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422


# ---- Audit log ----
class TestAuditLog:
    def test_audit_has_backfilled_entry(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/erasure-audit",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) == 3, f"expected 3 audit entries, got {len(rows)}: {rows}"

        backfilled = [row for row in rows if row.get("backfilled") is True]
        assert len(backfilled) == 1, f"expected exactly 1 backfilled row, got {len(backfilled)}"
        b = backfilled[0]
        assert b.get("anonymized_email") == "erased-576baf05@anonymized.invalid", b
        assert b.get("note") is not None
        assert "BACKFILLED" in b["note"].upper()


# ---- Regression: is_seed_data tagging via service key ----
class TestSeedTagging:
    def _service(self):
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                    return line.split("=", 1)[1].strip()
        pytest.skip("no service key")

    def _rest(self, path, key):
        return requests.get(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
        )

    def test_no_untagged_seed_rows(self):
        key = self._service()
        # get demo client id
        c = self._rest(f"clients?email=eq.{CLIENT_EMAIL}&select=id", key).json()
        assert c, "demo client not found"
        cid = c[0]["id"]
        for tbl in ["bookings", "deliverables", "invoices", "retainer_subscriptions"]:
            r = self._rest(f"{tbl}?client_id=eq.{cid}&is_seed_data=eq.false&select=id", key)
            assert r.status_code == 200
            assert r.json() == [], f"{tbl} has untagged rows for demo client: {r.json()}"


# ---- Regression: demo client data intact (via PostgREST + RLS) ----
class TestDemoClientDashboard:
    def _get(self, table, token):
        return requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=*",
            headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {token}"},
            timeout=15,
        )

    def test_bookings_present(self, client_token):
        r = self._get("bookings", client_token)
        assert r.status_code == 200, r.text
        assert len(r.json()) >= 2

    def test_deliverables_present(self, client_token):
        r = self._get("deliverables", client_token)
        assert r.status_code == 200, r.text
        assert len(r.json()) >= 3

    def test_invoices_present(self, client_token):
        r = self._get("invoices", client_token)
        assert r.status_code == 200, r.text
        assert len(r.json()) >= 2

    def test_retainer_present(self, client_token):
        r = self._get("retainer_subscriptions", client_token)
        assert r.status_code == 200, r.text
        assert len(r.json()) >= 1
