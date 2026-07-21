"""
pages/1_📅_Team_Calendar.py
----------------------------
Team Calendar page — shows all created calendar holds on a shared visual calendar.

Color coded by event type. Click an event to see details and add-to-calendar links.
"""

import json
from pathlib import Path
from datetime import datetime

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Team Calendar — Marketing Calendar Hold Builder",
    page_icon="📅",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CALENDAR_FILE = Path("team_calendar.json")

# Color palette by event type
EVENT_COLORS = {
    "Webinar":          "#0066CC",
    "In-Person Event":  "#28A745",
    "Product Launch":   "#FF6B35",
    "Customer Session": "#9B59B6",
    "Internal Meeting": "#6C757D",
    "Other":            "#17A2B8",
}

DEFAULT_COLOR = "#17A2B8"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_calendar_events() -> list[dict]:
    """Load all saved calendar holds from the shared JSON file."""
    if CALENDAR_FILE.exists():
        try:
            return json.loads(CALENDAR_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def format_dt(dt_str: str, all_day: bool = False) -> str:
    """Format a stored ISO datetime string for display."""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str)
        if all_day:
            return dt.strftime("%B %d, %Y")
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except ValueError:
        return dt_str


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("📅 Team Calendar")
st.caption("All marketing calendar holds created by the team, in one place.")

events = load_calendar_events()

if not events:
    st.info(
        "No calendar holds yet. Go to **Build a Hold** to create your first event — "
        "it will appear here automatically.",
        icon="📭",
    )
    st.stop()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

col_filter1, col_filter2, col_filter3 = st.columns([2, 2, 1])

with col_filter1:
    all_types = sorted(set(e.get("event_type", "Other") for e in events))
    selected_types = st.multiselect(
        "Filter by event type",
        options=all_types,
        default=all_types,
        key="type_filter",
    )

with col_filter2:
    search = st.text_input("Search events", placeholder="Search by title or campaign...", key="search")

with col_filter3:
    st.metric("Total holds", len(events))

# Apply filters
filtered = [
    e for e in events
    if e.get("event_type", "Other") in selected_types
    and (
        not search
        or search.lower() in e.get("title", "").lower()
        or search.lower() in e.get("campaign_id", "").lower()
    )
]

st.divider()

# ---------------------------------------------------------------------------
# Calendar view (streamlit-calendar)
# ---------------------------------------------------------------------------

# Build FullCalendar-compatible event list
calendar_events = []
for e in filtered:
    color = EVENT_COLORS.get(e.get("event_type", "Other"), DEFAULT_COLOR)
    cal_event = {
        "title": e.get("title", "Untitled"),
        "start": e.get("start_iso", ""),
        "end": e.get("end_iso", ""),
        "color": color,
        "allDay": e.get("all_day", False),
        "extendedProps": {
            "event_type": e.get("event_type", "Other"),
            "location": e.get("location", ""),
            "meeting_url": e.get("meeting_url", ""),
            "google_url": e.get("google_url", ""),
            "outlook_url": e.get("outlook_url", ""),
            "campaign_id": e.get("campaign_id", ""),
            "organizer_name": e.get("organizer_name", ""),
            "timezone": e.get("timezone", ""),
        },
    }
    calendar_events.append(cal_event)

calendar_options = {
    "initialView": "dayGridMonth",
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,listMonth",
    },
    "height": 650,
    "eventDisplay": "block",
    "dayMaxEvents": 3,
    "navLinks": True,
    "editable": False,
    "selectable": False,
}

# Custom CSS for the calendar
calendar_css = """
    .fc-event { cursor: pointer; font-size: 12px; }
    .fc-daygrid-event { border-radius: 4px; padding: 2px 4px; }
    .fc-toolbar-title { font-size: 1.2em !important; }
"""

