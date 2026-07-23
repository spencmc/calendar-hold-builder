# pages/1_📅_Team_Calendar.py
# Team Calendar — shows all calendar holds on a shared visual calendar.
# Click any event to view details, edit, or delete.

from __future__ import annotations

import sys
import zoneinfo
from pathlib import Path
from datetime import datetime, date, time

import streamlit as st

# Make db.py and styles.py importable from the pages/ sub-directory
sys.path.insert(0, str(Path(__file__).parent.parent))
import db
from styles import load_css, page_header, section_header, EVENT_COLORS as _EC

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Team Calendar — Calendar Hold Builder",
    page_icon="📅",
    layout="wide",
)

load_css()

# Sidebar navigation
with st.sidebar:
    st.page_link("app.py", label="Create a Hold", icon="🗓️")
    st.page_link("pages/1_📅_Team_Calendar.py", label="Team Calendar", icon="📅")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVENT_COLORS  = _EC  # imported from styles.py — single source of truth
DEFAULT_COLOR = "#17A2B8"
EVENT_TYPE_OPTIONS = list(EVENT_COLORS.keys())

COMMON_TZ = [
    "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "America/Phoenix", "Europe/London",
    "Europe/Paris", "Asia/Tokyo", "UTC",
]
ALL_TZ = sorted(zoneinfo.available_timezones())
TZ_OPTIONS = COMMON_TZ + ["─────────────────"] + [z for z in ALL_TZ if z not in COMMON_TZ]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_dt(dt_str: str, all_day: bool = False) -> str:
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%B %d, %Y") if all_day else dt.strftime("%B %d, %Y at %I:%M %p")
    except ValueError:
        return dt_str


def parse_iso_to_date_time(iso: str) -> tuple[date | None, time | None]:
    """Split an ISO datetime string into a (date, time) tuple."""
    if not iso:
        return None, None
    try:
        dt = datetime.fromisoformat(iso)
        return dt.date(), dt.time().replace(second=0, microsecond=0)
    except ValueError:
        return None, None


def find_event_by_id(events: list[dict], event_id: str) -> dict | None:
    for e in events:
        if str(e.get("id", "")) == str(event_id):
            return e
    return None

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "selected_event_id" not in st.session_state:
    st.session_state.selected_event_id = None
if "editing_event_id" not in st.session_state:
    st.session_state.editing_event_id = None
if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None

# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

page_header(
    "Team Calendar",
    "Every hold, in one place. Click any event to view details, edit, or delete.",
    logo="🗓️",
)

events = db.load_events()

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
# Calendar view
# ---------------------------------------------------------------------------

calendar_events = []
for e in filtered:
    color = EVENT_COLORS.get(e.get("event_type", "Other"), DEFAULT_COLOR)
    calendar_events.append({
        "id": str(e.get("id", "")),
        "title": e.get("title", "Untitled"),
        "start": e.get("start_iso", ""),
        "end": e.get("end_iso", ""),
        "color": color,
        "allDay": e.get("all_day", False),
        "extendedProps": {
            "db_id": str(e.get("id", "")),
            "event_type": e.get("event_type", "Other"),
            "location": e.get("location", ""),
            "meeting_url": e.get("meeting_url", ""),
            "google_url": e.get("google_url", ""),
            "outlook_url": e.get("outlook_url", ""),
            "campaign_id": e.get("campaign_id", ""),
            "organizer_name": e.get("organizer_name", ""),
            "timezone": e.get("timezone", ""),
        },
    })

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

    # When a calendar event is clicked, store its ID in session state
    if clicked and clicked.get("eventClick"):
        ev_click = clicked["eventClick"]["event"]
        db_id = ev_click.get("extendedProps", {}).get("db_id", "")
        if db_id:
            st.session_state.selected_event_id = db_id
            # Clear any open edit/delete state when a new event is selected
            if st.session_state.editing_event_id != db_id:
                st.session_state.editing_event_id = None
            if st.session_state.confirm_delete_id != db_id:
                st.session_state.confirm_delete_id = None

except ImportError:
    st.warning("Calendar view requires the `streamlit-calendar` package. Showing list view instead.")

# ---------------------------------------------------------------------------
# Event detail panel (shown when an event is selected)
# ---------------------------------------------------------------------------

