"""
brief_utils.py
--------------
Fetches a Google Doc and parses it into event form fields.

Requires:
  - A Google Docs API key (restricted to Google Docs API)
  - The Google Doc must be shared as "Anyone with the link can view"

Usage:
    from brief_utils import fetch_doc_text, parse_brief
    text = fetch_doc_text(doc_url, api_key)
    fields = parse_brief(text)
"""

import re
import requests
from datetime import datetime, date, time
from dateutil import parser as dateutil_parser


# ---------------------------------------------------------------------------
# Google Doc fetching
# ---------------------------------------------------------------------------

def extract_doc_id(url: str) -> str:
    """Extract the document ID from a Google Docs URL.

    Handles formats like:
      https://docs.google.com/document/d/DOC_ID/edit
      https://docs.google.com/document/d/DOC_ID/view
      https://docs.google.com/document/d/DOC_ID
    """
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(
            "Could not find a document ID in that URL. "
            "Make sure it's a Google Docs link like: "
            "https://docs.google.com/document/d/YOUR_DOC_ID/edit"
        )
    return match.group(1)


def fetch_doc_text(doc_url: str, api_key: str) -> str:
    """Fetch the plain text content of a public Google Doc via the Docs API.

    Args:
        doc_url: Full Google Docs URL.
        api_key: Google Docs API key.

    Returns:
        Plain text content of the document.

    Raises:
        ValueError: If the URL is invalid, the doc is not accessible,
                    or the API key is incorrect.
    """
    doc_id = extract_doc_id(doc_url)

    api_url = f"https://docs.googleapis.com/v1/documents/{doc_id}"
    params = {"key": api_key}

    try:
        response = requests.get(api_url, params=params, timeout=10)
    except requests.RequestException as e:
        raise ValueError(f"Network error fetching document: {e}")

    if response.status_code == 403:
        raise ValueError(
            "Access denied. Make sure the Google Doc is shared as "
            "'Anyone with the link can view'."
        )
    if response.status_code == 404:
        raise ValueError("Document not found. Check the URL and try again.")
    if response.status_code == 400:
        raise ValueError(
            "Invalid API key or request. Double-check your API key in Settings."
        )
    if not response.ok:
        raise ValueError(f"Google API error {response.status_code}: {response.text[:200]}")

    data = response.json()

    # Extract plain text from the document's structural content
    text_parts = []
    for element in data.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for pe in paragraph.get("elements", []):
            tr = pe.get("textRun")
            if tr:
                text_parts.append(tr.get("content", ""))

    return "".join(text_parts)


# ---------------------------------------------------------------------------
# Brief parsing
# ---------------------------------------------------------------------------