try:
    from streamlit_calendar import calendar as st_calendar

    clicked = st_calendar(
        events=calendar_events,
        options=calendar_options,
        custom_css=calendar_css,
        key="team_calendar",
    )

    # Handle click on an event
    if clicked and clicked.get("eventClick"):
        ev = clicked["eventClick"]["event"]
        props = ev.get("extendedProps", {})

        st.divider()
        st.subheader(f"📌 {ev.get('title', 'Event')}")

        info_col, links_col = st.columns([2, 1])

        with info_col:
            event_type = props.get("event_type", "Other")
            color = EVENT_COLORS.get(event_type, DEFAULT_COLOR)
            st.markdown(
                f"<span style='background:{color};color:white;padding:3px 10px;"
                f"border-radius:12px;font-size:13px;'>{event_type}</span>",
                unsafe_allow_html=True,
            )
            st.write("")

            all_day = ev.get("allDay", False)
            start_str = format_dt(ev.get("start", ""), all_day)
            end_str = format_dt(ev.get("end", ""), all_day)
            tz = props.get("timezone", "")

            st.markdown(f"**When:** {start_str} – {end_str}" + (f" ({tz})" if tz and not all_day else ""))

            if props.get("location"):
                st.markdown(f"**Location:** {props['location']}")
            if props.get("meeting_url"):
                st.markdown(f"**Join:** [{props['meeting_url']}]({props['meeting_url']})")
            if props.get("organizer_name"):
                st.markdown(f"**Organizer:** {props['organizer_name']}")
            if props.get("campaign_id"):
                st.markdown(f"**Campaign:** {props['campaign_id']}")

        with links_col:
            st.markdown("**Add to Calendar:**")
            if props.get("google_url"):
                st.markdown(f"[📅 Google Calendar]({props['google_url']})")
            if props.get("outlook_url"):
                st.markdown(f"[📧 Outlook]({props['outlook_url']})")

except ImportError:
    # Fallback: simple card-based list view if streamlit-calendar not installed
    st.warning("Calendar view requires the `streamlit-calendar` package. Showing list view instead.")
    _render_list_view(filtered)


# ---------------------------------------------------------------------------
# List view (always shown below calendar as backup / for printing)
# ---------------------------------------------------------------------------

def _render_list_view(event_list: list[dict]) -> None:
    """Render events as a simple sortable card list."""
    # Sort by start date
    sorted_events = sorted(event_list, key=lambda e: e.get("start_iso", ""))

    for e in sorted_events:
        color = EVENT_COLORS.get(e.get("event_type", "Other"), DEFAULT_COLOR)
        all_day = e.get("all_day", False)
        start_str = format_dt(e.get("start_iso", ""), all_day)
        tz = e.get("timezone", "")

        with st.container(border=True):
            left, right = st.columns([4, 1])
            with left:
                st.markdown(
                    f"<span style='background:{color};color:white;padding:2px 8px;"
                    f"border-radius:10px;font-size:11px;'>{e.get('event_type','Other')}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{e.get('title', 'Untitled')}**")
                st.caption(f"{start_str}" + (f" · {tz}" if tz and not all_day else ""))
                if e.get("location"):
                    st.caption(f"📍 {e['location']}")
                if e.get("campaign_id"):
                    st.caption(f"🏷️ {e['campaign_id']}")
            with right:
                if e.get("google_url"):
                    st.markdown(f"[Google Cal]({e['google_url']})")
                if e.get("outlook_url"):
                    st.markdown(f"[Outlook]({e['outlook_url']})")


with st.expander("📋 List view", expanded=False):
    _render_list_view(filtered)


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------

st.divider()
st.markdown("**Event Types:**")
legend_cols = st.columns(len(EVENT_COLORS))
for col, (etype, color) in zip(legend_cols, EVENT_COLORS.items()):
    with col:
        st.markdown(
            f"<span style='background:{color};color:white;padding:3px 10px;"
            f"border-radius:12px;font-size:12px;'>{etype}</span>",
            unsafe_allow_html=True,
        )
