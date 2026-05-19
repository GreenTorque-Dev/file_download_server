"""
Email Capture Plugin — FastAPI Backend
=======================================
Embed on any website with one <script> tag.
Developer sets which file to send via data-file attribute.
Server stores all files in /files/ folder.
"""

import sqlite3
import uuid
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, EmailStr

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL        = os.getenv("BASE_URL", "http://localhost:8000")
DB_PATH         = "plugin.db"
FILES_DIR       = Path("files")
LINK_EXPIRE_HRS = int(os.getenv("LINK_EXPIRE_HRS", 24))

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))
SMTP_USER     = os.getenv("SMTP_USER", "your@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_app_password")
FROM_EMAIL    = os.getenv("FROM_EMAIL", SMTP_USER)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Email Capture Plugin")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT NOT NULL,
                website     TEXT NOT NULL,
                file_name   TEXT NOT NULL,
                ip          TEXT,
                user_agent  TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS download_links (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                token          TEXT UNIQUE NOT NULL,
                email          TEXT NOT NULL,
                website        TEXT NOT NULL,
                file_name      TEXT NOT NULL,
                created_at     TEXT NOT NULL,
                expires_at     TEXT NOT NULL,
                downloaded     INTEGER DEFAULT 0,
                download_count INTEGER DEFAULT 0
            )
        """)
        db.commit()

init_db()

# ── Helpers ───────────────────────────────────────────────────────────────────
def send_email(to_email: str, subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = FROM_EMAIL
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False

def generate_token():
    return str(uuid.uuid4()).replace("-", "")

def build_email_html(file_name: str, download_url: str, expire_hrs: int) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:30px;">
      <div style="max-width:500px;margin:auto;background:#fff;border-radius:10px;padding:30px;">
        <h2 style="color:#1a1a1a;">Your download is ready</h2>
        <p style="color:#444;">Here is your requested file: <strong>{file_name}</strong></p>
        <p style="color:#444;">This link expires in <strong>{expire_hrs} hours</strong>.</p>
        <a href="{download_url}"
           style="display:inline-block;padding:12px 28px;background:#2563eb;
                  color:#fff;border-radius:6px;text-decoration:none;font-weight:bold;">
          Download Now
        </a>
        <p style="color:#999;font-size:12px;margin-top:20px;">
          If the button does not work:<br>
          <a href="{download_url}" style="color:#2563eb;">{download_url}</a>
        </p>
      </div>
    </body>
    </html>
    """

# ── Models ────────────────────────────────────────────────────────────────────
class SubscribeRequest(BaseModel):
    email:     EmailStr
    website:   str      # from data-website attribute
    file_name: str      # from data-file attribute

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/files")
async def list_files():
    """List all available files in /files/ folder."""
    if not FILES_DIR.exists():
        return {"files": []}
    files = [f.name for f in FILES_DIR.iterdir() if f.is_file()]
    return {"files": sorted(files)}


@app.post("/api/subscribe")
async def subscribe(req: SubscribeRequest, request: Request):
    # Sanitize — prevent path traversal
    file_name = Path(req.file_name).name
    file_path = FILES_DIR / file_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{file_name}' not found on server.")

    now        = datetime.utcnow()
    expires_at = now + timedelta(hours=LINK_EXPIRE_HRS)
    token      = generate_token()
    ip         = request.client.host
    user_agent = request.headers.get("user-agent", "")

    with get_db() as db:
        db.execute(
            "INSERT INTO subscribers (email, website, file_name, ip, user_agent, created_at) VALUES (?,?,?,?,?,?)",
            (req.email, req.website.strip(), file_name, ip, user_agent, now.isoformat()),
        )
        db.execute(
            """INSERT INTO download_links
               (token, email, website, file_name, created_at, expires_at)
               VALUES (?,?,?,?,?,?)""",
            (token, req.email, req.website.strip(), file_name, now.isoformat(), expires_at.isoformat()),
        )
        db.commit()

    download_url = f"{BASE_URL}/download/{token}"
    html         = build_email_html(file_name, download_url, LINK_EXPIRE_HRS)
    email_sent   = send_email(req.email, f"Your download: {file_name}", html)

    return {
        "success":    True,
        "email_sent": email_sent,
        "message":    "Check your email for the download link.",
        "dev_link":   download_url,
    }


@app.get("/download/{token}")
async def download_file(token: str):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM download_links WHERE token = ?", (token,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Invalid link.")

    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
        raise HTTPException(status_code=410, detail="This download link has expired.")

    file_path = FILES_DIR / row["file_name"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    with get_db() as db:
        db.execute(
            "UPDATE download_links SET downloaded=1, download_count=download_count+1 WHERE token=?",
            (token,),
        )
        db.commit()

    return FileResponse(
        path=file_path,
        filename=row["file_name"],
        media_type="application/octet-stream",
    )


@app.get("/admin/subscribers")
async def list_subscribers(secret: str = ""):
    admin_secret = os.getenv("ADMIN_SECRET", "admin123")
    if secret != admin_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    with get_db() as db:
        subscribers = db.execute("SELECT * FROM subscribers ORDER BY created_at DESC").fetchall()
        links       = db.execute("SELECT * FROM download_links ORDER BY created_at DESC").fetchall()

    return {
        "subscribers": [dict(r) for r in subscribers],
        "links":       [dict(r) for r in links],
    }


@app.get("/plugin.js")
async def serve_plugin():
    js = Path("plugin.js").read_text()
    return Response(content=js, media_type="application/javascript")


@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    return Path("demo.html").read_text()