# Patterns to match labeled fields in a brief document
FIELD_PATTERNS = {
    "title": [
        r"(?:event\s+(?:name|title)|webinar\s+(?:name|title)|title|name)\s*[:\-]\s*(.+)",
    ],
    "date": [
        r"(?:date|event\s+date|when)\s*[:\-]\s*(.+)",
    ],
    "start_time": [
        r"(?:start\s+time|time\s+start|begins?|starts?)\s*[:\-]\s*(.+)",
        r"(?:time)\s*[:\-]\s*(.+)",
    ],
    "end_time": [
        r"(?:end\s+time|time\s+end|ends?|concludes?|wraps?\s+up)\s*[:\-]\s*(.+)",
    ],
    "timezone": [
        r"(?:time\s*zone|tz|timezone)\s*[:\-]\s*(.+)",
    ],
    "location": [
        r"(?:location|venue|where|address|place)\s*[:\-]\s*(.+)",
    ],
    "meeting_url": [
        r"(?:zoom|meeting|join|webinar|virtual|call)\s+(?:url|link|link)\s*[:\-]\s*(https?://\S+)",
        r"(?:meeting\s+url|join\s+url|webinar\s+url|zoom\s+link|teams\s+link)\s*[:\-]\s*(https?://\S+)",
    ],
    "description": [
        r"(?:description|about|overview|summary|details?)\s*[:\-]\s*(.+)",
    ],
    "organizer_name": [
        r"(?:organizer|host|contact|presenter|speaker|owner)\s*(?:name)?\s*[:\-]\s*(.+)",
    ],
    "organizer_email": [
        r"(?:organizer|host|contact|presenter|speaker|owner)\s*(?:email)?\s*[:\-]\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
        r"email\s*[:\-]\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    ],
    "campaign_id": [
        r"(?:campaign|campaign\s+(?:name|id)|event\s+id|internal\s+id)\s*[:\-]\s*(.+)",
    ],
    "landing_page_url": [
        r"(?:landing\s+page|registration\s+(?:url|link|page)|register\s+(?:url|link|here)|event\s+(?:url|link|page))\s*[:\-]\s*(https?://\S+)",
    ],
}

# Common timezone abbreviations → IANA names
TZ_ABBREVIATIONS = {
    "ET": "America/New_York",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CT": "America/Chicago",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MT": "America/Denver",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PT": "America/Los_Angeles",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "UTC": "UTC",
    "GMT": "UTC",
}


def extract_field(text: str, field: str) -> str | None:
    """Try each pattern for a field and return the first match, stripped."""
    patterns = FIELD_PATTERNS.get(field, [])
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            # Remove trailing punctuation that got caught
            value = re.sub(r"[;,.]$", "", value).strip()
            if value:
                return value
    return None


def extract_urls_from_text(text: str) -> list[str]:
    """Find all URLs in the text."""
    return re.findall(r"https?://\S+", text)


def parse_datetime_str(date_str: str, time_str: str | None = None) -> datetime | None:
    """Parse a date string (and optional time string) into a datetime.

    Uses dateutil for flexible parsing of formats like:
      "September 15, 2024", "9/15/24", "2024-09-15", "Monday, Sept 15"
    """
    if not date_str:
        return None
    try:
        combined = date_str.strip()
        if time_str:
            combined = f"{date_str.strip()} {time_str.strip()}"
        return dateutil_parser.parse(combined, fuzzy=True)
    except (ValueError, OverflowError):
        try:
            return dateutil_parser.parse(date_str.strip(), fuzzy=True)
        except Exception:
            return None


def resolve_timezone(tz_raw: str | None) -> str:
    """Convert a raw timezone string to an IANA name if possible."""
    if not tz_raw:
        return ""
    tz_clean = tz_raw.strip().upper()
    # Check abbreviations map
    if tz_clean in TZ_ABBREVIATIONS:
        return TZ_ABBREVIATIONS[tz_clean]
    # Check if it looks like an IANA name (contains /)
    if "/" in tz_raw:
        return tz_raw.strip()
    return ""


def parse_brief(text: str) -> dict:
    """Parse a campaign brief text into a dict of event form fields.

    Returns a dict with keys matching the event form. Values are best-effort
    extractions — the user should review and correct before generating assets.

    Keys returned (all optional / may be None):
        title, start_dt, end_dt, timezone, location, meeting_url,
        description, organizer_name, organizer_email, campaign_id,
        landing_page_url
    """
    result = {}

    # ── Title ────────────────────────────────────────────────────────────────
    title = extract_field(text, "title")
    if not title:
        # Fall back to the first non-empty line
        for line in text.splitlines():
            line = line.strip()
            if line and len(line) < 120:
                title = line
                break
    result["title"] = title or ""

    # ── Dates & times ────────────────────────────────────────────────────────
    date_raw = extract_field(text, "date")
    start_time_raw = extract_field(text, "start_time")
    end_time_raw = extract_field(text, "end_time")

    start_dt = parse_datetime_str(date_raw, start_time_raw)
    result["start_dt"] = start_dt

    if end_time_raw:
        end_dt = parse_datetime_str(date_raw, end_time_raw)
        result["end_dt"] = end_dt
    elif start_dt:
        # Default to 1 hour after start if no end time found
        from datetime import timedelta
        result["end_dt"] = start_dt.replace(
            hour=min(start_dt.hour + 1, 23),
            minute=start_dt.minute,
        )
    else:
        result["end_dt"] = None

    # ── Timezone ─────────────────────────────────────────────────────────────
    tz_raw = extract_field(text, "timezone")
    if not tz_raw:
        # Look for timezone abbreviations anywhere in the text
        tz_match = re.search(
            r"\b(ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT|UTC|GMT)\b",
            text, re.IGNORECASE
        )
        if tz_match:
            tz_raw = tz_match.group(1).upper()
    result["timezone"] = resolve_timezone(tz_raw)

    # ── Location ─────────────────────────────────────────────────────────────
    result["location"] = extract_field(text, "location") or ""

    # ── Meeting URL ───────────────────────────────────────────────────────────
    meeting_url = extract_field(text, "meeting_url")
    if not meeting_url:
        # Search for Zoom/Teams/Meet links anywhere in the text
        url_match = re.search(
            r"https?://(?:[\w.-]*zoom\.us|teams\.microsoft\.com|meet\.google\.com)/\S+",
            text
        )
        if url_match:
            meeting_url = url_match.group(0).rstrip(".,;)")
    result["meeting_url"] = meeting_url or ""

    # ── Description ───────────────────────────────────────────────────────────
    description = extract_field(text, "description")
    result["description"] = description or ""

    # ── Organizer ─────────────────────────────────────────────────────────────
    result["organizer_name"] = extract_field(text, "organizer_name") or ""

    # Email — try labeled field first, then any email in the text
    organizer_email = extract_field(text, "organizer_email")
    if not organizer_email:
        email_match = re.search(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text
        )
        if email_match:
            organizer_email = email_match.group(0)
    result["organizer_email"] = organizer_email or ""

    # ── Campaign ID ───────────────────────────────────────────────────────────
    result["campaign_id"] = extract_field(text, "campaign_id") or ""

    # ── Landing page URL ──────────────────────────────────────────────────────
    landing_url = extract_field(text, "landing_page_url")
    if not landing_url:
        # Any URL that isn't a meeting URL
        for url in extract_urls_from_text(text):
            if not re.search(r"zoom\.us|teams\.microsoft|meet\.google", url):
                landing_url = url.rstrip(".,;)")
                break
    result["landing_page_url"] = landing_url or ""

    return result
