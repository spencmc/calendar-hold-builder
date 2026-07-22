"""
app.py
------
Marketing Calendar Hold Builder — Streamlit front-end.

Run locally:
    streamlit run app.py

Generates:
  - Downloadable ICS file
  - Google Calendar add-event link
  - Outlook Web App add-event link
  - Copyable plain-text links
  - HTML "Add to Calendar" button (Marketo-safe)
  - Human-readable event preview
"""

import json
import zoneinfo
from datetime import datetime, date, time, timedelta
from pathlib import Path

import streamlit as st

import db
from brief_utils import fetch_doc_text, extract_pdf_text, parse_brief, parse_brief_with_ai
from calendar_utils import (
    build_ics,
    build_google_url,
    build_outlook_url,
    build_html_button,
    build_utm_url,
    build_event_preview,
    validate_event,
    localize,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Marketing Calendar Hold Builder",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HISTORY_FILE = Path("recent_events.json")
CALENDAR_FILE = Path("team_calendar.json")
MAX_HISTORY = 10    # Recent events in sidebar
MAX_CALENDAR = 500  # Max events stored in team calendar

# ---------------------------------------------------------------------------
# All IANA timezones (sorted, common ones first)
# ---------------------------------------------------------------------------

COMMON_TZ = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "America/Anchorage",
    "Pacific/Honolulu",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Kolkata",
    "Australia/Sydney",
    "UTC",
]

ALL_TZ = sorted(zoneinfo.available_timezones())
TZ_OPTIONS = COMMON_TZ + ["─────────────────"] + [z for z in ALL_TZ if z not in COMMON_TZ]

# ---------------------------------------------------------------------------
# Event templates
# ---------------------------------------------------------------------------

TEMPLATES = {
    "── Select a template ──": {},
    "Webinar": {
        "title": "Webinar: [Topic Name]",
        "description": (
            "Join us for an informative webinar on [Topic Name].\n\n"
            "What you'll learn:\n"
            "• [Key point 1]\n"
            "• [Key point 2]\n"
            "• [Key point 3]\n\n"
            "Seats are limited — register today!"
        ),
        "location": "",
        "reminder_minutes": 15,
        "campaign_id": "WEB-2024-",
    },
    "In-Person Event": {
        "title": "[Event Name]",
        "description": (
            "Join us in person for [Event Name].\n\n"
            "Agenda:\n"
            "• [Session 1]\n"
            "• [Session 2]\n"
            "• Networking\n\n"
            "Please arrive 10 minutes early."
        ),
        "location": "[Venue Name], [Address], [City, State ZIP]",
        "reminder_minutes": 60,
        "campaign_id": "EVT-2024-",
    },
    "Product Launch": {
        "title": "[Product Name] Launch",
        "description": (
            "We're excited to announce the launch of [Product Name]!\n\n"
            "Join us to learn about new features, see live demos, and hear "
            "from the product team.\n\n"
            "Don't miss this exciting milestone."
        ),
        "location": "",
        "reminder_minutes": 30,
        "campaign_id": "LAUNCH-2024-",
    },
    "Customer Session": {
        "title": "Customer Session: [Customer Name]",
        "description": (
            "Dedicated session for [Customer Name].\n\n"
            "Agenda:\n"
            "• Review & check-in\n"
            "• Product updates\n"
            "• Q&A\n\n"
            "Please come prepared with questions."
        ),
        "location": "",
        "reminder_minutes": 15,
        "campaign_id": "CUST-2024-",
    },
    "Internal Meeting": {
        "title": "Team Sync: [Topic]",
        "description": (
            "Recurring team sync to discuss [Topic].\n\n"
            "Agenda:\n"
            "• Status updates\n"
            "• Blockers\n"
            "• Action items"
        ),
        "location": "",
        "reminder_minutes": 10,
        "campaign_id": "INT-2024-",
    },
}

# Reminder options — displayed as human-friendly labels, stored as int minutes
REMINDER_OPTIONS = {
    "No reminder": None,
    "5 minutes before": 5,
    "10 minutes before": 10,
    "15 minutes before": 15,
    "30 minutes before": 30,
    "1 hour before": 60,
    "2 hours before": 120,
    "1 day before": 1440,
    "2 days before": 2880,
}

