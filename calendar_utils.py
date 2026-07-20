"""
calendar_utils.py
-----------------
Core utility functions for the Marketing Calendar Hold Builder.

Handles:
  - RFC 5545-compliant ICS file generation
  - Google Calendar add-event URL construction
  - Outlook Web App add-event URL construction
  - HTML "Add to Calendar" button generation (Marketo-safe)
  - DST-aware datetime conversion
  - URL encoding and HTML escaping
  - Form validation
"""

import re
import html
import uuid
import urllib.parse
from datetime import datetime, date, timedelta
from typing import Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOOGLE_CAL_BASE = "https://calendar.google.com/calendar/render"
OUTLOOK_CAL_BASE = "https://outlook.live.com/calendar/0/deeplink/compose"

REQUIRED_FIELDS = ["title", "start_dt", "end_dt", "timezone", "organizer_name", "organizer_email"]

ICS_DATETIME_FORMAT = "%Y%m%dT%H%M%S"
ICS_DATE_FORMAT = "%Y%m%d"


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------

def parse_timezone(tz_name: str) -> ZoneInfo:
    """Return a ZoneInfo object for the given IANA timezone name.

    Raises ValueError with a human-readable message on invalid input.
    """
    if not tz_name:
        raise ValueError("Timezone is required.")
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        raise ValueError(f"Unknown timezone: '{tz_name}'. Use an IANA name like 'America/Chicago'.")


def localize(dt: datetime, tz_name: str) -> datetime:
    """Attach a timezone to a naive datetime using the IANA timezone name.

    Correctly resolves DST offsets for the given wall-clock time.

    Args:
        dt: A naive (no tzinfo) datetime object.
        tz_name: IANA timezone string, e.g. 'America/New_York'.

    Returns:
        A timezone-aware datetime.
    """
    tz = parse_timezone(tz_name)
    # Replace tzinfo — this is the correct way to attach a ZoneInfo zone
    # and properly resolves DST for the wall-clock time.
    return dt.replace(tzinfo=tz)


def to_utc(dt: datetime) -> datetime:
    """Convert a timezone-aware datetime to UTC."""
    from datetime import timezone
    return dt.astimezone(timezone.utc)


def format_ics_datetime(dt: datetime, all_day: bool = False) -> str:
    """Format a datetime for ICS output.

    For all-day events, returns DATE format (YYYYMMDD).
    For timed events, returns UTC datetime (YYYYMMDDTHHMMSSZ).
    """
    if all_day:
        if isinstance(dt, datetime):
            return dt.strftime(ICS_DATE_FORMAT)
        return dt.strftime(ICS_DATE_FORMAT)
    utc = to_utc(dt)
    return utc.strftime(ICS_DATETIME_FORMAT) + "Z"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_email(email: str) -> bool:
    """Basic RFC 5322-ish email validation."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def validate_url(url: str) -> bool:
    """Loose URL validation — must start with http:// or https://."""
    if not url:
        return True  # Optional fields are fine when empty
    return bool(re.match(r"^https?://", url.strip()))


