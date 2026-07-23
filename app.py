from __future__ import annotations

"""
app.py
------
Marketing Calendar Hold Builder — Streamlit front-end.

Run locally:
    streamlit run app.py

Generates ICS files, Google Calendar links, Outlook links,
HTML Add-to-Calendar buttons, and a plain-text event preview.
"""

import json
import zoneinfo
from datetime import datetime, date, time, timedelta
from pathlib import Path

import streamlit as st

import db
from styles import load_css, page_header, section_header, sidebar_brand, sidebar_label, results_banner, copy_button
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
    page_title="Calendar Hold Builder",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HISTORY_FILE = Path("recent_events.json")
MAX_HISTORY  = 10

COMMON_TZ = [
    "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "America/Phoenix", "America/Anchorage",
    "Pacific/Honolulu", "Europe/London", "Europe/Paris", "Europe/Berlin",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Australia/Sydney", "UTC",
]
ALL_TZ     = sorted(zoneinfo.available_timezones())
TZ_OPTIONS = COMMON_TZ + ["─────────────────"] + [z for z in ALL_TZ if z not in COMMON_TZ]

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = {
    "── Select a template ──": {},
    "Webinar": {
        "title": "Webinar: [Topic Name]",
        "description": (
            "Join us for an informative webinar on [Topic Name].\n\n"
            "What you'll learn:\n"
            "• [Key point 1]\n• [Key point 2]\n• [Key point 3]\n\n"
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
            "Agenda:\n• [Session 1]\n• [Session 2]\n• Networking\n\n"
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
            "from the product team.\n\nDon't miss this exciting milestone."
        ),
        "location": "",
        "reminder_minutes": 30,
        "campaign_id": "LAUNCH-2024-",
    },
    "Customer Session": {
        "title": "Customer Session: [Customer Name]",
        "description": (
            "Dedicated session for [Customer Name].\n\n"
            "Agenda:\n• Review & check-in\n• Product updates\n• Q&A\n\n"
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
            "Agenda:\n• Status updates\n• Blockers\n• Action items"
        ),
        "location": "",
        "reminder_minutes": 10,
        "campaign_id": "INT-2024-",
    },
}

TEMPLATE_ICONS = {
    "Webinar":          "🎙️",
    "In-Person Event":  "🏟️",
    "Product Launch":   "🚀",
    "Customer Session": "🤝",
    "Internal Meeting": "☕",
}

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
# History (local sidebar — no PII)
# ---------------------------------------------------------------------------

def load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_to_history(entry: dict) -> None:
    safe = {
        "title":      entry.get("title", ""),
        "start_str":  entry.get("start_str", ""),
        "timezone":   entry.get("timezone", ""),
        "campaign_id":entry.get("campaign_id", ""),
        "saved_at":   datetime.utcnow().isoformat() + "Z",
    }
    history = load_history()
    history.insert(0, safe)
    try:
        HISTORY_FILE.write_text(json.dumps(history[:MAX_HISTORY], indent=2))
    except OSError:
        pass


