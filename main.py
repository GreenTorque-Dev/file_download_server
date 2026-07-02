"""
Email Capture Plugin — FastAPI Backend
=======================================
Embed on any website with one <script> tag.
Developer sets which file to send via data-file attribute.
Server stores all files in /files/ folder.

Python 3.12 + Pydantic v2 compatible.
"""

import sqlite3
import uuid
import smtplib
import os
from datetime import datetime, timedelta, timezone
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

def _build_specs_block(spec_module: str | None, spec_version: str | None, spec_arch: str | None) -> str:
    """Deployment Specifications box — only renders rows that were actually provided.
    Returns "" entirely if none of the three fields were supplied."""
    rows = []
    if spec_module:
        rows.append(
            f'<span style="color:#22c55e; margin-right:5px;">&#10003;</span>'
            f'<strong>Product Module:</strong> {spec_module}<br>'
        )
    if spec_version:
        rows.append(
            f'<span style="color:#22c55e; margin-right:5px;">&#10003;</span>'
            f'<strong>Version/Build:</strong> {spec_version}<br>'
        )
    if spec_arch:
        rows.append(
            f'<span style="color:#22c55e; margin-right:5px;">&#10003;</span>'
            f'<strong>Target Architecture:</strong> {spec_arch}'
        )

    if not rows:
        return ""

    rows_html = "\n            ".join(rows)
    return f"""
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;background:#fafafa;border:1px solid #eef2f2;border-radius:6px;">
        <tr>
          <td style="padding:15px 20px;font-size:13px;color:#444;line-height:1.8;">
            <strong style="color:#1f4d4d;font-size:11px;text-transform:uppercase;display:block;margin-bottom:8px;letter-spacing:0.5px;">
              &#9881; Deployment Specifications
            </strong>
            {rows_html}
          </td>
        </tr>
      </table>"""


def _build_doc_link_block(doc_link: str | None) -> str:
    """Technical documentation paragraph — only renders if a doc link was supplied."""
    if not doc_link:
        return ""
    return f"""
      <p style="margin-top:30px;">
        For configuration and operational management, please refer to the <a href="{doc_link}" style="color:#1f4d4d;text-decoration:underline;font-weight:600;">technical documentation</a>.
      </p>"""


def build_email_html(
    file_name: str,
    download_url: str,
    expire_hrs: int,
    doc_link: str | None = None,
    spec_module: str | None = None,
    spec_version: str | None = None,
    spec_arch: str | None = None,
) -> str:
    specs_html = _build_specs_block(spec_module, spec_version, spec_arch)
    doc_html   = _build_doc_link_block(doc_link)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Your Download</title>
</head>

<body style="margin:0;padding:0;background-color:#0b1f1f;font-family:Arial,Helvetica,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;background:#0b1f1f;">
<tr>
<td align="center">

