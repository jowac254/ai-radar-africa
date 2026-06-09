"""
AI Radar Africa - Gmail Sender
Sends the daily brief via Gmail API (OAuth2).
Supports both interactive auth (local) and service account / token file (GitHub Actions).
"""

import os
import base64
import json
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from datetime import date

log = logging.getLogger(__name__)

# ── Dependencies ───────────────────────────────────────────────────────────────
# pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None

    # 1. Try loading saved token
    if Path(TOKEN_PATH).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # 2. If no valid creds, refresh or re-auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(CREDENTIALS_PATH).exists():
                raise FileNotFoundError(
                    "credentials.json not found. Download it from Google Cloud Console "
                    "(APIs & Services → Credentials → OAuth 2.0 Client ID → Download JSON)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the token for next run
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        log.info(f"Token saved → {TOKEN_PATH}")

    return build("gmail", "v1", credentials=creds)


def build_email_html(brief_text: str, today: str) -> str:
    """Wrap the brief in clean HTML for email rendering."""
    # Convert section markers to HTML headings
    html_body = brief_text
    replacements = [
        ("---AI RADAR AFRICA BRIEF---", f"<h1 style='color:#1a1a2e;font-family:sans-serif'>🌍 AI Radar Africa — {today}</h1>"),
        ("---PODCAST SCRIPT---",        "<hr><h2 style='color:#16213e;font-family:sans-serif'>🎙️ Podcast Script</h2>"),
        ("---LINKEDIN POST---",         "<hr><h2 style='color:#16213e;font-family:sans-serif'>💼 LinkedIn Post</h2>"),
        ("🔴 TOP STORY",               "<h3 style='color:#c0392b'>🔴 Top Story</h3>"),
        ("🟡 SECONDARY STORY",         "<h3 style='color:#e67e22'>🟡 Secondary Story</h3>"),
        ("🟢 EMERGING TREND",          "<h3 style='color:#27ae60'>🟢 Emerging Trend</h3>"),
    ]
    for old, new in replacements:
        html_body = html_body.replace(old, new)

    # Wrap lines in paragraphs
    lines = html_body.split("\n")
    paragraphs = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<h"):
            paragraphs.append(stripped)
        elif stripped.startswith("-"):
            paragraphs.append(f"<li style='font-family:sans-serif;margin:4px 0'>{stripped[1:].strip()}</li>")
        elif stripped:
            paragraphs.append(f"<p style='font-family:sans-serif;margin:6px 0'>{stripped}</p>")

    return f"""
    <html><body style='max-width:680px;margin:auto;padding:24px;background:#fafafa'>
    {''.join(paragraphs)}
    <hr>
    <p style='font-size:12px;color:#888;font-family:sans-serif'>
    AI Radar Africa · Nairobi, Kenya · 
    <a href='https://tiktok.com/@jowac254'>@jowac254 on TikTok</a>
    </p>
    </body></html>
    """


def send_brief(brief_text: str, to_email: str, from_email: str = None):
    """Send the daily brief via Gmail API."""
    today = date.today().strftime("%B %d, %Y")
    subject = f"🌍 AI Radar Africa — {today}"

    from_email = from_email or os.environ.get("GMAIL_SENDER", "")
    if not from_email:
        raise ValueError("Set GMAIL_SENDER in your .env file (your Gmail address).")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_email
    msg["To"]      = to_email

    # Plain text fallback
    msg.attach(MIMEText(brief_text, "plain"))
    # HTML version
    msg.attach(MIMEText(build_email_html(brief_text, today), "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service = get_gmail_service()
    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    log.info(f"Email sent! Message ID: {result['id']} → {to_email}")
    return result


if __name__ == "__main__":
    import sys

    brief_path = f"outputs/brief_{date.today()}.json"
    # Try .txt if no .json
    if not Path(brief_path).exists():
        brief_path = f"outputs/brief_{date.today()}.txt"

    if not Path(brief_path).exists():
        print("No brief found. Run brief_generator.py first.")
        sys.exit(1)

    with open(brief_path) as f:
        brief_text = f.read()

    to_email = os.environ.get("BRIEF_RECIPIENT", "")
    if not to_email:
        to_email = input("Enter recipient email: ").strip()

    send_brief(brief_text, to_email)
    print("✅ Brief sent via Gmail!")