# ---------------------------------------------------------------------------
# Recent events persistence (no PII stored)
# ---------------------------------------------------------------------------

def load_history() -> list[dict]:
    """Load recent event history from local JSON file."""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_to_history(entry: dict) -> None:
    """Persist a sanitized event entry (no PII) to local history sidebar."""
    safe_entry = {
        "title": entry.get("title", ""),
        "start_str": entry.get("start_str", ""),
        "end_str": entry.get("end_str", ""),
        "timezone": entry.get("timezone", ""),
        "campaign_id": entry.get("campaign_id", ""),
        "saved_at": datetime.utcnow().isoformat() + "Z",
    }
    history = load_history()
    history.insert(0, safe_entry)
    history = history[:MAX_HISTORY]
    try:
        HISTORY_FILE.write_text(json.dumps(history, indent=2))
    except OSError:
        pass


def save_to_team_calendar(entry: dict) -> None:
    """Save a full event entry to Supabase shared team calendar."""
    start_dt = entry.get("start_dt")
    end_dt = entry.get("end_dt")

    cal_entry = {
        "title": entry.get("title", ""),
        "event_type": entry.get("event_type", "Other"),
        "start_iso": start_dt.isoformat() if start_dt else "",
        "end_iso": end_dt.isoformat() if end_dt else "",
        "timezone": entry.get("timezone", ""),
        "all_day": entry.get("all_day", False),
        "location": entry.get("location", ""),
        "meeting_url": entry.get("meeting_url", ""),
        "description": entry.get("description", ""),
        "organizer_name": entry.get("organizer_name", ""),
        "campaign_id": entry.get("campaign_id", ""),
        "landing_page_url": entry.get("landing_page_url", ""),
        "google_url": entry.get("google_url", ""),
        "outlook_url": entry.get("outlook_url", ""),
        "source": "app",
    }

    db.save_event(cal_entry)


# ---------------------------------------------------------------------------
# Clipboard copy helper (uses Streamlit + JS)
# ---------------------------------------------------------------------------

COPY_BUTTON_COUNTER = 0  # used to give each copy button a unique key


