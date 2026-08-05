"""Adversarial RLS test: proves Client B cannot read/modify Client A's rows (and vice versa).
All attack requests use the PUBLISHABLE/ANON key + the attacker's own JWT — never service_role."""
import json
import os
import sys
import httpx

URL = "https://pnqqmzszasvfnvnnonvd.supabase.co"
ANON = "sb_publishable_KhBYDE7Rl1aNrMf22lIJ7w_53HJF86f"
SK = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BACKEND = "http://localhost:8001/api"

A_EMAIL, B_EMAIL = "client.a@seed.flyboytest.com", "client.b@seed.flyboytest.com"
PW = "SeedTest#2026!"

svc = {"apikey": SK, "Authorization": f"Bearer {SK}", "Content-Type": "application/json"}


def admin_create_user(email, name):
    r = httpx.post(f"{URL}/auth/v1/admin/users", headers=svc, json={
        "email": email, "password": PW, "email_confirm": True,
        "user_metadata": {"full_name": name}})
    if r.status_code == 422 and "registered" in r.text:
        return None
    r.raise_for_status()
    return r.json()["id"]


def login(email):
    r = httpx.post(f"{URL}/auth/v1/token?grant_type=password",
                   headers={"apikey": ANON, "Content-Type": "application/json"},
                   json={"email": email, "password": PW})
    r.raise_for_status()
    return r.json()["access_token"]


def anon_headers(jwt):
    return {"apikey": ANON, "Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}


def setup_client(email, name):
    admin_create_user(email, name)
    jwt = login(email)
    prof = httpx.post(f"{BACKEND}/clients/ensure", headers={"Authorization": f"Bearer {jwt}"},
                      json={"full_name": name, "company": "SEED_TEST_DATA"}).json()
    cid = prof["id"]
    # booking created AS the client (anon key + own JWT — RLS insert policy)
    b = httpx.post(f"{URL}/rest/v1/bookings", headers={**anon_headers(jwt), "Prefer": "return=representation"},
                   json={"client_id": cid, "title": f"{name} Seed Shoot", "status": "confirmed"}).json()[0]
    # deliverable + invoice are admin-only writes by design → created via service key (setup only)
    d = httpx.post(f"{URL}/rest/v1/deliverables", headers={**svc, "Prefer": "return=representation"},
                   json={"client_id": cid, "booking_id": b["id"], "title": f"{name} Seed Cut v1",
                         "status": "in_review"}).json()[0]
    inv = httpx.post(f"{URL}/rest/v1/invoices", headers={**svc, "Prefer": "return=representation"},
                     json={"client_id": cid, "booking_id": b["id"], "source_type": "booking",
                           "invoice_number": f"INV-SEED-{cid[:8]}", "amount": 100, "status": "sent"}).json()[0]
    return {"name": name, "email": email, "jwt": jwt, "client_id": cid,
            "booking_id": b["id"], "deliverable_id": d["id"], "invoice_id": inv["id"]}


failures = []


def show(label, method, path, status, body, ok, verdict_note):
    result = "PASS" if ok else "*** CRITICAL RLS FAILURE ***"
    if not ok:
        failures.append(label)
    print(f"\n  [{label}]")
    print(f"  REQUEST : {method} {URL}{path}")
    print(f"            headers: apikey=<ANON publishable key>, Authorization=Bearer <attacker's own JWT>")
    print(f"  STATUS  : {status}")
    print(f"  BODY    : {body if len(body) <= 300 else body[:300] + '…'}")
    print(f"  RESULT  : {result} — {verdict_note}")


def attack(attacker, victim):
    h = anon_headers(attacker["jwt"])
    hp = {**h, "Prefer": "return=representation"}
    print(f"\n{'='*74}\nATTACKER: {attacker['name']} ({attacker['email']})  →  "
          f"TARGET: {victim['name']}'s rows\n{'='*74}")

    for label, table, rid in [("a. SELECT victim's booking by ID", "bookings", victim["booking_id"]),
                              ("b. SELECT victim's deliverable by ID", "deliverables", victim["deliverable_id"]),
                              ("c. SELECT victim's invoice by ID", "invoices", victim["invoice_id"])]:
        path = f"/rest/v1/{table}?id=eq.{rid}&select=*"
        r = httpx.get(URL + path, headers=h)
        rows = r.json() if r.status_code == 200 else []
        show(label, "GET", path, r.status_code, r.text,
             r.status_code == 200 and rows == [],
             "zero rows returned" if rows == [] else f"{len(rows)} of victim's rows LEAKED")

    for table in ["bookings", "deliverables", "invoices"]:
        path = f"/rest/v1/{table}?select=id,client_id"
        r = httpx.get(URL + path, headers=h)
        rows = r.json()
        leaked = [x for x in rows if x["client_id"] == victim["client_id"]]
        own_only = all(x["client_id"] == attacker["client_id"] for x in rows)
        show(f"d. unfiltered SELECT * from {table}", "GET", path, r.status_code, r.text,
             not leaked and own_only,
             f"{len(rows)} rows, all client_id == attacker's own; victim absent" if not leaked
             else f"victim rows present: {leaked}")

    path = f"/rest/v1/bookings?id=eq.{victim['booking_id']}"
    r = httpx.patch(URL + path, headers=hp, json={"title": "HACKED BY OTHER CLIENT"})
    check = httpx.get(URL + f"/rest/v1/bookings?id=eq.{victim['booking_id']}&select=title", headers=svc).json()
    unchanged = check and check[0]["title"] != "HACKED BY OTHER CLIENT"
    show("e1. UPDATE victim's booking", "PATCH", path, r.status_code, r.text,
         r.json() == [] and unchanged,
         f"0 rows updated; service-role check confirms title still '{check[0]['title']}'" if unchanged
         else "VICTIM ROW WAS MODIFIED")

    r = httpx.delete(URL + path, headers=hp)
    check = httpx.get(URL + f"/rest/v1/bookings?id=eq.{victim['booking_id']}&select=id", headers=svc).json()
    survives = len(check) == 1
    show("e2. DELETE victim's booking", "DELETE", path, r.status_code, r.text,
         r.json() == [] and survives,
         "0 rows deleted; service-role check confirms row still exists" if survives
         else "VICTIM ROW WAS DELETED")


print("SETUP — creating throwaway seed clients (marked company='SEED_TEST_DATA';")
print("note: schema has no is_seed_data column — it was not in the user-reviewed SQL)")
A = setup_client(A_EMAIL, "Client A")
B = setup_client(B_EMAIL, "Client B")
for c in (A, B):
    print(f"\n  {c['name']}: email={c['email']}\n    client_id      = {c['client_id']}"
          f"\n    booking_id     = {c['booking_id']}\n    deliverable_id = {c['deliverable_id']}"
          f"\n    invoice_id     = {c['invoice_id']}")

attack(B, A)
attack(A, B)

print(f"\n{'='*74}")
if failures:
    print(f"VERDICT: {len(failures)} CRITICAL RLS FAILURE(S): {failures}")
    sys.exit(1)
print("VERDICT: ALL 16 ADVERSARIAL TESTS PASSED — RLS isolates clients in both directions.")
