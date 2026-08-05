import os
import random
import secrets
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import create_client

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]

sb = create_client(SUPABASE_URL, SERVICE_KEY)

app = FastAPI(title="Flyboy Videography Portal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer(auto_error=False)

SCHEMA_HINT = "Supabase tables not found. Run /app/supabase_schema.sql in your Supabase SQL Editor."


def is_schema_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "schema cache" in msg or "does not exist" in msg or "pgrst205" in msg


def get_auth_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, "Bearer token required")
    try:
        res = sb.auth.get_user(credentials.credentials)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if not res or not res.user:
        raise HTTPException(401, "Invalid or expired token")
    return res.user


def get_client_row(user):
    try:
        r = sb.table("clients").select("*").eq("user_id", user.id).execute()
    except Exception as e:
        if is_schema_error(e):
            raise HTTPException(503, SCHEMA_HINT)
        raise HTTPException(500, str(e))
    return r.data[0] if r.data else None


def require_admin(user=Depends(get_auth_user)):
    client = get_client_row(user)
    if not client or client["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return client


class EnsureBody(BaseModel):
    full_name: Optional[str] = None
    company: Optional[str] = None


@app.get("/api/health")
def health():
    return {"status": "ok", "database": "supabase"}


@app.post("/api/clients/ensure")
def ensure_client(body: EnsureBody, user=Depends(get_auth_user)):
    client = get_client_row(user)
    role = "admin" if (user.email or "").lower() in ADMIN_EMAILS else "client"
    if client:
        updates = {}
        if body.full_name and not client.get("full_name"):
            updates["full_name"] = body.full_name
        if body.company and not client.get("company"):
            updates["company"] = body.company
        if role == "admin" and client["role"] != "admin":
            updates["role"] = "admin"
        if updates:
            client = sb.table("clients").update(updates).eq("id", client["id"]).execute().data[0]
        return client
    meta = user.user_metadata or {}
    row = {
        "user_id": user.id,
        "email": user.email,
        "full_name": body.full_name or meta.get("full_name"),
        "company": body.company or meta.get("company"),
        "role": role,
    }
    try:
        return sb.table("clients").insert(row).execute().data[0]
    except Exception as e:
        if is_schema_error(e):
            raise HTTPException(503, SCHEMA_HINT)
        raise HTTPException(500, str(e))


@app.get("/api/me")
def me(user=Depends(get_auth_user)):
    client = get_client_row(user)
    if not client:
        raise HTTPException(404, "Client profile not found")
    return client


@app.post("/api/demo/seed")
def seed_demo(user=Depends(get_auth_user)):
    client = get_client_row(user)
    if not client:
        raise HTTPException(404, "Client profile not found")
    cid = client["id"]
    existing = sb.table("bookings").select("id").eq("client_id", cid).limit(1).execute()
    if existing.data:
        raise HTTPException(409, "Demo data already exists for this client")

    today = date.today()
    suffix = random.randint(1000, 9999)
    bookings = sb.table("bookings").insert([
        {"client_id": cid, "title": "Brand Film — HQ Launch", "shoot_type": "Brand Film",
         "shoot_date": str(today + timedelta(days=12)), "location": "Downtown Studio A",
         "status": "confirmed", "budget": 8500, "notes": "Two-day shoot, drone unit on day 2."},
        {"client_id": cid, "title": "Product Teaser — Q3 Drop", "shoot_type": "Product",
         "shoot_date": str(today - timedelta(days=20)), "location": "White Cyc Stage",
         "status": "in_post", "budget": 4200, "notes": "Macro pass complete, awaiting color.", "is_seed_data": True},
    ]).execute().data

    sub = sb.table("retainer_subscriptions").insert({
        "client_id": cid, "package_name": "Growth Retainer", "monthly_price": 3500,
        "videos_per_month": 4, "status": "active",
        "started_on": str(today - timedelta(days=90)), "renews_on": str(today + timedelta(days=8)),
        "is_seed_data": True,
    }).execute().data[0]

    delivs = sb.table("deliverables").insert([
        {"client_id": cid, "booking_id": bookings[1]["id"], "title": "Q3 Teaser — Cut v2",
         "version": 2, "status": "in_review",
         "video_url": "https://player.vimeo.com/video/76979871", "notes": "Color pass applied.", "is_seed_data": True},
        {"client_id": cid, "subscription_id": sub["id"], "title": "June Social Edit #3",
         "version": 1, "status": "revisions_requested",
         "video_url": "https://player.vimeo.com/video/76979871", "notes": "Vertical crop 9:16.", "is_seed_data": True},
        {"client_id": cid, "subscription_id": sub["id"], "title": "May Recap Reel",
         "version": 3, "status": "final_delivered",
         "video_url": "https://player.vimeo.com/video/76979871",
         "final_file_url": "https://example.com/final/may-recap-4k.mp4", "is_seed_data": True},
    ]).execute().data

    sb.table("review_threads").insert([
        {"deliverable_id": delivs[0]["id"], "client_id": cid, "author_user_id": user.id,
         "author_name": client.get("full_name") or client["email"], "author_role": client["role"],
         "version": 2, "timestamp_seconds": 14.5,
         "comment": "Logo lands a beat too early — push it back ~10 frames.", "resolved": False, "is_seed_data": True},
        {"deliverable_id": delivs[0]["id"], "client_id": cid, "author_user_id": user.id,
         "author_name": client.get("full_name") or client["email"], "author_role": client["role"],
         "version": 2, "timestamp_seconds": 42.0,
         "comment": "Love this transition. Keep exactly as is.", "resolved": True, "is_seed_data": True},
    ]).execute()

    sb.table("invoices").insert([
        {"client_id": cid, "booking_id": bookings[0]["id"], "source_type": "booking",
         "invoice_number": f"INV-B-{suffix}", "amount": 4250, "status": "sent",
         "issued_on": str(today - timedelta(days=3)), "due_on": str(today + timedelta(days=11)), "is_seed_data": True},
        {"client_id": cid, "subscription_id": sub["id"], "source_type": "subscription",
         "invoice_number": f"INV-R-{suffix}", "amount": 3500, "status": "paid",
         "issued_on": str(today - timedelta(days=30)), "due_on": str(today - timedelta(days=16)), "is_seed_data": True},
    ]).execute()

    return {"seeded": True}


# ---------- ADMIN (service_role, deliberately bypasses RLS) ----------

@app.get("/api/admin/clients")
def admin_clients(admin=Depends(require_admin)):
    return sb.table("clients").select("*").order("created_at", desc=True).execute().data


@app.get("/api/admin/overview")
def admin_overview(admin=Depends(require_admin)):
    out = {}
    for t in ["clients", "bookings", "retainer_subscriptions", "deliverables", "invoices"]:
        out[t] = sb.table(t).select("id", count="exact").execute().count
    return out


class BookingIn(BaseModel):
    client_id: str
    title: str
    shoot_type: Optional[str] = None
    shoot_date: Optional[str] = None
    location: Optional[str] = None
    status: str = "inquiry"
    budget: Optional[float] = None
    notes: Optional[str] = None


class SubscriptionIn(BaseModel):
    client_id: str
    package_name: str
    monthly_price: float = 0
    videos_per_month: int = 1
    status: str = "active"
    renews_on: Optional[str] = None


class DeliverableIn(BaseModel):
    client_id: str
    title: str
    booking_id: Optional[str] = None
    subscription_id: Optional[str] = None
    version: int = 1
    status: str = "draft"
    video_url: Optional[str] = None
    final_file_url: Optional[str] = None
    notes: Optional[str] = None


class InvoiceIn(BaseModel):
    client_id: str
    source_type: str
    booking_id: Optional[str] = None
    subscription_id: Optional[str] = None
    invoice_number: str
    amount: float
    status: str = "draft"
    due_on: Optional[str] = None


class PatchBody(BaseModel):
    status: Optional[str] = None
    version: Optional[int] = None
    video_url: Optional[str] = None
    final_file_url: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/admin/bookings")
def admin_create_booking(body: BookingIn, admin=Depends(require_admin)):
    return sb.table("bookings").insert(body.model_dump(exclude_none=True)).execute().data[0]


@app.post("/api/admin/subscriptions")
def admin_create_subscription(body: SubscriptionIn, admin=Depends(require_admin)):
    return sb.table("retainer_subscriptions").insert(body.model_dump(exclude_none=True)).execute().data[0]


@app.post("/api/admin/deliverables")
def admin_create_deliverable(body: DeliverableIn, admin=Depends(require_admin)):
    if not body.booking_id and not body.subscription_id:
        raise HTTPException(422, "Link the deliverable to a booking_id or subscription_id")
    return sb.table("deliverables").insert(body.model_dump(exclude_none=True)).execute().data[0]


@app.post("/api/admin/invoices")
def admin_create_invoice(body: InvoiceIn, admin=Depends(require_admin)):
    if body.source_type == "booking" and not body.booking_id:
        raise HTTPException(422, "booking invoices require booking_id")
    if body.source_type == "subscription" and not body.subscription_id:
        raise HTTPException(422, "subscription invoices require subscription_id")
    try:
        return sb.table("invoices").insert(body.model_dump(exclude_none=True)).execute().data[0]
    except Exception as e:
        raise HTTPException(422, str(e))


@app.patch("/api/admin/deliverables/{deliverable_id}")
def admin_patch_deliverable(deliverable_id: str, body: PatchBody, admin=Depends(require_admin)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(422, "Nothing to update")
    r = sb.table("deliverables").update(updates).eq("id", deliverable_id).execute()
    if not r.data:
        raise HTTPException(404, "Deliverable not found")
    return r.data[0]


@app.patch("/api/admin/bookings/{booking_id}")
def admin_patch_booking(booking_id: str, body: PatchBody, admin=Depends(require_admin)):
    updates = body.model_dump(exclude_none=True)
    r = sb.table("bookings").update(updates).eq("id", booking_id).execute()
    if not r.data:
        raise HTTPException(404, "Booking not found")
    return r.data[0]


@app.post("/api/admin/clients/{client_id}/erase")
def admin_erase_client(client_id: str, admin=Depends(require_admin)):
    """GDPR erasure: anonymize personal data, preserve financial/business records."""
    r = sb.table("clients").select("*").eq("id", client_id).execute()
    if not r.data:
        raise HTTPException(404, "Client not found")
    client = r.data[0]
    if client["role"] == "admin":
        raise HTTPException(400, "Cannot erase an admin account")
    if client["email"].endswith("@anonymized.invalid"):
        raise HTTPException(409, "Client already erased")

    anon_email = f"erased-{client_id[:8]}@anonymized.invalid"
    try:
        sb.auth.admin.update_user_by_id(client["user_id"], {
            "email": anon_email,
            "password": secrets.token_urlsafe(24),
            "ban_duration": "876000h",
            "user_metadata": {"full_name": "Erased Client", "company": None},
        })
    except Exception as e:
        raise HTTPException(500, f"Auth account update failed; no data was anonymized: {e}")
    sb.table("clients").update({
        "full_name": "Erased Client", "email": anon_email, "company": None,
    }).eq("id", client_id).execute()
    sb.table("review_threads").update({"author_name": "Erased Client"}).eq("client_id", client_id).eq("author_role", "client").execute()
    counts = {
        t: sb.table(t).select("id", count="exact").eq("client_id", client_id).execute().count
        for t in ["bookings", "deliverables", "invoices"]
    }
    sb.table("erasure_audit_log").insert({
        "erased_client_id": client_id,
        "erased_client_previous_role": client["role"],
        "anonymized_email": anon_email,
        "performed_by_client_id": admin["id"],
        "performed_by_email": admin["email"],
        "bookings_preserved": counts["bookings"],
        "deliverables_preserved": counts["deliverables"],
        "invoices_preserved": counts["invoices"],
    }).execute()
    return {
        "erased": True,
        "client_id": client_id,
        "anonymized_email": anon_email,
        "preserved": counts,
        "auth_account": "email anonymized, password rotated, login banned",
        "audit_logged": True,
    }


@app.get("/api/admin/erasure-audit")
def admin_erasure_audit(admin=Depends(require_admin)):
    return sb.table("erasure_audit_log").select("*").order("created_at", desc=True).execute().data
