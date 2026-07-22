from __future__ import annotations

"""
db.py
-----
Shared database layer using Supabase.

Both the Streamlit app and CalBot use this module to read/write calendar events.
Replaces the local team_calendar.json file with a cloud database that both
the Streamlit app and the Slack bot can access simultaneously.
"""

import os
import requests
from datetime import datetime


# ---------------------------------------------------------------------------
# Config — reads from environment or Streamlit secrets
# ---------------------------------------------------------------------------

def _get_config() -> tuple[str, str]:
    """Get Supabase URL and key from environment or Streamlit secrets."""
    # Try Streamlit secrets first (when running in Streamlit)
    try:
        import streamlit as st
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return url, key
    except Exception:
        pass

    # Fall back to environment variables (when running CalBot)
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    return url, key


TABLE = "calendar_events"


def _headers() -> dict:
    _, key = _get_config()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _base_url() -> str:
    url, _ = _get_config()
    return f"{url.rstrip('/')}/rest/v1/{TABLE}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_event(entry: dict) -> bool:
    """Insert a calendar event into Supabase.

    Args:
        entry: Dict with event fields (matches table schema).

    Returns:
        True on success, False on failure.
    """
    url, key = _get_config()
    if not url or not key:
        return False  # Supabase not configured — silent fail

    # Clean up fields to match table schema
    row = {
        "title":            entry.get("title", ""),
        "event_type":       entry.get("event_type", "Other"),
        "start_iso":        entry.get("start_iso", ""),
        "end_iso":          entry.get("end_iso", ""),
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
        "source":           entry.get("source", "app"),
    }

    try:
        resp = requests.post(_base_url(), json=row, headers=_headers(), timeout=10)
        return resp.ok
    except Exception:
        return False


def load_events(limit: int = 500) -> list[dict]:
    """Fetch all calendar events from Supabase, newest first."""
    url, key = _get_config()
    if not url or not key:
        return []

    try:
        resp = requests.get(
            _base_url(),
            headers={**_headers(), "Prefer": ""},
            params={"order": "saved_at.desc", "limit": limit},
            timeout=10,
        )
        if resp.ok:
            return resp.json()
        return []
    except Exception:
        return []


def delete_event(event_id: str) -> bool:
    """Delete a calendar event by its UUID.

    Args:
        event_id: The UUID of the event to delete.

    Returns:
        True on success, False on failure.
    """
    url, key = _get_config()
    if not url or not key:
        return False

    try:
        resp = requests.delete(
            _base_url(),
            headers=_headers(),
            params={"id": f"eq.{event_id}"},
            timeout=10,
        )
        return resp.ok
    except Exception:
        return False


def update_event(event_id: str, data: dict) -> bool:
    """Update fields on an existing calendar event.

    Args:
        event_id: The UUID of the event to update.
        data: Dict of fields to update (only provided keys are changed).

    Returns:
        True on success, False on failure.
    """
    url, key = _get_config()
    if not url or not key:
        return False

    try:
        resp = requests.patch(
            _base_url(),
            headers=_headers(),
            params={"id": f"eq.{event_id}"},
            json=data,
            timeout=10,
        )
        return resp.ok
    except Exception:
        return False