def validate_event(data: dict) -> list[str]:
    """Validate event data dict. Returns a list of error strings (empty = valid).

    Checks:
      - Required fields are present and non-empty
      - Organizer email is valid
      - End time is after start time (for non-all-day events)
      - Virtual meeting URL and landing page URL are valid if provided
      - Timezone is a known IANA name

    Args:
        data: Dictionary with event fields (see build_ics / build_google_url for keys).

    Returns:
        List of human-readable error strings.
    """
    errors = []

    # Required presence checks
    if not data.get("title", "").strip():
        errors.append("Event title is required.")
    if not data.get("organizer_name", "").strip():
        errors.append("Organizer name is required.")
    if not data.get("organizer_email", "").strip():
        errors.append("Organizer email is required.")
    elif not validate_email(data["organizer_email"]):
        errors.append(f"Organizer email '{data['organizer_email']}' is not valid.")

    # Timezone
    tz_name = data.get("timezone", "")
    if not tz_name:
        errors.append("Timezone is required.")
    else:
        try:
            parse_timezone(tz_name)
        except ValueError as e:
            errors.append(str(e))

    # Datetime checks
    all_day = data.get("all_day", False)
    start = data.get("start_dt")
    end = data.get("end_dt")

    if start is None:
        errors.append("Start date/time is required.")
    if end is None:
        errors.append("End date/time is required.")

    if start is not None and end is not None and not errors:
        if not all_day:
            # Both are datetimes — localize if naive
            if isinstance(start, datetime) and start.tzinfo is None and tz_name:
                try:
                    start = localize(start, tz_name)
                    end = localize(end, tz_name)
                except ValueError:
                    pass  # TZ error already caught above
            if isinstance(start, datetime) and isinstance(end, datetime):
                if end <= start:
                    errors.append("End date/time must be after start date/time.")
        else:
            # All-day: compare as dates
            s = start.date() if isinstance(start, datetime) else start
            e = end.date() if isinstance(end, datetime) else end
            if e < s:
                errors.append("End date must be on or after start date for all-day events.")

    # Optional URL fields
    for field, label in [("meeting_url", "Virtual meeting URL"), ("landing_page_url", "Landing-page URL")]:
        val = data.get(field, "")
        if val and not validate_url(val):
            errors.append(f"{label} must start with http:// or https://.")

    return errors


# ---------------------------------------------------------------------------
# ICS generation
# ---------------------------------------------------------------------------

def fold_ics_line(line: str) -> str:
    """RFC 5545 line folding: lines must be ≤75 octets, continued with CRLF + space."""
    if len(line.encode("utf-8")) <= 75:
        return line
    result = []
    current = ""
    for char in line:
        candidate = current + char
        if len(candidate.encode("utf-8")) > 75:
            result.append(current)
            current = " " + char  # continuation line starts with a space
        else:
            current = candidate
    if current:
        result.append(current)
    return "\r\n".join(result)


def escape_ics_text(text: str) -> str:
    """Escape special characters in ICS text values per RFC 5545 §3.3.11."""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "")
    return text