selected_id = st.session_state.selected_event_id
if selected_id:
    full_event = find_event_by_id(events, selected_id)
    if full_event:
        st.divider()

        # ── Header row with title + action buttons ───────────────────────
        title_col, btn_col = st.columns([5, 2])
        with title_col:
            st.subheader(f"📌 {full_event.get('title', 'Event')}")
        with btn_col:
            action_cols = st.columns(3)
            with action_cols[0]:
                if st.button("✏️ Edit", key="btn_edit", use_container_width=True):
                    st.session_state.editing_event_id = selected_id
                    st.session_state.confirm_delete_id = None
            with action_cols[1]:
                if st.button("🗑️ Delete", key="btn_delete", use_container_width=True, type="secondary"):
                    st.session_state.confirm_delete_id = selected_id
                    st.session_state.editing_event_id = None
            with action_cols[2]:
                if st.button("✕ Close", key="btn_close", use_container_width=True):
                    st.session_state.selected_event_id = None
                    st.session_state.editing_event_id = None
                    st.session_state.confirm_delete_id = None
                    st.rerun()

        # ── Delete confirmation ──────────────────────────────────────────
        if st.session_state.confirm_delete_id == selected_id:
            st.warning(
                f"Are you sure you want to delete **{full_event.get('title', 'this event')}**? "
                "This cannot be undone.",
                icon="⚠️",
            )
            yes_col, no_col, _ = st.columns([1, 1, 4])
            with yes_col:
                if st.button("Yes, delete", key="confirm_yes", type="primary"):
                    ok = db.delete_event(selected_id)
                    if ok:
                        st.success("Event deleted.")
                    else:
                        st.error("Could not delete — check Supabase connection.")
                    st.session_state.selected_event_id = None
                    st.session_state.confirm_delete_id = None
                    st.rerun()
            with no_col:
                if st.button("Cancel", key="confirm_no"):
                    st.session_state.confirm_delete_id = None
                    st.rerun()

        # ── Edit form ────────────────────────────────────────────────────
        elif st.session_state.editing_event_id == selected_id:
            st.markdown("#### Edit Event")

            # Parse stored ISO strings back into date/time objects
            start_d, start_t = parse_iso_to_date_time(full_event.get("start_iso", ""))
            end_d, end_t = parse_iso_to_date_time(full_event.get("end_iso", ""))

            with st.form("edit_event_form"):
                e_title = st.text_input("Title *", value=full_event.get("title", ""))

                ec1, ec2 = st.columns(2)
                with ec1:
                    e_event_type = st.selectbox(
                        "Event Type",
                        options=EVENT_TYPE_OPTIONS,
                        index=EVENT_TYPE_OPTIONS.index(full_event.get("event_type", "Other"))
                        if full_event.get("event_type", "Other") in EVENT_TYPE_OPTIONS else 0,
                    )
                with ec2:
                    e_all_day = st.checkbox("All-day event", value=full_event.get("all_day", False))

                dc1, dc2 = st.columns(2)
                with dc1:
                    st.markdown("**Start**")
                    e_start_date = st.date_input(
                        "Start date", value=start_d or date.today(), label_visibility="collapsed", key="e_start_date"
                    )
                    if not e_all_day:
                        e_start_time = st.time_input(
                            "Start time", value=start_t or time(10, 0), label_visibility="collapsed",
                            key="e_start_time", step=300,
                        )
                    else:
                        e_start_time = time(0, 0)
                with dc2:
                    st.markdown("**End**")
                    e_end_date = st.date_input(
                        "End date", value=end_d or date.today(), label_visibility="collapsed", key="e_end_date"
                    )
                    if not e_all_day:
                        e_end_time = st.time_input(
                            "End time", value=end_t or time(11, 0), label_visibility="collapsed",
                            key="e_end_time", step=300,
                        )
                    else:
                        e_end_time = time(0, 0)

                # Timezone selector
                stored_tz = full_event.get("timezone", "America/Chicago")
                tz_index = TZ_OPTIONS.index(stored_tz) if stored_tz in TZ_OPTIONS else 1
                e_timezone = st.selectbox("Time Zone", options=TZ_OPTIONS, index=tz_index)
                if e_timezone.startswith("─"):
                    e_timezone = stored_tz

                lc1, lc2 = st.columns(2)
                with lc1:
                    e_location = st.text_input("Location", value=full_event.get("location", ""))
                with lc2:
                    e_meeting_url = st.text_input("Meeting URL", value=full_event.get("meeting_url", ""))

                e_description = st.text_area("Description", value=full_event.get("description", ""), height=100)

                oc1, oc2 = st.columns(2)
                with oc1:
                    e_organizer = st.text_input("Organizer Name", value=full_event.get("organizer_name", ""))
                with oc2:
                    e_campaign = st.text_input("Campaign ID", value=full_event.get("campaign_id", ""))

                e_landing = st.text_input("Landing Page URL", value=full_event.get("landing_page_url", ""))

                save_col, cancel_col, _ = st.columns([1, 1, 4])
                with save_col:
                    save_btn = st.form_submit_button("💾 Save Changes", type="primary")
                with cancel_col:
                    cancel_btn = st.form_submit_button("Cancel")

            if cancel_btn:
                st.session_state.editing_event_id = None
                st.rerun()

            if save_btn:
                if not e_title.strip():
                    st.error("Title is required.")
                else:
                    new_start = datetime.combine(e_start_date, e_start_time)
                    new_end = datetime.combine(e_end_date, e_end_time)
                    if not e_all_day and new_end <= new_start:
                        st.error("End time must be after start time.")
                    else:
                        updates = {
                            "title": e_title.strip(),
                            "event_type": e_event_type,
                            "start_iso": new_start.isoformat(),
                            "end_iso": new_end.isoformat(),
                            "timezone": e_timezone,
                            "all_day": e_all_day,
                            "location": e_location,
                            "meeting_url": e_meeting_url,
                            "description": e_description,
                            "organizer_name": e_organizer,
                            "campaign_id": e_campaign,
                            "landing_page_url": e_landing,
                        }
                        ok = db.update_event(selected_id, updates)
                        if ok:
                            st.success("✅ Event updated!")
                            st.session_state.editing_event_id = None
                            st.rerun()
                        else:
                            st.error("Could not save — check Supabase connection.")

        # ── Read-only detail view ────────────────────────────────────────
        else:
            all_day = full_event.get("all_day", False)
            start_str = format_dt(full_event.get("start_iso", ""), all_day)
            end_str = format_dt(full_event.get("end_iso", ""), all_day)
            tz = full_event.get("timezone", "")
            event_type = full_event.get("event_type", "Other")
            color = EVENT_COLORS.get(event_type, DEFAULT_COLOR)

            info_col, links_col = st.columns([2, 1])
            with info_col:
                st.markdown(
                    f"<span style='background:{color};color:white;padding:3px 10px;"
                    f"border-radius:12px;font-size:13px;'>{event_type}</span>",
                    unsafe_allow_html=True,
                )
                st.write("")
                st.markdown(
                    f"**When:** {start_str} – {end_str}"
                    + (f" ({tz})" if tz and not all_day else "")
                )
                if full_event.get("location"):
                    st.markdown(f"**Location:** {full_event['location']}")
                if full_event.get("meeting_url"):
                    url = full_event["meeting_url"]
                    st.markdown(f"**Join:** [{url}]({url})")
                if full_event.get("organizer_name"):
                    st.markdown(f"**Organizer:** {full_event['organizer_name']}")
                if full_event.get("campaign_id"):
                    st.markdown(f"**Campaign:** {full_event['campaign_id']}")
                if full_event.get("description"):
                    with st.expander("Description"):
                        st.write(full_event["description"])

            with links_col:
                st.markdown("**Add to Calendar:**")
                if full_event.get("google_url"):
                    st.markdown(f"[📅 Google Calendar]({full_event['google_url']})")
                if full_event.get("outlook_url"):
                    st.markdown(f"[📧 Outlook]({full_event['outlook_url']})")

# ---------------------------------------------------------------------------
# List view (expandable, always available)
# ---------------------------------------------------------------------------

def _render_list_view(event_list: list[dict]) -> None:
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
                # Quick delete from list view
                event_id = str(e.get("id", ""))
                if event_id and st.button("🗑️", key=f"list_del_{event_id}", help="Delete this event"):
                    st.session_state.selected_event_id = event_id
                    st.session_state.confirm_delete_id = event_id
                    st.rerun()


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