def save_to_team_calendar(entry: dict) -> None:
    """Save a full event entry to Supabase shared team calendar."""
    start_dt = entry.get("start_dt")
    end_dt   = entry.get("end_dt")
    db.save_event({
        "title":            entry.get("title", ""),
        "event_type":       entry.get("event_type", "Other"),
        "start_iso":        start_dt.isoformat() if start_dt else "",
        "end_iso":          end_dt.isoformat()   if end_dt   else "",
        "timezone":         entry.get("timezone", ""),
        "all_day":          entry.get("all_day", False),
        "location":         entry.get("location", ""),
        "meeting_url":      entry.get("meeting_url", ""),
        "description":      entry.get("description", ""),
        "organizer_name":   entry.get("organizer_name", ""),
        "campaign_id":      entry.get("campaign_id", ""),
        "landing_page_url": entry.get("landing_page_url", ""),
        "google_url":       entry.get("google_url", ""),
        "outlook_url":      entry.get("outlook_url", ""),
        "source":           "app",
    })


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:

    # ── Hero header ──────────────────────────────────────────────────────────
    page_header(
        "Calendar Hold Builder",
        "Grab the date before someone else does. 🎯",
    )

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        sidebar_brand()

        # Navigation
        st.page_link("app.py", label="Create a Hold", icon="🗓️")
        st.page_link("pages/1_📅_Team_Calendar.py", label="Team Calendar", icon="📅")

        st.divider()

        # Quick-pick template buttons
        sidebar_label("Quick Templates")
        tmpl_items = list(TEMPLATE_ICONS.items())
        for i in range(0, len(tmpl_items), 2):
            cols = st.columns(2, gap="small")
            for j, col in enumerate(cols):
                if i + j < len(tmpl_items):
                    name, icon = tmpl_items[i + j]
                    short = name.split()[0]  # "Webinar", "In-Person", etc.
                    with col:
                        if st.button(
                            f"{icon} {short}",
                            key=f"tmpl_btn_{name}",
                            use_container_width=True,
                        ):
                            st.session_state.template_select = name
                            st.rerun()

        # Dropdown fallback (all templates including "select")
        sidebar_label("Or pick a template")
        selected_template = st.selectbox(
            "template",
            options=list(TEMPLATES.keys()),
            key="template_select",
            label_visibility="collapsed",
            help="Pre-fill the form with a starting point for common event types.",
        )

        st.divider()

        # Recent holds
        sidebar_label("Recent Holds")
        history = load_history()
        if history:
            for item in history:
                with st.expander(f"📌 {item.get('title', 'Untitled')[:32]}"):
                    st.caption(
                        f"{item.get('start_str', '')}  \n"
                        f"{item.get('timezone', '')}  \n"
                        + (f"🏷️ {item['campaign_id']}" if item.get("campaign_id") else "")
                    )
                    st.caption(f"Saved {item.get('saved_at', '')[:10]}")
        else:
            st.markdown(
                "<p style='color:rgba(255,255,255,0.3);font-size:0.82rem;"
                "font-style:italic;margin-top:4px;'>No holds yet.</p>",
                unsafe_allow_html=True,
            )

    # ── Template & brief state ────────────────────────────────────────────────
    tmpl = TEMPLATES.get(selected_template, {})

    if "brief_fields" not in st.session_state:
        st.session_state.brief_fields = {}

    # ── Brief import expander ─────────────────────────────────────────────────
    with st.expander("✨ Import from Brief  —  Google Doc or PDF", expanded=False):
        _proxy_url = st.secrets.get("LITELLM_PROXY_URL", "")
        _proxy_key = st.secrets.get("LITELLM_API_KEY", "")
        _ai_on     = bool(_proxy_url and _proxy_key)

        if _ai_on:
            st.success("AI-powered parsing enabled — Claude will extract dates, times, and details automatically.", icon="🤖")
        else:
            st.info("Standard parsing active. AI parsing will kick in once LiteLLM is configured.", icon="ℹ️")

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
                    st.error("Paste a Google Doc URL first.")
                else:
                    with st.spinner("Fetching brief..."):
                        try:
                            brief_text = fetch_doc_text(doc_url_input.strip())
                        except ValueError as e:
                            st.error(str(e))
        else:
            uploaded_pdf = st.file_uploader(
                "Upload PDF brief",
                type=["pdf"],
                key="pdf_uploader",
                help="Upload a campaign brief as a PDF.",
            )
            if st.button("🔍 Import Brief", key="import_pdf_btn"):
                if not uploaded_pdf:
                    st.error("Please attach a PDF first.")
                else:
                    with st.spinner("Reading PDF..."):
                        try:
                            brief_text = extract_pdf_text(uploaded_pdf.read())
                        except ValueError as e:
                            st.error(str(e))

        if brief_text:
            with st.spinner("Parsing with AI..." if _ai_on else "Parsing brief..."):
                try:
                    if _ai_on:
                        fields = parse_brief_with_ai(brief_text, _proxy_url, _proxy_key)
                    else:
                        fields = parse_brief(brief_text)
                    st.session_state.brief_fields = fields
                    found = [k for k, v in (fields[0] if isinstance(fields, list) else fields).items() if v]
                    st.success(
                        f"Brief imported! Detected: {', '.join(found[:6])}. "
                        "Review the form below before generating."
                    )
                except (ValueError, Exception) as e:
                    st.error(f"Could not parse brief: {e}")

    # Merge brief → template defaults
    brief = st.session_state.brief_fields
    if brief:
        src = brief[0] if isinstance(brief, list) else brief
        for key in ["title", "location", "meeting_url", "description",
                    "organizer_name", "organizer_email", "campaign_id", "landing_page_url"]:
            if src.get(key):
                tmpl[key] = src[key]

    # ── Event form ────────────────────────────────────────────────────────────
    with st.form("event_form", clear_on_submit=False):

        # ── Event details ─────────────────────────────────────────────────
        section_header("Event Details", "📋")

        col_title, col_type = st.columns([3, 1])
        with col_title:
            title = st.text_input(
                "Event Title *",
                value=tmpl.get("title", ""),
                placeholder="e.g. Q3 Product Webinar",
                help="Required. Shown in all calendar apps.",
            )
        with col_type:
            event_type_options = [
                "Webinar", "In-Person Event", "Product Launch",
                "Customer Session", "Internal Meeting", "Other",
            ]
            default_type_index = (
                event_type_options.index(selected_template)
                if selected_template in event_type_options else 0
            )
            event_type = st.selectbox(
                "Event Type",
                options=event_type_options,
                index=default_type_index,
                help="Color-codes the event on the Team Calendar.",
            )

        col_allday, _ = st.columns([1, 3])
        with col_allday:
            all_day = st.checkbox("All-day event", value=False)

        # Date / time defaults
        _default_start      = date.today() + timedelta(days=7)
        _default_end        = date.today() + timedelta(days=7)
        _default_start_time = time(10, 0)
        _default_end_time   = time(11, 0)

        src = brief[0] if isinstance(brief, list) else brief
        if src.get("start_dt") and isinstance(src["start_dt"], datetime):
            _default_start      = src["start_dt"].date()
            _default_start_time = src["start_dt"].time().replace(second=0, microsecond=0)
        if src.get("end_dt") and isinstance(src["end_dt"], datetime):
            _default_end      = src["end_dt"].date()
            _default_end_time = src["end_dt"].time().replace(second=0, microsecond=0)

        # ── Date & time ───────────────────────────────────────────────────
        section_header("When", "🗓️")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                "<p style='font-size:0.78rem;font-weight:600;text-transform:uppercase;"
                "letter-spacing:0.06em;color:#6B7280;margin-bottom:4px;'>Start *</p>",
                unsafe_allow_html=True,
            )
            start_date = st.date_input("Start date", value=_default_start,
                                       label_visibility="collapsed", key="start_date")
            if not all_day:
                start_time_val = st.time_input("Start time", value=_default_start_time,
                                               label_visibility="collapsed",
                                               key="start_time", step=300)
            else:
                start_time_val = time(0, 0)

        with col2:
            st.markdown(
                "<p style='font-size:0.78rem;font-weight:600;text-transform:uppercase;"
                "letter-spacing:0.06em;color:#6B7280;margin-bottom:4px;'>End *</p>",
                unsafe_allow_html=True,
            )
            end_date = st.date_input("End date", value=_default_end,
                                     label_visibility="collapsed", key="end_date")
            if not all_day:
                end_time_val = st.time_input("End time", value=_default_end_time,
                                             label_visibility="collapsed",
                                             key="end_time", step=300)
            else:
                end_time_val = time(0, 0)

        default_tz = "America/Chicago"
        tz_index   = TZ_OPTIONS.index(default_tz) if default_tz in TZ_OPTIONS else 0
        timezone   = st.selectbox(
            "Time Zone *", options=TZ_OPTIONS, index=tz_index,
            help="IANA timezone — common zones listed first.",
        )
        if timezone.startswith("─"):
            timezone = "UTC"

        # ── Location ──────────────────────────────────────────────────────
        section_header("Location", "📍")

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
                help="Zoom, Teams, Google Meet, etc.",
            )

        # ── Description ───────────────────────────────────────────────────
        section_header("Description", "✍️")

        description = st.text_area(
            "Event Description",
            value=tmpl.get("description", ""),
            height=140,
            placeholder="What will attendees learn or experience?",
        )

        # ── Organizer ─────────────────────────────────────────────────────
        section_header("Organizer", "👤")

        col5, col6 = st.columns(2)
        with col5:
            organizer_name  = st.text_input("Organizer Name *",  placeholder="Jane Smith")
        with col6:
            organizer_email = st.text_input("Organizer Email *", placeholder="jane@g2.com")

        # ── Reminder ──────────────────────────────────────────────────────
        section_header("Reminder", "⏰")

        reminder_label   = st.selectbox(
            "Reminder Timing",
            options=list(REMINDER_OPTIONS.keys()),
            index=3,  # Default: 15 minutes
            help="Embeds a VALARM in the ICS file.",
        )
        reminder_minutes = REMINDER_OPTIONS[reminder_label]

        # ── Campaign & tracking ───────────────────────────────────────────
        section_header("Campaign & Tracking", "🏷️")

        col7, col8 = st.columns(2)
        with col7:
            campaign_id = st.text_input(
                "Campaign ID / Event Name",
                value=tmpl.get("campaign_id", ""),
                placeholder="e.g. Q3-WEBINAR-2024",
                help="Stored in the ICS as X-CAMPAIGN-ID. Not visible to attendees.",
            )
        with col8:
            landing_page_url = st.text_input(
                "Landing-Page URL",
                placeholder="https://g2.com/event-page",
                help="Appended to the event description and included in calendar links.",
            )

        with st.expander("UTM Parameters (optional)"):
            ucol1, ucol2, ucol3 = st.columns(3)
            with ucol1:
                utm_source   = st.text_input("utm_source",   placeholder="email")
                utm_term     = st.text_input("utm_term",     placeholder="")
            with ucol2:
                utm_medium   = st.text_input("utm_medium",   placeholder="invite")
                utm_content  = st.text_input("utm_content",  placeholder="")
            with ucol3:
                utm_campaign = st.text_input("utm_campaign", placeholder="q3-webinar-2024")

        # ── HTML button label ─────────────────────────────────────────────
        section_header("HTML Button", "🖱️")

        button_label = st.text_input(
            "Button Label",
            value="Add to Calendar",
            help="Text shown on the Marketo-safe HTML calendar button.",
        )

        st.divider()
        submitted = st.form_submit_button(
            "🗓️  Generate Calendar Assets",
            type="primary",
            use_container_width=True,
        )

    # ── Post-submit processing ────────────────────────────────────────────────
    if submitted:
        if all_day:
            start_dt = datetime.combine(start_date, time(0, 0))
            end_dt   = datetime.combine(end_date,   time(0, 0))
        else:
            start_dt = datetime.combine(start_date, start_time_val)
            end_dt   = datetime.combine(end_date,   end_time_val)

        utm_params = {
            "utm_source": utm_source, "utm_medium": utm_medium,
            "utm_campaign": utm_campaign, "utm_term": utm_term, "utm_content": utm_content,
        }
        final_landing_url = build_utm_url(landing_page_url, utm_params)

        event_data = {
            "title": title, "start_dt": start_dt, "end_dt": end_dt,
            "timezone": timezone, "all_day": all_day, "location": location,
            "meeting_url": meeting_url, "description": description,
            "organizer_name": organizer_name, "organizer_email": organizer_email,
            "reminder_minutes": reminder_minutes, "campaign_id": campaign_id,
            "landing_page_url": final_landing_url,
        }

        errors = validate_event(event_data)
        if errors:
            st.error("Fix these before generating:")
            for e in errors:
                st.markdown(f"- {e}")
            st.stop()

        ics_content  = build_ics(event_data)
        google_url   = build_google_url(event_data)
        outlook_url  = build_outlook_url(event_data)
        html_button  = build_html_button(event_data, button_label=button_label or "Add to Calendar")
        preview_text = build_event_preview(event_data)

        save_to_history({
            "title": title,
            "start_str": start_dt.strftime("%b %d, %Y %I:%M %p"),
            "timezone": timezone,
            "campaign_id": campaign_id,
        })
        save_to_team_calendar({
            **event_data,
            "event_type": event_type,
            "google_url": google_url,
            "outlook_url": outlook_url,
        })

        # ── Success banner ────────────────────────────────────────────────
        results_banner(
            "Hold secured! Your event is on the Team Calendar.",
            f"Calendar assets ready for: {title}",
        )

        # ── Output tabs ───────────────────────────────────────────────────
        tab_preview, tab_ics, tab_google, tab_outlook, tab_html = st.tabs([
            "📋 Preview",
            "📁 ICS File",
            "🗓️ Google Calendar",
            "📧 Outlook",
            "🖱️ HTML Button",
        ])

        with tab_preview:
            st.subheader("Event Preview")
            st.text(preview_text)

        with tab_ics:
            st.subheader("Download ICS File")
            st.caption(
                "RFC 5545 compliant · works with Google Calendar, Outlook, and Apple Calendar."
            )
            safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)
            st.download_button(
                label="⬇️  Download .ics File",
                data=ics_content.encode("utf-8"),
                file_name=f"{safe_title.replace(' ', '_')}.ics",
                mime="text/calendar",
            )
            with st.expander("Preview raw ICS"):
                st.code(ics_content, language="text")

        with tab_google:
            st.subheader("Google Calendar Link")
            st.caption("Opens a pre-filled New Event form in Google Calendar.")
            st.markdown(f"[Open in Google Calendar ↗]({google_url})")
            st.text_area("URL", value=google_url, height=80, key="google_url_text")
            copy_button(google_url, label="📋  Copy Google Calendar URL", key="copy_google")

        with tab_outlook:
            st.subheader("Outlook Calendar Link")
            st.caption(
                "Opens a pre-filled New Event form in Outlook Web App. "
                "For Office 365, use the variant below."
            )
            st.markdown(f"[Open in Outlook ↗]({outlook_url})")
            st.text_area("URL", value=outlook_url, height=80, key="outlook_url_text")
            copy_button(outlook_url, label="📋  Copy Outlook URL", key="copy_outlook")

            office365_url = outlook_url.replace(
                "https://outlook.live.com", "https://outlook.office.com"
            )
            with st.expander("Office 365 / Work accounts"):
                st.text_area("Office 365 URL", value=office365_url,
                             height=80, key="o365_url_text")
                copy_button(office365_url, label="📋  Copy Office 365 URL", key="copy_o365")

        with tab_html:
            st.subheader("HTML Add to Calendar Button")
            st.caption(
                "Paste into a Marketo email or landing page. "
                "Inline styles only — no external CSS or JS needed."
            )
            st.markdown("**Live Preview:**")
            st.components.v1.html(html_button, height=160, scrolling=False)
            st.markdown("**HTML Source:**")
            st.text_area("HTML snippet", value=html_button, height=280, key="html_button_text")
            copy_button(html_button, label="📋  Copy HTML", key="copy_html")

            if final_landing_url and final_landing_url != landing_page_url:
                st.markdown("**Landing Page URL with UTM parameters:**")
                st.text_area("UTM URL", value=final_landing_url, height=60, key="utm_url_text")
                copy_button(final_landing_url, label="📋  Copy UTM URL", key="copy_utm")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
