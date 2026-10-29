"""Educational consultation requests; not bookings or financial advice."""
from datetime import date, datetime, timedelta, timezone
import hmac
import sqlite3
import threading
import time
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
router = APIRouter()
rate_lock = threading.Lock()
requests_by_client = {}

def connect(request: Request):
    DB = request.app.state.settings.database
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS consultations(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
        topic TEXT NOT NULL, preferred_date TEXT NOT NULL,
        message TEXT NOT NULL, consent_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'requested')""")
    return db

class Consultation(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    topic: str = Field(min_length=3, max_length=80)
    preferred_date: date
    message: str = Field(default="", max_length=1200)
    privacy_accepted: bool

    model_config = {"extra": "forbid"}

    @field_validator("name", "topic", "message")
    @classmethod
    def clean_text(cls, v: str):
        v = v.strip()
        if any(ord(c) < 32 and c not in "\n\t" for c in v) or "<" in v or ">" in v:
            raise ValueError("Markup and control characters are not accepted")
        return v

    @field_validator("preferred_date")
    @classmethod
    def reasonable_date(cls, v: date):
        if not date.today() <= v <= date.today() + timedelta(days=180):
            raise ValueError("Date must be within the next 180 days")
        return v

@router.post("/api/consultations", status_code=201)
def create_consultation(payload: Consultation, request: Request):
    if not payload.privacy_accepted:
        raise HTTPException(400, "Privacy consent is required")
    # Use a trusted reverse proxy for public deployments; do not trust X-Forwarded-For.
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with rate_lock:
        hits = [t for t in requests_by_client.get(client, []) if now - t < 3600]
        if len(hits) >= 5:
            raise HTTPException(429, "Rate limit exceeded")
        hits.append(now)
        requests_by_client[client] = hits
    timestamp = datetime.now(timezone.utc).isoformat()
    with connect(request) as db:
        db.execute("DELETE FROM consultations WHERE consent_at < ?",
                   ((datetime.now(timezone.utc)-timedelta(days=90)).isoformat(),))
        cursor = db.execute(
            "INSERT INTO consultations(name,email,topic,preferred_date,message,consent_at) VALUES(?,?,?,?,?,?)",
            (payload.name, str(payload.email), payload.topic,
             str(payload.preferred_date), payload.message, timestamp))
        db.commit()
    return {"id": cursor.lastrowid, "status": "requested",
            "note": "Request received; this is not a confirmed appointment."}

def require_admin(request: Request, token: str | None):
    ADMIN_TOKEN = request.app.state.settings.admin_token
    if not ADMIN_TOKEN or len(ADMIN_TOKEN) < 32:
        raise HTTPException(503, "Admin API disabled")
    if not token or not hmac.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(401, "Not authorized")

@router.get("/api/admin/consultations")
def admin_list(request: Request, x_admin_token: str | None = Header(default=None)):
    require_admin(request, x_admin_token)
    with connect(request) as db:
        data = db.execute(
            "SELECT id,name,email,topic,preferred_date,message,consent_at,status "
            "FROM consultations ORDER BY id DESC LIMIT 100").fetchall()
    return {"requests": [dict(row) for row in data]}

@router.delete("/api/admin/consultations/{item_id}")
def admin_delete(item_id: int, request: Request, x_admin_token: str | None = Header(default=None)):
    require_admin(request, x_admin_token)
    with connect(request) as db:
        result = db.execute("DELETE FROM consultations WHERE id=?", (item_id,))
        db.commit()
    if not result.rowcount:
        raise HTTPException(404, "Not found")
    return {"deleted": True}