def build_ics(data: dict) -> str:
    """Generate an RFC 5545-compliant ICS calendar file as a string.

    Args:
        data: Dictionary with the following keys:
            title          (str, required)
            start_dt       (datetime, required)
            end_dt         (datetime, required)
            timezone       (str, IANA name, required)
            all_day        (bool, default False)
            location       (str, optional)
            meeting_url    (str, optional)
            description    (str, optional)
            organizer_name (str, required)
            organizer_email(str, required)
            reminder_minutes (int, optional — None means no alarm)
            campaign_id    (str, optional — stored as X-CAMPAIGN-ID)
            landing_page_url (str, optional — appended to description)
            uid            (str, optional — generated if absent)

    Returns:
        A CRLF-terminated ICS string ready for download.
    """
    tz_name = data["timezone"]
    all_day = data.get("all_day", False)
    start = data["start_dt"]
    end = data["end_dt"]

    # Attach timezone if naive datetimes
    if not all_day:
        if isinstance(start, datetime) and start.tzinfo is None:
            start = localize(start, tz_name)
        if isinstance(end, datetime) and end.tzinfo is None:
            end = localize(end, tz_name)

    # For all-day events, ICS end date is exclusive (day after last day)
    if all_day:
        if isinstance(end, datetime):
            end_date = end.date() + timedelta(days=1)
        else:
            end_date = end + timedelta(days=1)
        dtstart = f"DTSTART;VALUE=DATE:{start.strftime(ICS_DATE_FORMAT) if isinstance(start, datetime) else start.strftime(ICS_DATE_FORMAT)}"
        dtend = f"DTEND;VALUE=DATE:{end_date.strftime(ICS_DATE_FORMAT)}"
    else:
        dtstart = f"DTSTART:{format_ics_datetime(start)}"
        dtend = f"DTEND:{format_ics_datetime(end)}"

    # Build description — append meeting URL and landing page URL if provided
    desc_parts = []
    if data.get("description", "").strip():
        desc_parts.append(data["description"].strip())
    if data.get("meeting_url", "").strip():
        desc_parts.append(f"Join: {data['meeting_url'].strip()}")
    if data.get("landing_page_url", "").strip():
        desc_parts.append(f"More info: {data['landing_page_url'].strip()}")
    description = "\n".join(desc_parts)

    # Build location — prefer physical, append meeting URL if virtual
    location = data.get("location", "").strip()
    if data.get("meeting_url", "").strip() and not location:
        location = data["meeting_url"].strip()

    # UID — use provided or generate a new one
    uid = data.get("uid") or f"{uuid.uuid4()}@marketing-calendar-hold-builder"

    # DTSTAMP — current UTC timestamp
    from datetime import timezone as _tz
    now_utc = datetime.now(_tz.utc)
    dtstamp = now_utc.strftime(ICS_DATETIME_FORMAT) + "Z"

    # Assemble lines
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Marketing Calendar Hold Builder//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        fold_ics_line(f"SUMMARY:{escape_ics_text(data['title'])}"),
        fold_ics_line(dtstart),
        fold_ics_line(dtend),
        fold_ics_line(f"DTSTAMP:{dtstamp}"),
        fold_ics_line(f"UID:{uid}"),
        fold_ics_line(f"ORGANIZER;CN={escape_ics_text(data['organizer_name'])}:mailto:{data['organizer_email']}"),
    ]

    if location:
        lines.append(fold_ics_line(f"LOCATION:{escape_ics_text(location)}"))

    if description:
        lines.append(fold_ics_line(f"DESCRIPTION:{escape_ics_text(description)}"))

    if data.get("meeting_url", "").strip():
        lines.append(fold_ics_line(f"URL:{data['meeting_url'].strip()}"))

    if data.get("campaign_id", "").strip():
        lines.append(fold_ics_line(f"X-CAMPAIGN-ID:{escape_ics_text(data['campaign_id'].strip())}"))

    # VALARM — reminder
    reminder_minutes = data.get("reminder_minutes")
    if reminder_minutes is not None:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            fold_ics_line(f"DESCRIPTION:Reminder: {escape_ics_text(data['title'])}"),
            f"TRIGGER:-PT{int(reminder_minutes)}M",
            "END:VALARM",
        ]

    lines += [
        "END:VEVENT",
        "END:VCALENDAR",
    ]

    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------------------
# Google Calendar URL
# ---------------------------------------------------------------------------

def build_google_url(data: dict) -> str:
    """Build a Google Calendar 'add event' URL.

    No authentication required — opens pre-filled new-event form.

    Returns:
        Fully URL-encoded string.
    """
    tz_name = data["timezone"]
    all_day = data.get("all_day", False)
    start = data["start_dt"]
    end = data["end_dt"]

    if all_day:
        # Google uses YYYYMMDD for all-day
        if isinstance(start, datetime):
            start = start.date()
        if isinstance(end, datetime):
            end = end.date()
        dates = f"{start.strftime(ICS_DATE_FORMAT)}/{end.strftime(ICS_DATE_FORMAT)}"
    else:
        if isinstance(start, datetime) and start.tzinfo is None:
            start = localize(start, tz_name)
        if isinstance(end, datetime) and end.tzinfo is None:
            end = localize(end, tz_name)
        # Google expects UTC datetime in the 'dates' param
        start_utc = to_utc(start).strftime(ICS_DATETIME_FORMAT) + "Z"
        end_utc = to_utc(end).strftime(ICS_DATETIME_FORMAT) + "Z"
        dates = f"{start_utc}/{end_utc}"

    # Build details field
    details_parts = []
    if data.get("description", "").strip():
        details_parts.append(data["description"].strip())
    if data.get("meeting_url", "").strip():
        details_parts.append(f"Join: {data['meeting_url'].strip()}")
    if data.get("landing_page_url", "").strip():
        details_parts.append(f"More info: {data['landing_page_url'].strip()}")
    details = "\n".join(details_parts)

    location = data.get("location", "").strip()
    if not location and data.get("meeting_url", "").strip():
        location = data["meeting_url"].strip()

    params = {
        "action": "TEMPLATE",
        "text": data["title"],
        "dates": dates,
    }
    if details:
        params["details"] = details
    if location:
        params["location"] = location
    if not all_day:
        params["ctz"] = tz_name

    return GOOGLE_CAL_BASE + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


