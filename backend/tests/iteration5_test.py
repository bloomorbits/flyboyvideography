"""Iteration 5 tests: Approve Cut, Profile RLS, Overdue Invoice Sweep."""
import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SUPABASE_URL = None
SUPABASE_ANON = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL=") and not BASE_URL:
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
        elif line.startswith("REACT_APP_SUPABASE_URL="):
            SUPABASE_URL = line.split("=", 1)[1].strip()
        elif line.startswith("REACT_APP_SUPABASE_ANON_KEY="):
            SUPABASE_ANON = line.split("=", 1)[1].strip()

SERVICE_KEY = None
with open("/app/backend/.env") as f:
    for line in f:
        if line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
            SERVICE_KEY = line.split("=", 1)[1].strip()

ADMIN_EMAIL = "flyboy.admin.demo@gmail.com"
ADMIN_PASS = "AdminStudio#2026"
CLIENT_EMAIL = "demo.client.frameform@gmail.com"
CLIENT_PASS = "DemoClient#2026"


def _login(email, password):
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON, "Content-Type": "application/json"},
        json={"email": email, "password": password}, timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def client_token():
    return _login(CLIENT_EMAIL, CLIENT_PASS)


@pytest.fixture(scope="module")
def client_id(client_token):
    r = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {client_token}"})
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(scope="module")
def throwaway_user():
    """Create a throwaway *@seed.flyboytest.com user via GoTrue admin API."""
    email = f"throw-{uuid.uuid4().hex[:8]}@seed.flyboytest.com"
    password = "SeedTest#2026!"
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"},
        json={"email": email, "password": password, "email_confirm": True,
              "user_metadata": {"full_name": "Throwaway Seed", "is_seed_data": True}},
        timeout=15,
    )
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    user_id = r.json()["id"]
    # login
    tok = _login(email, password)
    # ensure client row (tagged is_seed)
    er = requests.post(f"{BASE_URL}/api/clients/ensure",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"full_name": "Throwaway Seed", "company": "SeedCo"})
    assert er.status_code == 200, er.text
    client_row_id = er.json()["id"]
    # mark is_seed_data via service key
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_row_id}",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        json={"is_seed_data": True}, timeout=10,
    )
    yield {"user_id": user_id, "token": tok, "client_row_id": client_row_id, "email": email}
    # cleanup: delete client row + auth user
    requests.delete(f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_row_id}",
                    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"})
    requests.delete(f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
                    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"})


def _find_deliverable(client_token, title_contains):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/deliverables?select=*",
        headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}"}, timeout=10,
    )
    assert r.status_code == 200, r.text
    for d in r.json():
        if title_contains.lower() in d["title"].lower():
            return d
    return None


# ================= APPROVE CUT =================

class TestApproveCut:
    def test_approve_401_no_token(self):
        # pick any deliverable id — even a fake one; auth must reject first
        r = requests.post(f"{BASE_URL}/api/deliverables/00000000-0000-0000-0000-000000000000/approve")
        assert r.status_code in (401, 403), r.text

    def test_approve_409_already_approved(self, client_token):
        """Q3 Teaser — Cut v2 is already approved per main agent context."""
        d = _find_deliverable(client_token, "Q3 Teaser")
        assert d is not None
        assert d["status"] == "approved", f"expected approved, got {d['status']}"
        r = requests.post(f"{BASE_URL}/api/deliverables/{d['id']}/approve",
                          headers={"Authorization": f"Bearer {client_token}"})
        assert r.status_code == 409, r.text
        assert "approved" in r.json()["detail"].lower()

    def test_approve_409_final_delivered(self, client_token):
        d = _find_deliverable(client_token, "May Recap Reel")
        assert d is not None
        assert d["status"] == "final_delivered"
        r = requests.post(f"{BASE_URL}/api/deliverables/{d['id']}/approve",
                          headers={"Authorization": f"Bearer {client_token}"})
        assert r.status_code == 409, r.text

    def test_approve_403_not_your_deliverable(self, client_token, throwaway_user):
        """Use throwaway user's token to approve demo client's deliverable → 403."""
        d = _find_deliverable(client_token, "June Social Edit")
        assert d is not None, "June Social Edit #3 must exist for UI test"
        # DO NOT approve — use throwaway token so demo client's deliverable stays revisions_requested for UI test
        r = requests.post(f"{BASE_URL}/api/deliverables/{d['id']}/approve",
                          headers={"Authorization": f"Bearer {throwaway_user['token']}"})
        assert r.status_code == 403, r.text
        assert "not your" in r.json()["detail"].lower()


