"""
slack_bot.py
------------
CalBot — Marketing Calendar Hold Builder Slack Bot

Monitors a Slack channel for campaign brief links (Google Docs) or PDF uploads,
parses them with AI via the G2 LiteLLM proxy, and posts back calendar assets.

How it works:
  1. Someone posts a Google Doc link or uploads a PDF to a watched channel
  2. CalBot reads the brief and parses it with AI (claude-haiku-4-5)
  3. CalBot replies with a formatted summary + Google Calendar, Outlook, and ICS links
  4. The event is saved to team_calendar.json for the shared Team Calendar

Setup:
  1. Add to .env or environment:
       SLACK_BOT_TOKEN=xoxb-...
       SLACK_APP_TOKEN=xapp-...
       LITELLM_PROXY_URL=https://llmproxy.g2.com
       LITELLM_API_KEY=...
       STREAMLIT_APP_URL=https://your-app.streamlit.app  (optional, for deep links)

  2. Enable Socket Mode in your Slack app settings
  3. Subscribe to event: message.channels
  4. Run: python slack_bot.py

Requires:
  slack-bolt>=1.18.0
  python-dotenv>=1.0.0
  (plus existing requirements.txt deps)
"""

import os
import re
import json
import tempfile
import logging
from datetime import datetime
from pathlib import Path

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

from brief_utils import (
    fetch_doc_text,
    extract_pdf_text,
    parse_brief,
    parse_brief_with_ai,
)
from calendar_utils import (
    build_ics,
    build_google_url,
    build_outlook_url,
    localize,
    validate_event,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()  # Load from .env file if present

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
LITELLM_PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "")
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", "")
STREAMLIT_APP_URL = os.environ.get("STREAMLIT_APP_URL", "")

CALENDAR_FILE = Path("team_calendar.json")
MAX_CALENDAR = 500

# Event type → color mapping (matches the Streamlit app)
EVENT_COLORS = {
    "Webinar":          "#0066CC",
    "In-Person Event":  "#28A745",
    "Product Launch":   "#FF6B35",
    "Customer Session": "#9B59B6",
    "Internal Meeting": "#6C757D",
    "Other":            "#17A2B8",
}

# ---------------------------------------------------------------------------
# Slack app
# ---------------------------------------------------------------------------

app = App(token=SLACK_BOT_TOKEN)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_google_doc_url(text: str) -> str | None:
    """Return the first Google Docs URL found in text, or None."""
    match = re.search(
        r"https://docs\.google\.com/document/d/[a-zA-Z0-9_-]+[^\s>]*",
        text
    )
    return match.group(0) if match else None


def save_to_team_calendar(event_data: dict, google_url: str, outlook_url: str) -> None:
    """Save the parsed event to the shared team_calendar.json."""
    start_dt = event_data.get("start_dt")
    end_dt = event_data.get("end_dt")

    entry = {
        "title": event_data.get("title", ""),
        "event_type": event_data.get("event_type", "Other"),
        "start_iso": start_dt.isoformat() if start_dt else "",
        "end_iso": end_dt.isoformat() if end_dt else "",
        "timezone": event_data.get("timezone", ""),
        "all_day": event_data.get("all_day", False),
        "location": event_data.get("location", ""),
        "meeting_url": event_data.get("meeting_url", ""),
        "description": event_data.get("description", ""),
        "organizer_name": event_data.get("organizer_name", ""),
        "campaign_id": event_data.get("campaign_id", ""),
        "landing_page_url": event_data.get("landing_page_url", ""),
        "google_url": google_url,
        "outlook_url": outlook_url,
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "source": "slack",
    }

    existing = []
    if CALENDAR_FILE.exists():
        try:
            existing = json.loads(CALENDAR_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            existing = []

    existing.insert(0, entry)
    existing = existing[:MAX_CALENDAR]

    try:
        CALENDAR_FILE.write_text(json.dumps(existing, indent=2))
        logger.info(f"Saved event to team calendar: {entry['title']}")
    except OSError as e:
        logger.warning(f"Could not save to team calendar: {e}")


def format_datetime(dt: datetime | None, tz: str = "") -> str:
    """Format a datetime for Slack display."""
    if not dt:
        return "TBD"
    try:
        if tz and dt.tzinfo is None:
            dt = localize(dt, tz)
        return dt.strftime("%A, %B %d, %Y at %I:%M %p") + (f" {tz}" if tz else "")
    except Exception:
        return dt.strftime("%B %d, %Y at %I:%M %p")


def build_slack_blocks(fields: dict, google_url: str, outlook_url: str) -> list:
    """Build Slack Block Kit blocks for the calendar hold response."""
    title = fields.get("title", "Untitled Event")
    event_type = fields.get("event_type", "Other")
    color = EVENT_COLORS.get(event_type, "#17A2B8")
    tz = fields.get("timezone", "")
    start_dt = fields.get("start_dt")
    end_dt = fields.get("end_dt")
    location = fields.get("location", "")
    meeting_url = fields.get("meeting_url", "")
    organizer_name = fields.get("organizer_name", "")
    campaign_id = fields.get("campaign_id", "")

    start_str = format_datetime(start_dt, tz)
    end_str = format_datetime(end_dt, tz)

    # Build detail lines
    details = []
    details.append(f"🗓️  *{start_str}*")
    if end_dt:
        details.append(f"⏱️  Ends: {end_str}")
    if location:
        details.append(f"📍  {location}")
    if meeting_url:
        details.append(f"🔗  <{meeting_url}|Join virtual meeting>")
    if organizer_name:
        details.append(f"👤  {organizer_name}")
    if campaign_id:
        details.append(f"🏷️  {campaign_id}")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📅 {title}", "emoji": True},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"*Event type:* {event_type}"}
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(details) or "_No details found_"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Add to Calendar:*"},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📅 Google Calendar", "emoji": True},
                    "url": google_url,
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📧 Outlook", "emoji": True},
                    "url": outlook_url,
                },
            ],
        },
    ]

    # Add Streamlit app deep link if configured
    if STREAMLIT_APP_URL:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"<{STREAMLIT_APP_URL}|Open Calendar Hold Builder> to download ICS or get the HTML button",
                }
            ],
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": "_Review the details and adjust in the app if needed._"}
        ],
    })

    return blocks