<table width="620" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.25);">

  <tr>
    <td style="background:linear-gradient(135deg,#0f2a2a,#1f4d4d);padding:35px 30px;text-align:center;color:#ffffff;">

      <div style="margin:0 auto 15px; width:46px; height:24px; background:#4ade80; border-radius:20px; position:relative; display:block; opacity:0.95;">
        <div style="position:absolute; width:22px; height:22px; background:#4ade80; border-radius:50%; top:-10px; left:6px;"></div>
        <div style="position:absolute; width:16px; height:16px; background:#4ade80; border-radius:50%; top:-6px; right:6px;"></div>
      </div>

      <h2 style="margin:0;font-weight:600;letter-spacing:0.5px;font-size:24px;">
        Your Download Is Ready
      </h2>

      <p style="margin:8px 0 0;color:#b8d4d4;font-size:13px;letter-spacing:0.5px;">
        Secure Delivery • Enterprise Ready
      </p>

    </td>
  </tr>

  <tr>
    <td style="padding:40px 40px 35px;color:#333333;font-size:14px;line-height:1.7;">

      <p style="margin-top:0;font-size:15px;">Dear Customer,</p>

      <p>Your requested file is ready for download.</p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin:25px 0;background:#f4f8f8;border-left:4px solid #22c55e;border-radius:6px;">
        <tr>
          <td style="padding:25px;text-align:center;">

            <div style="margin:0 auto 12px; width:36px; height:36px; background:#e6f7ed; border-radius:50%; line-height:36px; text-align:center; color:#22c55e; font-size:18px; font-weight:bold;">
              &darr;
            </div>

            <p style="margin:0 0 18px;color:#445555;font-size:13px;font-weight:600;">
              Click below to securely download your file:
            </p>

            <a href="{download_url}"
            style="background:#22c55e; color:#ffffff; text-decoration:none; padding:12px 28px;
            border-radius:6px; display:inline-block; box-shadow:0 4px 14px rgba(34,197,94,0.35); text-align:left;">

              <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                <tr>
                  <td style="padding-right:12px; vertical-align:middle;">
                    <div style="width:28px; height:36px; background:#ffffff; border-radius:3px; position:relative; overflow:hidden; border-top-right-radius:10px;">
                      <div style="position:absolute; top:0; right:0; width:0; height:0; border-style:solid; border-width:0 10px 10px 0; border-color:transparent transparent #d1ebd9 transparent; background:#22c55e;"></div>
                      <div style="position:absolute; bottom:3px; width:100%; text-align:center; font-family:Arial, sans-serif; font-size:9px; font-weight:900; color:#22c55e; letter-spacing:0.3px;">FILE</div>
                    </div>
                  </td>
                  <td style="vertical-align:middle; line-height:1.2;">
                    <span style="font-size:14px; font-weight:800; display:block; letter-spacing:0.5px; text-transform:uppercase;">Download {file_name}</span>
                    <span style="font-size:10px; font-weight:400; color:#d1ebd9; display:block; margin-top:2px;">Secure Protocol Block &darr;</span>
                  </td>
                </tr>
              </table>

            </a>

            <p style="margin:18px 0 0;font-size:11px;color:#778888;font-style:italic;">
              &#9202; This secure link expires automatically in {expire_hrs} hours.
            </p>

          </td>
        </tr>
      </table>
{specs_html}
{doc_html}

      <p style="margin-bottom:0;padding-top:10px;">
        Best regards,<br>
        <strong style="color:#1f4d4d;">The Delivery Team</strong>
      </p>

    </td>
  </tr>

  <tr>
    <td style="height:1px;background:#e6eeee;"></td>
  </tr>

  <tr>
    <td style="padding:25px 30px;text-align:center;background:#f4f8f8;font-size:12px;color:#667777;line-height:1.6;">

      <div style="margin-bottom:8px;">
        <strong style="color:#2f3f3f;">{FROM_EMAIL}</strong>
      </div>

      <div style="margin-top:15px;color:#aaaaaa;font-size:11px;">
        &copy; {datetime.now(timezone.utc).year} All rights reserved.
      </div>

    </td>
  </tr>

</table>

</td>
</tr>
</table>

</body>
</html>
    """

# ── Models ────────────────────────────────────────────────────────────────────
class SubscribeRequest(BaseModel):
    email:     EmailStr
    website:   str      # from data-website attribute
    file_name: str      # from data-file attribute

    # Optional — all None/omitted by default, each section only renders if present
    doc_link:     str | None = None   # from data-doc-link attribute
    spec_module:  str | None = None   # from data-spec-module attribute
    spec_version: str | None = None   # from data-spec-version attribute
    spec_arch:    str | None = None   # from data-spec-arch attribute

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

    # ✅ Python 3.12: use timezone-aware datetime instead of deprecated utcnow()
    now        = datetime.now(timezone.utc)
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
    html         = build_email_html(
        file_name,
        download_url,
        LINK_EXPIRE_HRS,
        doc_link=req.doc_link,
        spec_module=req.spec_module,
        spec_version=req.spec_version,
        spec_arch=req.spec_arch,
    )
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

    # ✅ Python 3.12: compare timezone-aware datetimes consistently
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at.tzinfo is None:
        # Handle legacy rows stored without timezone info
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
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
    if secret != 'admin':
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