# ---------------------------------------------------------------------------
# Outlook Calendar URL
# ---------------------------------------------------------------------------

def build_outlook_url(data: dict) -> str:
    """Build an Outlook Web App 'add event' URL.

    Uses outlook.live.com deeplink — works for personal Outlook accounts
    without OAuth. Office 365 users can swap the base URL to
    https://outlook.office.com/calendar/0/deeplink/compose.

    Returns:
        Fully URL-encoded string.
    """
    tz_name = data["timezone"]
    all_day = data.get("all_day", False)
    start = data["start_dt"]
    end = data["end_dt"]

    if all_day:
        if isinstance(start, datetime):
            start = start.date()
        if isinstance(end, datetime):
            end = end.date()
        # Outlook all-day: ISO 8601 date strings
        start_str = start.isoformat()
        end_str = end.isoformat()
    else:
        if isinstance(start, datetime) and start.tzinfo is None:
            start = localize(start, tz_name)
        if isinstance(end, datetime) and end.tzinfo is None:
            end = localize(end, tz_name)
        # Outlook wants ISO 8601 UTC
        start_str = to_utc(start).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        end_str = to_utc(end).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    body_parts = []
    if data.get("description", "").strip():
        body_parts.append(data["description"].strip())
    if data.get("meeting_url", "").strip():
        body_parts.append(f"Join: {data['meeting_url'].strip()}")
    if data.get("landing_page_url", "").strip():
        body_parts.append(f"More info: {data['landing_page_url'].strip()}")
    body = "\n".join(body_parts)

    location = data.get("location", "").strip()
    if not location and data.get("meeting_url", "").strip():
        location = data["meeting_url"].strip()

    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": data["title"],
        "startdt": start_str,
        "enddt": end_str,
        "allday": "true" if all_day else "false",
    }
    if body:
        params["body"] = body
    if location:
        params["location"] = location

    return OUTLOOK_CAL_BASE + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


# ---------------------------------------------------------------------------
# HTML "Add to Calendar" button (Marketo-safe)
# ---------------------------------------------------------------------------

def build_html_button(data: dict, button_label: str = "Add to Calendar") -> str:
    """Generate a self-contained HTML 'Add to Calendar' dropdown button.

    The output is a single-file HTML snippet safe for pasting into Marketo
    email templates. It uses only inline styles and no external dependencies.

    The dropdown offers:
      - Google Calendar
      - Outlook / Office 365
      - Download ICS (data URI — works in most email clients that render HTML)

    Args:
        data: Event data dict (same as build_ics).
        button_label: Text shown on the button.

    Returns:
        An HTML string with properly escaped attribute values.
    """
    google_url = html.escape(build_google_url(data), quote=True)
    outlook_url = html.escape(build_outlook_url(data), quote=True)

    # ICS as a data URI for direct download
    ics_content = build_ics(data)
    import base64
    ics_b64 = base64.b64encode(ics_content.encode("utf-8")).decode("ascii")
    ics_data_uri = f"data:text/calendar;charset=utf-8;base64,{ics_b64}"
    safe_title = html.escape(data.get("title", "event"), quote=True)

    snippet = f"""<!-- Marketing Calendar Hold Builder: Add to Calendar Button -->
<div style="display:inline-block;position:relative;font-family:Arial,sans-serif;">
  <a href="#"
     onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='block'?'none':'block';return false;"
     style="display:inline-block;padding:10px 20px;background-color:#0066CC;color:#ffffff;
            text-decoration:none;border-radius:4px;font-size:14px;font-weight:bold;
            cursor:pointer;">
    {html.escape(button_label)}
  </a>
  <div style="display:none;position:absolute;top:100%;left:0;z-index:9999;
              background:#ffffff;border:1px solid #cccccc;border-radius:4px;
              box-shadow:0 2px 8px rgba(0,0,0,0.15);min-width:180px;margin-top:4px;">
    <a href="{google_url}" target="_blank" rel="noopener"
       style="display:block;padding:10px 16px;color:#333333;text-decoration:none;
              font-size:13px;border-bottom:1px solid #eeeeee;">
      Google Calendar
    </a>
    <a href="{outlook_url}" target="_blank" rel="noopener"
       style="display:block;padding:10px 16px;color:#333333;text-decoration:none;
              font-size:13px;border-bottom:1px solid #eeeeee;">
      Outlook / Office 365
    </a>
    <a href="{ics_data_uri}" download="{safe_title}.ics"
       style="display:block;padding:10px 16px;color:#333333;text-decoration:none;
              font-size:13px;">
      Apple / Other (.ics)
    </a>
  </div>
</div>"""
    return snippet


