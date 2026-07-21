"""
brief_utils.py
--------------
Fetches a Google Doc or PDF and parses it into event form fields using AI.

AI parsing uses the G2 LiteLLM proxy (OpenAI-compatible) with claude-haiku-4-5.
Falls back to regex parsing if AI is unavailable.

Usage:
    from brief_utils import fetch_doc_text, extract_pdf_text, parse_brief_with_ai
    text = fetch_doc_text(doc_url)
    fields = parse_brief_with_ai(text, proxy_url, api_key)
"""

import re
import json
import requests
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser


# ---------------------------------------------------------------------------
# Google Doc fetching
# ---------------------------------------------------------------------------

def extract_doc_id(url: str) -> str:
    """Extract the document ID from a Google Docs URL."""
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(
            "Could not find a document ID in that URL. "
            "Make sure it's a Google Docs link like: "
            "https://docs.google.com/document/d/YOUR_DOC_ID/edit"
        )
    return match.group(1)


def fetch_doc_text(doc_url: str) -> str:
    """Fetch plain text from a public Google Doc using the export URL.

    No API key required — works for any doc shared as 'Anyone with the link can view'.
    """
    doc_id = extract_doc_id(doc_url)
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    try:
        response = requests.get(export_url, timeout=10)
    except requests.RequestException as e:
        raise ValueError(f"Network error fetching document: {e}")

    if response.status_code == 403:
        raise ValueError(
            "Access denied. Make sure the Google Doc is shared as "
            "'Anyone with the link can view' before importing."
        )
    if response.status_code == 404:
        raise ValueError("Document not found. Check the URL and try again.")
    if not response.ok:
        raise ValueError(
            f"Could not fetch document (error {response.status_code}). "
            "Make sure the doc is shared as 'Anyone with the link can view'."
        )

    return response.text


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF file (as bytes).

    Uses pdfplumber for reliable text extraction including multi-column layouts.

    Args:
        pdf_bytes: Raw PDF file content.

    Returns:
        Extracted plain text.
    """
    try:
        import pdfplumber
        import io
        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except ImportError:
        raise ValueError("pdfplumber is not installed. Run: pip install pdfplumber")
    except Exception as e:
        raise ValueError(f"Could not read PDF: {e}")


# ---------------------------------------------------------------------------
# AI-powered brief parsing via LiteLLM proxy
# ---------------------------------------------------------------------------

AI_SYSTEM_PROMPT = """You are an assistant that extracts event details from marketing campaign briefs.

Extract the following fields and return them as a valid JSON object. If a field is not found, use null.

Fields to extract:
- title: Event name or title
- date: Event date (as written in the brief)
- start_time: Start time (as written)
- end_time: End time (as written)
- timezone: Timezone (convert abbreviations like CT, ET, PT to IANA format like America/Chicago)
- location: Physical venue or address
- meeting_url: Zoom, Teams, Google Meet, or other virtual meeting URL
- description: Event description, overview, or about section
- organizer_name: Name of the organizer, host, or contact person
- organizer_email: Email of the organizer
- campaign_id: Campaign name, ID, or internal event ID
- landing_page_url: Registration or landing page URL (not the meeting URL)

Return ONLY a JSON object, no explanation or markdown."""

AI_USER_PROMPT = """Extract event details from this campaign brief:

{brief_text}