def process_brief(text: str, say, thread_ts: str = None) -> None:
    """Parse brief text and post the calendar hold response."""
    # Use AI if configured, otherwise fall back to regex
    try:
        if LITELLM_PROXY_URL and LITELLM_API_KEY:
            logger.info("Parsing brief with AI...")
            fields = parse_brief_with_ai(text, LITELLM_PROXY_URL, LITELLM_API_KEY)
        else:
            logger.info("Parsing brief with regex (AI not configured)...")
            fields = parse_brief(text)
    except Exception as e:
        say(
            text=f"⚠️ Could not parse the brief: {e}",
            thread_ts=thread_ts,
        )
        return

    # Check we got at least a title
    if not fields.get("title"):
        say(
            text="⚠️ I couldn't find event details in that brief. Make sure it contains an event name, date, and time.",
            thread_ts=thread_ts,
        )
        return

    # Build calendar URLs
    try:
        google_url = build_google_url(fields)
        outlook_url = build_outlook_url(fields)
    except Exception as e:
        say(
            text=f"⚠️ Could not build calendar links: {e}",
            thread_ts=thread_ts,
        )
        return

    # Save to team calendar
    save_to_team_calendar(fields, google_url, outlook_url)

    # Post response
    blocks = build_slack_blocks(fields, google_url, outlook_url)
    say(
        text=f"📅 Calendar hold created for: {fields.get('title', 'your event')}",
        blocks=blocks,
        thread_ts=thread_ts,
    )
    logger.info(f"Posted calendar hold for: {fields.get('title')}")


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

@app.event("message")
def handle_message(event, say, client) -> None:
    """Handle incoming channel messages.

    Triggers on:
      - Messages containing a Google Docs URL
      - Messages with a PDF file attachment
    """
    # Ignore bot messages to prevent loops
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return

    text = event.get("text", "")
    thread_ts = event.get("ts")  # Reply in thread

    # ── Google Doc link ───────────────────────────────────────────────────
    doc_url = is_google_doc_url(text)
    if doc_url:
        logger.info(f"Detected Google Doc URL: {doc_url}")
        say(text="📄 Found a brief — parsing it now...", thread_ts=thread_ts)
        try:
            brief_text = fetch_doc_text(doc_url)
            process_brief(brief_text, say, thread_ts=thread_ts)
        except ValueError as e:
            say(text=f"⚠️ Could not fetch the doc: {e}", thread_ts=thread_ts)
        return

    # ── PDF file upload ───────────────────────────────────────────────────
    files = event.get("files", [])
    for file in files:
        if file.get("mimetype") == "application/pdf":
            logger.info(f"Detected PDF upload: {file.get('name')}")
            say(text="📄 Found a PDF brief — parsing it now...", thread_ts=thread_ts)
            try:
                # Download the PDF using the bot token
                import requests as _requests
                response = _requests.get(
                    file["url_private"],
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    timeout=30,
                )
                response.raise_for_status()
                brief_text = extract_pdf_text(response.content)
                process_brief(brief_text, say, thread_ts=thread_ts)
            except Exception as e:
                say(text=f"⚠️ Could not read the PDF: {e}", thread_ts=thread_ts)
            return


@app.event("app_mention")
def handle_mention(event, say) -> None:
    """Respond to @CalBot mentions with usage help."""
    say(
        text="👋 Hi! I'm CalBot. Here's how to use me:",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "👋 *Hi! I'm CalBot.*\n\n"
                        "Drop a campaign brief in this channel and I'll generate calendar holds automatically.\n\n"
                        "*I accept:*\n"
                        "• 🔗 A Google Docs link _(doc must be shared as 'Anyone with the link can view')_\n"
                        "• 📎 A PDF file upload\n\n"
                        "I'll reply with Google Calendar and Outlook links, and add the event to the shared Team Calendar."
                    ),
                },
            }
        ],
        thread_ts=event.get("ts"),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not SLACK_BOT_TOKEN:
        raise ValueError("SLACK_BOT_TOKEN is not set. Add it to your .env file.")
    if not SLACK_APP_TOKEN:
        raise ValueError("SLACK_APP_TOKEN is not set. Add it to your .env file.")

    logger.info("Starting CalBot in Socket Mode...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
