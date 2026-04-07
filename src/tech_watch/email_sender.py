"""
email_sender.py — Format and send the daily digest email via Gmail API.

Uses OAuth2 refresh token (no password stored).
Sends a nicely formatted HTML email with the top articles of the day.
"""

import logging
import os
import base64
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from tech_watch.config import (
    DIGEST_RECIPIENTS,
    DIGEST_SUBJECT_PREFIX,
    DIGEST_SENDER_NAME,
    MAX_ARTICLES_IN_DIGEST,
)

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def send_digest(articles: list[dict]) -> None:
    """
    Send the daily digest email with the top articles.

    articles: list of enriched article dicts (already filtered + scored)
    """
    if not articles:
        logger.warning("No articles to send — skipping email")
        return

    # Cap at MAX_ARTICLES_IN_DIGEST
    articles = articles[:MAX_ARTICLES_IN_DIGEST]

    service = _get_gmail_service()
    subject = _build_subject()
    html = _build_html(articles)
    plain = _build_plain(articles)

    for recipient in DIGEST_RECIPIENTS:
        message = _create_message(recipient, subject, html, plain)
        _send_message(service, message)
        logger.info(f"Digest sent to {recipient} with {len(articles)} articles")


def _get_gmail_service():
    """Build and return an authenticated Gmail API service."""
    client_id     = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN must all be set in .env")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def _build_subject() -> str:
    """Build the email subject line with today's date."""
    today = datetime.now(timezone.utc).strftime("%d %B %Y")
    return f"{DIGEST_SUBJECT_PREFIX} {today}"


def _create_message(recipient: str, subject: str, html: str, plain: str) -> dict:
    """Create a Gmail API message object."""
    sender_email = os.getenv("GMAIL_SENDER_EMAIL", "")
    sender = f"{DIGEST_SENDER_NAME} <{sender_email}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def _send_message(service, message: dict) -> None:
    """Send a message via the Gmail API."""
    service.users().messages().send(userId="me", body=message).execute()


def _build_html(articles: list[dict]) -> str:
    """Build a clean HTML email body."""
    today = datetime.now(timezone.utc).strftime("%d %B %Y")
    rows = ""
    for a in articles:
        topics_html = "".join(
            f'<span style="background:#e8f4fd;color:#1a73e8;padding:2px 8px;'
            f'border-radius:12px;font-size:12px;margin-right:4px;">{t}</span>'
            for t in a.get("topics", [])
        )
        score = a.get("relevance_score", 0)
        score_color = "#34a853" if score >= 8 else "#fbbc04" if score >= 6 else "#ea4335"
        rows += f"""
        <div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <a href="{a['url']}" style="font-size:16px;font-weight:600;color:#1a1a1a;
                   text-decoration:none;">{a['title']}</a>
                <span style="background:{score_color};color:white;padding:2px 8px;
                   border-radius:12px;font-size:12px;margin-left:12px;white-space:nowrap;">
                   {score}/10
                </span>
            </div>
            <div style="color:#666;font-size:13px;margin:6px 0;">
                {a.get('source', '')} · {a.get('published', '')}
            </div>
            <p style="color:#333;font-size:14px;margin:8px 0;">{a.get('summary', '')}</p>
            <div style="margin-top:8px;">{topics_html}</div>
        </div>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#1a1a1a;">
        <div style="border-bottom:2px solid #1a73e8;padding-bottom:12px;margin-bottom:24px;">
            <h1 style="margin:0;font-size:24px;color:#1a73e8;">Daily Tech Watch</h1>
            <p style="margin:4px 0 0;color:#666;">{today} · {len(articles)} articles</p>
        </div>
        {rows}
        <div style="border-top:1px solid #e0e0e0;margin-top:24px;padding-top:12px;
             color:#999;font-size:12px;text-align:center;">
            Powered by Tech Watch · Unsubscribe anytime by stopping the pipeline
        </div>
    </body></html>"""


def _build_plain(articles: list[dict]) -> str:
    """Build a plain text fallback email body."""
    today = datetime.now(timezone.utc).strftime("%d %B %Y")
    lines = [f"Daily Tech Watch — {today}", f"{len(articles)} articles\n", "="*60]
    for a in articles:
        lines += [
            f"\n[{a.get('relevance_score', 0)}/10] {a['title']}",
            f"Source: {a.get('source', '')}",
            f"URL: {a['url']}",
            f"{a.get('summary', '')}",
            f"Topics: {', '.join(a.get('topics', []))}",
            "-"*60,
        ]
    return "\n".join(lines)