def copy_button(text: str, label: str = "📋 Copy", key: str = "") -> None:
    """Render a small copy-to-clipboard button using Streamlit components."""
    global COPY_BUTTON_COUNTER
    COPY_BUTTON_COUNTER += 1
    unique_key = key or f"copy_{COPY_BUTTON_COUNTER}"

    # Encode text for safe embedding in JS
    import json as _json
    js_text = _json.dumps(text)  # proper JS string with escaping

    copy_js = f"""
    <script>
    function copyText_{unique_key}() {{
        var text = {js_text};
        if (navigator.clipboard && window.isSecureContext) {{
            navigator.clipboard.writeText(text).then(function() {{
                var btn = document.getElementById('btn_{unique_key}');
                var orig = btn.innerText;
                btn.innerText = '✅ Copied!';
                setTimeout(function() {{ btn.innerText = orig; }}, 1500);
            }});
        }} else {{
            var ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            var btn = document.getElementById('btn_{unique_key}');
            var orig = btn.innerText;
            btn.innerText = '✅ Copied!';
            setTimeout(function() {{ btn.innerText = orig; }}, 1500);
        }}
    }}
    </script>
    <button id="btn_{unique_key}"
            onclick="copyText_{unique_key}()"
            style="padding:4px 12px;font-size:12px;cursor:pointer;
                   border:1px solid #ccc;border-radius:4px;background:#f8f8f8;">
        {label}
    </button>
    """
    st.components.v1.html(copy_js, height=36)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    # ── Header ──────────────────────────────────────────────────────────────
    st.title("📅 Marketing Calendar Hold Builder")
    st.caption(
        "Create calendar assets for webinars, events, launches, customer sessions, "
        "and internal meetings. Generates ICS files and add-to-calendar links for "
        "Google, Outlook, and Apple Calendar."
    )
    st.divider()

    # ── Sidebar: Template picker + recent events ─────────────────────────────
    with st.sidebar:
        st.header("Templates")
        selected_template = st.selectbox(
            "Load a template",
            options=list(TEMPLATES.keys()),
            key="template_select",
            help="Pre-fill the form with a starting point for common event types.",
        )

        st.divider()
        st.header("Recent Events")
        history = load_history()
        if history:
            for item in history:
                with st.expander(f"📌 {item.get('title', 'Untitled')[:40]}"):
                    st.caption(f"**When:** {item.get('start_str', '')} ({item.get('timezone', '')})")
                    if item.get("campaign_id"):
                        st.caption(f"**Campaign:** {item['campaign_id']}")
                    st.caption(f"Saved: {item.get('saved_at', '')[:10]}")
        else:
            st.caption("No recent events yet. Generated events will appear here.")

    # ── Determine template defaults ──────────────────────────────────────────
    tmpl = TEMPLATES.get(selected_template, {})

    # ── Import from Google Doc brief ─────────────────────────────────────────
    # Store parsed brief fields in session state so they survive form rerender
    if "brief_fields" not in st.session_state:
        st.session_state.brief_fields = {}

    with st.expander("📄 Import from Brief (Google Doc or PDF)", expanded=False):
        st.caption(
            "Import a campaign brief to auto-fill the form using AI. "
            "Supports Google Docs and PDF uploads. "
            "Google Docs must be shared as **'Anyone with the link can view'** — "
            "open the doc, click Share, and set access to 'Anyone with the link'."
        )

        # Check if AI is configured via Streamlit secrets
        _proxy_url = st.secrets.get("LITELLM_PROXY_URL", "")
        _proxy_key = st.secrets.get("LITELLM_API_KEY", "")
        _ai_available = bool(_proxy_url and _proxy_key)

        if _ai_available:
            st.success("✨ AI-powered parsing enabled", icon="🤖")
        else:
            st.info("Using standard parsing. AI parsing will be enabled once configured.", icon="ℹ️")

        # Source selector
        import_source = st.radio(
            "Brief source",
            options=["Google Doc URL", "Upload PDF"],
            horizontal=True,
            key="import_source",
        )

        brief_text = None

        if import_source == "Google Doc URL":
            doc_url_input = st.text_input(
                "Google Doc URL",
                placeholder="https://docs.google.com/document/d/YOUR_DOC_ID/edit",
                key="doc_url_input",
            )
            if st.button("🔍 Import Brief", key="import_brief_btn"):
                if not doc_url_input.strip():
                    st.error("Please paste your Google Doc URL.")
                else:
                    with st.spinner("Fetching brief..."):
                        try:
                            brief_text = fetch_doc_text(doc_url_input.strip())
                        except ValueError as e:
                            st.error(str(e))
                            brief_text = None

        else:  # PDF upload
            uploaded_pdf = st.file_uploader(
                "Upload PDF brief",
                type=["pdf"],
                key="pdf_uploader",
                help="Upload a campaign brief as a PDF file.",
            )
            if st.button("🔍 Import Brief", key="import_pdf_btn"):
                if not uploaded_pdf:
                    st.error("Please upload a PDF file.")
                else:
                    with st.spinner("Reading PDF..."):
                        try:
                            brief_text = extract_pdf_text(uploaded_pdf.read())
                        except ValueError as e:
                            st.error(str(e))
                            brief_text = None

        # Parse the brief text if we have it
        if brief_text:
            with st.spinner("Parsing brief with AI..." if _ai_available else "Parsing brief..."):
                try:
                    if _ai_available:
                        fields = parse_brief_with_ai(brief_text, _proxy_url, _proxy_key)
                    else:
                        fields = parse_brief(brief_text)
                    st.session_state.brief_fields = fields
                    found = [k for k, v in fields.items() if v]
                    st.success(
                        f"✅ Brief imported! Detected: {', '.join(found)}. "
                        "Review and adjust the form below before generating."
                    )
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

    # Merge brief fields into template defaults (brief takes priority)
    brief = st.session_state.brief_fields
    if brief:
        for key in ["title", "location", "meeting_url", "description",
                    "organizer_name", "organizer_email", "campaign_id", "landing_page_url"]:
            if brief.get(key):
                tmpl[key] = brief[key]

    # ── Form ─────────────────────────────────────────────────────────────────
    with st.form("event_form", clear_on_submit=False):
        # ── Event Details ──────────────────────────────────────────────────
        st.subheader("Event Details")

        col_title, col_type = st.columns([3, 1])
        with col_title:
            title = st.text_input(
                "Event Title *",
                value=tmpl.get("title", ""),
                placeholder="e.g. Q3 Product Webinar",
                help="Required. The title will appear in all calendar apps.",
            )
        with col_type:
            event_type_options = ["Webinar", "In-Person Event", "Product Launch", "Customer Session", "Internal Meeting", "Other"]
            # Pre-select based on template
            default_type_index = 0
            if selected_template in event_type_options:
                default_type_index = event_type_options.index(selected_template)
            event_type = st.selectbox(
                "Event Type",
                options=event_type_options,
                index=default_type_index,
                help="Used to color-code the event on the Team Calendar.",
            )

        col_allday, _ = st.columns([1, 3])
        with col_allday:
            all_day = st.checkbox("All-day event", value=False)

        # Use brief dates if available, otherwise default to 1 week from today
        _default_start = date.today() + timedelta(days=7)
        _default_end = date.today() + timedelta(days=7)
        _default_start_time = time(10, 0)
        _default_end_time = time(11, 0)

        if brief.get("start_dt") and isinstance(brief["start_dt"], datetime):
            _default_start = brief["start_dt"].date()
            _default_start_time = brief["start_dt"].time().replace(second=0, microsecond=0)
        if brief.get("end_dt") and isinstance(brief["end_dt"], datetime):
            _default_end = brief["end_dt"].date()
            _default_end_time = brief["end_dt"].time().replace(second=0, microsecond=0)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Start Date & Time** *")
            start_date = st.date_input(
                "Start date",
                value=_default_start,
                label_visibility="collapsed",
                key="start_date",
            )
            if not all_day:
                start_time_val = st.time_input(
                    "Start time",
                    value=_default_start_time,
                    label_visibility="collapsed",
                    key="start_time",
                    step=300,  # 5-minute increments
                )
            else:
                start_time_val = time(0, 0)

        with col2:
            st.markdown("**End Date & Time** *")
            end_date = st.date_input(
                "End date",
                value=_default_end,
                label_visibility="collapsed",
                key="end_date",
            )
            if not all_day:
                end_time_val = st.time_input(
                    "End time",
                    value=_default_end_time,
                    label_visibility="collapsed",
                    key="end_time",
                    step=300,
                )
            else:
                end_time_val = time(0, 0)

        # Timezone
        default_tz = "America/Chicago"
        tz_index = TZ_OPTIONS.index(default_tz) if default_tz in TZ_OPTIONS else 0
        timezone = st.selectbox(
            "Time Zone *",
            options=TZ_OPTIONS,
            index=tz_index,
            help="Select the IANA timezone for this event. Common timezones are listed first.",
        )
        # Guard against the separator being selected
        if timezone.startswith("─"):
            timezone = "UTC"

        # ── Location & Virtual ────────────────────────────────────────────
        st.subheader("Location")
        col3, col4 = st.columns(2)
        with col3:
            location = st.text_input(
                "Physical Location",
                value=tmpl.get("location", ""),
                placeholder="e.g. 100 Main St, Chicago, IL 60601",
                help="Leave blank for virtual-only events.",
            )
        with col4:
            meeting_url = st.text_input(
                "Virtual Meeting URL",
                value="",
                placeholder="https://zoom.us/j/...",
                help="Zoom, Teams, Google Meet, etc. Leave blank for in-person events.",
            )

        # ── Description ───────────────────────────────────────────────────
        st.subheader("Description")
        description = st.text_area(
            "Event Description",
            value=tmpl.get("description", ""),
            height=150,
            placeholder="Describe the event. What will attendees learn or experience?",
        )

        # ── Organizer ─────────────────────────────────────────────────────
        st.subheader("Organizer")
        col5, col6 = st.columns(2)
        with col5:
            organizer_name = st.text_input(
                "Organizer Name *",
                placeholder="Jane Smith",
            )
        with col6:
            organizer_email = st.text_input(
                "Organizer Email *",
                placeholder="jane@example.com",
            )

        # ── Reminder ──────────────────────────────────────────────────────
        st.subheader("Reminder")
        reminder_label = st.selectbox(
            "Reminder Timing",
            options=list(REMINDER_OPTIONS.keys()),
            index=2,  # Default: 15 minutes
            help="A VALARM will be embedded in the ICS file.",
        )
        reminder_minutes = REMINDER_OPTIONS[reminder_label]

        # ── Campaign & Tracking ───────────────────────────────────────────
        st.subheader("Campaign & Tracking")
        col7, col8 = st.columns(2)
        with col7:
            campaign_id = st.text_input(
                "Campaign Name / Internal Event ID",
                value=tmpl.get("campaign_id", ""),
                placeholder="e.g. Q3-WEBINAR-2024",
                help="Stored in the ICS as X-CAMPAIGN-ID. Not visible to recipients.",
            )
        with col8:
            landing_page_url = st.text_input(
                "Landing-Page URL",
                placeholder="https://example.com/event-page",
                help="Appended to the event description and included in links.",
            )

        # UTM Parameters (expandable)
        with st.expander("UTM Parameters (optional)"):
            ucol1, ucol2, ucol3 = st.columns(3)
            with ucol1:
                utm_source = st.text_input("utm_source", placeholder="email")
                utm_term = st.text_input("utm_term", placeholder="")
            with ucol2:
                utm_medium = st.text_input("utm_medium", placeholder="invite")
                utm_content = st.text_input("utm_content", placeholder="")
            with ucol3:
                utm_campaign = st.text_input("utm_campaign", placeholder="q3-webinar-2024")

        # ── HTML Button label ─────────────────────────────────────────────
        st.subheader("HTML Button")
        button_label = st.text_input(
            "Button Label",
            value="Add to Calendar",
            help="The text shown on the Marketo-safe HTML calendar button.",
        )

        st.divider()
        submitted = st.form_submit_button(
            "🗓️ Generate Calendar Assets",
            type="primary",
            use_container_width=True,
        )

    # ── Process form submission ───────────────────────────────────────────────
    if submitted:
        # Build datetime objects
        if all_day:
            start_dt = datetime.combine(start_date, time(0, 0))
            end_dt = datetime.combine(end_date, time(0, 0))
        else:
            start_dt = datetime.combine(start_date, start_time_val)
            end_dt = datetime.combine(end_date, end_time_val)

        # Build UTM-decorated landing page URL
        utm_params = {
            "utm_source": utm_source,
            "utm_medium": utm_medium,
            "utm_campaign": utm_campaign,
            "utm_term": utm_term,
            "utm_content": utm_content,
        }
        final_landing_url = build_utm_url(landing_page_url, utm_params)

        # Assemble event data dict
        event_data = {
            "title": title,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "timezone": timezone,
            "all_day": all_day,
            "location": location,
            "meeting_url": meeting_url,
            "description": description,
            "organizer_name": organizer_name,
            "organizer_email": organizer_email,
            "reminder_minutes": reminder_minutes,
            "campaign_id": campaign_id,
            "landing_page_url": final_landing_url,
        }

        # ── Validation ────────────────────────────────────────────────────
        errors = validate_event(event_data)
        if errors:
            st.error("Please fix the following issues before generating:")
            for e in errors:
                st.markdown(f"- {e}")
            st.stop()

        # ── Generate outputs ──────────────────────────────────────────────
        ics_content = build_ics(event_data)
        google_url = build_google_url(event_data)
        outlook_url = build_outlook_url(event_data)
        html_button = build_html_button(event_data, button_label=button_label or "Add to Calendar")
        preview_text = build_event_preview(event_data)

        # ── Save to history sidebar + shared team calendar ────────────────
        save_to_history({
            "title": title,
            "start_str": start_dt.strftime("%Y-%m-%d %H:%M"),
            "end_str": end_dt.strftime("%Y-%m-%d %H:%M"),
            "timezone": timezone,
            "campaign_id": campaign_id,
        })
        save_to_team_calendar({
            **event_data,
            "event_type": event_type,
            "google_url": google_url,
            "outlook_url": outlook_url,
        })

        # ── Results UI ────────────────────────────────────────────────────
        st.success("✅ Calendar assets generated! Event added to the **Team Calendar**.")
        st.divider()

        # ── Tab layout for outputs ────────────────────────────────────────
        tab_preview, tab_ics, tab_google, tab_outlook, tab_html = st.tabs([
            "📋 Preview",
            "📁 ICS File",
            "🗓️ Google Calendar",
            "📧 Outlook",
            "🖱️ HTML Button",
        ])

        # ── Preview tab ───────────────────────────────────────────────────
        with tab_preview:
            st.subheader("Event Preview")
            st.text(preview_text)

        # ── ICS tab ───────────────────────────────────────────────────────
        with tab_ics:
            st.subheader("Download ICS File")
            st.caption(
                "Works with Google Calendar, Microsoft Outlook, and Apple Calendar. "
                "RFC 5545 compliant with proper DST handling."
            )
            safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)
            filename = f"{safe_title.replace(' ', '_')}.ics"
            st.download_button(
                label="⬇️ Download ICS File",
                data=ics_content.encode("utf-8"),
                file_name=filename,
                mime="text/calendar",
                use_container_width=False,
            )
            with st.expander("Preview ICS content"):
                st.code(ics_content, language="text")

        # ── Google Calendar tab ───────────────────────────────────────────
        with tab_google:
            st.subheader("Google Calendar Link")
            st.caption("Opens a pre-filled 'New Event' form in Google Calendar. No sign-in required to view.")
            st.markdown(f"[Open in Google Calendar]({google_url})", unsafe_allow_html=False)
            st.text_area(
                "Plain-text Google Calendar URL",
                value=google_url,
                height=80,
                key="google_url_text",
            )
            copy_button(google_url, label="📋 Copy Google Calendar URL", key="copy_google")

        # ── Outlook tab ───────────────────────────────────────────────────
        with tab_outlook:
            st.subheader("Outlook Calendar Link")
            st.caption(
                "Opens a pre-filled 'New Event' form in Outlook Web App (outlook.live.com). "
                "For Office 365, replace the base URL with outlook.office.com in the link below."
            )
            st.markdown(f"[Open in Outlook]({outlook_url})", unsafe_allow_html=False)
            st.text_area(
                "Plain-text Outlook URL",
                value=outlook_url,
                height=80,
                key="outlook_url_text",
            )
            copy_button(outlook_url, label="📋 Copy Outlook URL", key="copy_outlook")

            # Office 365 variant
            office365_url = outlook_url.replace(
                "https://outlook.live.com",
                "https://outlook.office.com",
            )
            with st.expander("Office 365 / Work accounts"):
                st.text_area(
                    "Office 365 URL",
                    value=office365_url,
                    height=80,
                    key="o365_url_text",
                )
                copy_button(office365_url, label="📋 Copy Office 365 URL", key="copy_o365")

        # ── HTML Button tab ───────────────────────────────────────────────
        with tab_html:
            st.subheader("HTML Add to Calendar Button")
            st.caption(
                "Paste this snippet into a Marketo email template or landing page. "
                "Uses only inline styles — no external CSS or JS dependencies. "
                "Offers Google Calendar, Outlook, and ICS download options."
            )

            # Live preview
            st.markdown("**Live Preview:**")
            st.components.v1.html(html_button, height=160, scrolling=False)

            # Raw HTML
            st.markdown("**HTML Source:**")
            st.text_area(
                "HTML snippet",
                value=html_button,
                height=300,
                key="html_button_text",
            )
            copy_button(html_button, label="📋 Copy HTML", key="copy_html")

            # Landing page URL with UTM (if present)
            if final_landing_url and final_landing_url != landing_page_url:
                st.markdown("**Landing Page URL with UTM parameters:**")
                st.text_area(
                    "UTM URL",
                    value=final_landing_url,
                    height=60,
                    key="utm_url_text",
                )
                copy_button(final_landing_url, label="📋 Copy UTM URL", key="copy_utm")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