# ---------------------------------------------------------------------------
# UTM URL builder
# ---------------------------------------------------------------------------

def build_utm_url(base_url: str, utm: dict) -> str:
    """Append UTM parameters to a URL, skipping empty values.

    Args:
        base_url: The landing page URL.
        utm: Dict with keys: utm_source, utm_medium, utm_campaign,
             utm_term, utm_content.

    Returns:
        URL with UTM parameters appended.
    """
    if not base_url:
        return ""
    clean = {k: v for k, v in utm.items() if v and v.strip()}
    if not clean:
        return base_url
    sep = "&" if "?" in base_url else "?"
    return base_url + sep + urllib.parse.urlencode(clean)


# ---------------------------------------------------------------------------
# Human-readable event preview
# ---------------------------------------------------------------------------

def build_event_preview(data: dict) -> str:
    """Build a human-readable plain-text event summary.

    Returns:
        Multi-line string suitable for display in a text area or email.
    """
    tz_name = data.get("timezone", "UTC")
    all_day = data.get("all_day", False)
    start = data.get("start_dt")
    end = data.get("end_dt")

    if all_day:
        if isinstance(start, datetime):
            start = start.date()
        if isinstance(end, datetime):
            end = end.date()
        time_str = f"{start.strftime('%B %d, %Y')} – {end.strftime('%B %d, %Y')} (All day)"
    else:
        if start and isinstance(start, datetime):
            if start.tzinfo is None:
                try:
                    start = localize(start, tz_name)
                    end = localize(end, tz_name)
                except Exception:
                    pass
            fmt = "%B %d, %Y at %I:%M %p"
            time_str = f"{start.strftime(fmt)} – {end.strftime(fmt)} ({tz_name})"
        else:
            time_str = "N/A"

    lines = [
        f"📅  {data.get('title', '')}",
        f"",
        f"When:       {time_str}",
    ]
    if data.get("location", "").strip():
        lines.append(f"Location:   {data['location'].strip()}")
    if data.get("meeting_url", "").strip():
        lines.append(f"Join URL:   {data['meeting_url'].strip()}")
    if data.get("description", "").strip():
        lines.append(f"")
        lines.append(f"Details:")
        for line in data["description"].strip().splitlines():
            lines.append(f"  {line}")
    if data.get("organizer_name", "").strip() or data.get("organizer_email", "").strip():
        lines.append(f"")
        lines.append(f"Organizer:  {data.get('organizer_name','').strip()} <{data.get('organizer_email','').strip()}>")
    if data.get("campaign_id", "").strip():
        lines.append(f"Campaign:   {data['campaign_id'].strip()}")
    if data.get("landing_page_url", "").strip():
        lines.append(f"Landing:    {data['landing_page_url'].strip()}")

    return "\n".join(lines)
