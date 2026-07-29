import base64
import email as email_lib
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from ..models import GmailConnection


def get_credentials(connection: GmailConnection) -> Credentials:
    """Build Google credentials from stored tokens."""
    creds = Credentials(
        token         = connection.access_token,
        refresh_token = connection.refresh_token,
        token_uri     = "https://oauth2.googleapis.com/token",
        client_id     = settings_get("GOOGLE_CLIENT_ID"),
        client_secret = settings_get("GOOGLE_CLIENT_SECRET"),
    )
    # Auto-refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save new token back to DB
        connection.access_token  = creds.token
        connection.token_expiry  = creds.expiry
        connection.save(update_fields=["access_token", "token_expiry"])
    return creds


def get_gmail_service(connection: GmailConnection):
    """Return authenticated Gmail API service."""
    creds = get_credentials(connection)
    return build("gmail", "v1", credentials=creds)


def fetch_unread_emails(connection: GmailConnection) -> list[dict]:
    """
    Fetch unread emails from the connected Gmail inbox.
    Applies sender_filter if set (e.g. '@gmail.com').
    Returns list of dicts ready for emotion classification.
    """
    service = get_gmail_service(connection)

    # Build Gmail query
    query = "is:unread"
    if connection.sender_filter:
        query += f" from:{connection.sender_filter}"

    results = service.users().messages().list(
        userId  = "me",
        q       = query,
        maxResults = 20           # process max 20 per cycle
    ).execute()

    messages = results.get("messages", [])
    parsed   = []

    for msg in messages:
        try:
            detail = service.users().messages().get(
                userId  = "me",
                id      = msg["id"],
                format  = "full"
            ).execute()

            parsed_email = _parse_message(detail)
            if parsed_email:
                parsed.append(parsed_email)

            # Mark as read so we don't re-process
            service.users().messages().modify(
                userId = "me",
                id     = msg["id"],
                body   = {"removeLabelIds": ["UNREAD"]}
            ).execute()

        except Exception as e:
            print(f"[gmail_service] Failed to parse message {msg['id']}: {e}")
            continue

    return parsed


def _parse_message(msg: dict) -> dict | None:
    """Extract sender, subject and body text from a Gmail message."""
    try:
        headers = msg["payload"]["headers"]

        subject  = _get_header(headers, "Subject") or "(no subject)"
        from_raw = _get_header(headers, "From")    or ""
        msg_id   = msg["id"]

        sender_name, sender_email = _parse_sender(from_raw)
        body = _extract_body(msg["payload"])

        if not body.strip():
            return None          # nothing to classify

        return {
            "gmail_message_id": msg_id,
            "customer_name":    sender_name,
            "customer_email":   sender_email,
            "subject":          subject[:500],
            "body_snippet":     body[:300],     # first 300 chars only
            "full_text":        f"{subject}. {body[:500]}",  # sent to HuggingFace
        }

    except Exception as e:
        print(f"[gmail_service] Parse error: {e}")
        return None


def _get_header(headers: list, name: str) -> str | None:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def _parse_sender(from_raw: str) -> tuple[str, str]:
    """
    Parse 'John Smith <john@gmail.com>' into ('John Smith', 'john@gmail.com').
    Falls back gracefully if format differs.
    """
    if "<" in from_raw and ">" in from_raw:
        name  = from_raw.split("<")[0].strip().strip('"')
        email = from_raw.split("<")[1].replace(">", "").strip()
    else:
        name  = ""
        email = from_raw.strip()
    return name, email


def _extract_body(payload: dict) -> str:
    """
    Recursively extract plain text body from Gmail payload.
    Handles both simple and multipart messages.
    """
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

    if "parts" in payload:
        for part in payload["parts"]:
            text = _extract_body(part)
            if text:
                return text

    return ""


def settings_get(key: str) -> str:
    """Helper to get Django settings safely."""
    from django.conf import settings
    return getattr(settings, key, "")