Return a JSON object with the fields described."""


def parse_brief_with_ai(text: str, proxy_url: str, api_key: str) -> dict:
    """Parse a brief using the G2 LiteLLM proxy (OpenAI-compatible API).

    Uses claude-haiku-4-5 for fast, cost-effective extraction.

    Args:
        text: Plain text content of the brief.
        proxy_url: LiteLLM proxy base URL (e.g. https://llmproxy.g2.com).
        api_key: LiteLLM API key.

    Returns:
        Dict of parsed event fields.
    """
    # Truncate very long briefs to avoid token limits
    brief_text = text[:8000] if len(text) > 8000 else text

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "claude-haiku-4-5",
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": AI_USER_PROMPT.format(brief_text=brief_text)},
        ],
        "temperature": 0,
        "max_tokens": 1000,
    }

    try:
        response = requests.post(
            f"{proxy_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        raise ValueError(f"Network error calling AI: {e}")

    if response.status_code == 401:
        raise ValueError("Invalid API key. Check your LiteLLM key in Streamlit secrets.")
    if response.status_code == 404:
        raise ValueError("AI proxy URL not found. Check the proxy URL in Streamlit secrets.")
    if not response.ok:
        raise ValueError(f"AI error {response.status_code}: {response.text[:200]}")

    try:
        content = response.json()["choices"][0]["message"]["content"]
        # Strip markdown code fences if present
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        ai_fields = json.loads(content)
    except (KeyError, json.JSONDecodeError) as e:
        raise ValueError(f"Could not parse AI response: {e}")

    return _build_event_fields(ai_fields)


def _build_event_fields(ai_fields: dict) -> dict:
    """Convert raw AI-extracted fields into typed event form fields.

    Parses date/time strings into datetime objects and resolves timezones.
    """
    result = {}

    # Title
    result["title"] = ai_fields.get("title") or ""

    # Dates — combine date + time strings
    date_raw = ai_fields.get("date") or ""
    start_time_raw = ai_fields.get("start_time") or ""
    end_time_raw = ai_fields.get("end_time") or ""

    result["start_dt"] = _parse_dt(date_raw, start_time_raw)
    result["end_dt"] = _parse_dt(date_raw, end_time_raw)

    # If end_dt missing, default to 1 hour after start
    if result["start_dt"] and not result["end_dt"]:
        result["end_dt"] = result["start_dt"] + timedelta(hours=1)

    # Timezone
    tz_raw = ai_fields.get("timezone") or ""
    result["timezone"] = tz_raw.strip() if tz_raw else ""

    # String fields
    result["location"] = ai_fields.get("location") or ""
    result["meeting_url"] = ai_fields.get("meeting_url") or ""
    result["description"] = ai_fields.get("description") or ""
    result["organizer_name"] = ai_fields.get("organizer_name") or ""
    result["organizer_email"] = ai_fields.get("organizer_email") or ""
    result["campaign_id"] = ai_fields.get("campaign_id") or ""
    result["landing_page_url"] = ai_fields.get("landing_page_url") or ""

    return result


def _parse_dt(date_str: str, time_str: str) -> datetime | None:
    """Parse a date + time string into a naive datetime."""
    if not date_str:
        return None
    try:
        combined = f"{date_str} {time_str}".strip()
        return dateutil_parser.parse(combined, fuzzy=True)
    except Exception:
        try:
            return dateutil_parser.parse(date_str, fuzzy=True)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Fallback regex parser (used when AI is not configured)
# ---------------------------------------------------------------------------

FIELD_PATTERNS = {
    "title": [r"(?:event\s+(?:name|title)|webinar\s+(?:name|title)|title|name)\s*[:\-]\s*(.+)"],
    "date": [r"(?:date|event\s+date|when)\s*[:\-]\s*(.+)"],
    "start_time": [
        r"(?:start\s+time|time\s+start|begins?|starts?)\s*[:\-]\s*(.+)",
        r"(?:time)\s*[:\-]\s*(.+)",
    ],
    "end_time": [r"(?:end\s+time|time\s+end|ends?|concludes?|wraps?\s+up)\s*[:\-]\s*(.+)"],
    "timezone": [r"(?:time\s*zone|tz|timezone)\s*[:\-]\s*(.+)"],
    "location": [r"(?:location|venue|where|address|place)\s*[:\-]\s*(.+)"],
    "meeting_url": [
        r"(?:meeting\s+url|join\s+url|webinar\s+url|zoom\s+link|teams\s+link)\s*[:\-]\s*(https?://\S+)",
    ],
    "description": [r"(?:description|about|overview|summary|details?)\s*[:\-]\s*(.+)"],
    "organizer_name": [r"(?:organizer|host|contact|presenter|speaker|owner)\s*(?:name)?\s*[:\-]\s*(.+)"],
    "organizer_email": [
        r"email\s*[:\-]\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    ],
    "campaign_id": [r"(?:campaign|campaign\s+(?:name|id)|event\s+id|internal\s+id)\s*[:\-]\s*(.+)"],
    "landing_page_url": [
        r"(?:landing\s+page|registration\s+(?:url|link|page)|register\s+(?:url|link|here))\s*[:\-]\s*(https?://\S+)",
    ],
}

TZ_ABBREVIATIONS = {
    "ET": "America/New_York", "EST": "America/New_York", "EDT": "America/New_York",
    "CT": "America/Chicago", "CST": "America/Chicago", "CDT": "America/Chicago",
    "MT": "America/Denver", "MST": "America/Denver", "MDT": "America/Denver",
    "PT": "America/Los_Angeles", "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles",
    "UTC": "UTC", "GMT": "UTC",
}


def parse_brief(text: str) -> dict:
    """Regex-based fallback parser. Used when AI is not configured."""
    result = {}

    def extract(field):
        for pattern in FIELD_PATTERNS.get(field, []):
            m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if m:
                v = re.sub(r"[;,.]$", "", m.group(1).strip())
                if v:
                    return v
        return None

    title = extract("title")
    if not title:
        for line in text.splitlines():
            line = line.strip()
            if line and len(line) < 120:
                title = line
                break
    result["title"] = title or ""

    date_raw = extract("date")
    start_raw = extract("start_time")
    end_raw = extract("end_time")

    result["start_dt"] = _parse_dt(date_raw or "", start_raw or "")
    result["end_dt"] = _parse_dt(date_raw or "", end_raw or "")
    if result["start_dt"] and not result["end_dt"]:
        result["end_dt"] = result["start_dt"] + timedelta(hours=1)

    tz_raw = extract("timezone")
    if not tz_raw:
        m = re.search(r"\b(ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT|UTC|GMT)\b", text, re.IGNORECASE)
        if m:
            tz_raw = m.group(1).upper()
    tz = TZ_ABBREVIATIONS.get((tz_raw or "").upper(), "")
    if not tz and tz_raw and "/" in tz_raw:
        tz = tz_raw.strip()
    result["timezone"] = tz

    result["location"] = extract("location") or ""

    meeting_url = extract("meeting_url")
    if not meeting_url:
        m = re.search(r"https?://(?:[\w.-]*zoom\.us|teams\.microsoft\.com|meet\.google\.com)/\S+", text)
        if m:
            meeting_url = m.group(0).rstrip(".,;)")
    result["meeting_url"] = meeting_url or ""

    result["description"] = extract("description") or ""
    result["organizer_name"] = extract("organizer_name") or ""

    email = extract("organizer_email")
    if not email:
        m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
        if m:
            email = m.group(0)
    result["organizer_email"] = email or ""

    result["campaign_id"] = extract("campaign_id") or ""

    landing = extract("landing_page_url")
    if not landing:
        for url in re.findall(r"https?://\S+", text):
            if not re.search(r"zoom\.us|teams\.microsoft|meet\.google", url):
                landing = url.rstrip(".,;)")
                break
    result["landing_page_url"] = landing or ""

    return result