# ================= PROFILE RLS =================

class TestProfileRLS:
    def test_client_cannot_escalate_role(self, client_token, client_id):
        """Direct PATCH clients with role=admin via anon+client JWT must fail (RLS 42501 or filtered out)."""
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}",
            headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}",
                     "Content-Type": "application/json", "Prefer": "return=representation"},
            json={"role": "admin"}, timeout=10,
        )
        # Either RLS blocks (403/401/42501) or returns empty array (silent RLS filter)
        # We must verify the actual persisted role is still 'client'
        me = requests.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {client_token}"}).json()
        assert me["role"] == "client", f"ROLE ESCALATED! got {me['role']}"
        # Also verify server error signal
        if r.status_code == 200:
            # PostgREST with RLS may return empty list
            assert r.json() == [], f"PATCH succeeded silently! {r.text}"
        else:
            assert r.status_code in (401, 403, 400, 404), f"unexpected status {r.status_code}: {r.text}"

    def test_client_can_update_own_phone(self, client_token, client_id):
        original = requests.get(f"{BASE_URL}/api/me",
                                headers={"Authorization": f"Bearer {client_token}"}).json()
        original_phone = original.get("phone")
        new_phone = "+44 7700 900999"
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}",
            headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}",
                     "Content-Type": "application/json", "Prefer": "return=representation"},
            json={"phone": new_phone}, timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json()[0]["phone"] == new_phone
        # revert
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/clients?id=eq.{client_id}",
            headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}",
                     "Content-Type": "application/json"},
            json={"phone": original_phone}, timeout=10,
        )


# ================= OVERDUE SWEEP =================

class TestOverdueSweep:
    def test_existing_overdue_flag(self, client_token):
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/invoices?select=*&invoice_number=eq.INV-B-OVERDUE-8922",
            headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}"}, timeout=10,
        )
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1, f"expected 1 row, got {rows}"
        assert rows[0]["status"] == "overdue"

    def test_sweep_flips_past_due_sent_to_overdue(self, admin_token, client_token, client_id):
        # Find a booking for the demo client to attach invoice
        bookings = requests.get(
            f"{SUPABASE_URL}/rest/v1/bookings?select=id&client_id=eq.{client_id}&limit=1",
            headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}"}).json()
        assert bookings
        booking_id = bookings[0]["id"]

        past_due_num = f"INV-TEST-PAST-{uuid.uuid4().hex[:6].upper()}"
        future_due_num = f"INV-TEST-FUTURE-{uuid.uuid4().hex[:6].upper()}"

        headers_admin = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        past = requests.post(f"{BASE_URL}/api/admin/invoices", headers=headers_admin, json={
            "client_id": client_id, "source_type": "booking", "booking_id": booking_id,
            "invoice_number": past_due_num, "amount": 100, "status": "sent",
            "due_on": str(date.today() - timedelta(days=5)),
        })
        assert past.status_code == 200, past.text
        past_id = past.json()["id"]

        future = requests.post(f"{BASE_URL}/api/admin/invoices", headers=headers_admin, json={
            "client_id": client_id, "source_type": "booking", "booking_id": booking_id,
            "invoice_number": future_due_num, "amount": 200, "status": "sent",
            "due_on": str(date.today() + timedelta(days=30)),
        })
        assert future.status_code == 200, future.text
        future_id = future.json()["id"]

        try:
            # Trigger sweep via /api/clients/ensure
            e = requests.post(f"{BASE_URL}/api/clients/ensure",
                              headers={"Authorization": f"Bearer {client_token}"}, json={})
            assert e.status_code == 200

            past_after = requests.get(
                f"{SUPABASE_URL}/rest/v1/invoices?select=status&id=eq.{past_id}",
                headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}"}).json()
            assert past_after[0]["status"] == "overdue", past_after

            future_after = requests.get(
                f"{SUPABASE_URL}/rest/v1/invoices?select=status&id=eq.{future_id}",
                headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}"}).json()
            assert future_after[0]["status"] == "sent", future_after
        finally:
            # cleanup
            for iid in (past_id, future_id):
                requests.delete(f"{SUPABASE_URL}/rest/v1/invoices?id=eq.{iid}",
                                headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"})

    def test_paid_invoice_untouched(self, client_token):
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/invoices?select=*&invoice_number=eq.INV-R-3518",
            headers={"apikey": SUPABASE_ANON, "Authorization": f"Bearer {client_token}"}).json()
        assert r and r[0]["status"] == "paid"
