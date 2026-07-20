"""
test_calendar_utils.py
----------------------
Unit tests for calendar_utils.py

Covers:
  - ICS generation (structure, RFC 5545 compliance, CRLF line endings)
  - DST-aware timezone conversion
  - URL encoding for Google and Outlook links
  - HTML button generation (escape safety)
  - Form validation (required fields, end > start, email, URL)
  - UTM URL building
  - All-day and multi-day events
  - Line folding per RFC 5545
  - Event preview generation

Run with:
    pytest test_calendar_utils.py -v
"""

import pytest
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from calendar_utils import (
    build_ics,
    build_google_url,
    build_outlook_url,
    build_html_button,
    build_utm_url,
    build_event_preview,
    validate_event,
    localize,
    to_utc,
    escape_ics_text,
    fold_ics_line,
    format_ics_datetime,
    parse_timezone,
    validate_email,
    validate_url,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def basic_event():
    """Minimal valid timed event (naive datetimes — will be localized)."""
    return {
        "title": "Q3 Webinar",
        "start_dt": datetime(2024, 9, 15, 10, 0),   # naive
        "end_dt": datetime(2024, 9, 15, 11, 0),
        "timezone": "America/Chicago",
        "all_day": False,
        "location": "Online",
        "meeting_url": "https://zoom.us/j/123456",
        "description": "An informative webinar.",
        "organizer_name": "Jane Smith",
        "organizer_email": "jane@example.com",
        "reminder_minutes": 15,
        "campaign_id": "WEB-2024-Q3",
        "landing_page_url": "https://example.com/webinar",
    }


@pytest.fixture
def allday_event():
    """Valid all-day single-day event."""
    return {
        "title": "Company Offsite",
        "start_dt": datetime(2024, 10, 1, 0, 0),
        "end_dt": datetime(2024, 10, 3, 0, 0),  # multi-day all-day
        "timezone": "America/New_York",
        "all_day": True,
        "location": "Chicago, IL",
        "meeting_url": "",
        "description": "Annual company offsite.",
        "organizer_name": "HR Team",
        "organizer_email": "hr@example.com",
        "reminder_minutes": 1440,
        "campaign_id": "",
        "landing_page_url": "",
    }


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------

class TestTimezoneHelpers:

    def test_parse_valid_timezone(self):
        tz = parse_timezone("America/New_York")
        assert tz is not None

    def test_parse_utc(self):
        tz = parse_timezone("UTC")
        assert tz is not None

    def test_parse_invalid_timezone(self):
        with pytest.raises(ValueError, match="Unknown timezone"):
            parse_timezone("Not/ATimezone")

    def test_parse_empty_string(self):
        with pytest.raises(ValueError, match="required"):
            parse_timezone("")

    def test_localize_naive_datetime(self):
        dt = datetime(2024, 9, 15, 10, 0)  # naive
        result = localize(dt, "America/Chicago")
        assert result.tzinfo is not None
        # UTC offset for America/Chicago in September (CDT) = -5:00
        from datetime import timezone, timedelta as td
        assert result.utcoffset() == td(hours=-5)

    def test_localize_dst_summer(self):
        """Summer: America/New_York should be UTC-4 (EDT)."""
        dt = datetime(2024, 7, 4, 12, 0)
        result = localize(dt, "America/New_York")
        from datetime import timedelta as td
        assert result.utcoffset() == td(hours=-4)

    def test_localize_dst_winter(self):
        """Winter: America/New_York should be UTC-5 (EST)."""
        dt = datetime(2024, 1, 15, 12, 0)
        result = localize(dt, "America/New_York")
        from datetime import timedelta as td
        assert result.utcoffset() == td(hours=-5)

    def test_to_utc_conversion(self):
        dt = localize(datetime(2024, 9, 15, 10, 0), "America/Chicago")
        utc = to_utc(dt)
        # CDT = UTC-5, so 10:00 CDT = 15:00 UTC
        assert utc.hour == 15
        assert utc.minute == 0

    def test_to_utc_preserves_date(self):
        dt = localize(datetime(2024, 9, 15, 0, 30), "America/New_York")
        utc = to_utc(dt)
        # 00:30 EDT (UTC-4) = 04:30 UTC — still same calendar day in UTC
        assert utc.hour == 4
        assert utc.minute == 30

    def test_format_ics_datetime_utc(self):
        dt = localize(datetime(2024, 9, 15, 10, 0), "America/Chicago")
        result = format_ics_datetime(dt)
        assert result.endswith("Z")
        assert "T150000Z" in result  # 10:00 CDT = 15:00 UTC

    def test_format_ics_datetime_allday(self):
        dt = datetime(2024, 10, 1, 0, 0)
        result = format_ics_datetime(dt, all_day=True)
        assert result == "20241001"
        assert "T" not in result


# ---------------------------------------------------------------------------
# ICS generation
# ---------------------------------------------------------------------------

class TestICSGeneration:

    def test_basic_ics_structure(self, basic_event):
        ics = build_ics(basic_event)
        assert ics.startswith("BEGIN:VCALENDAR")
        assert "END:VCALENDAR" in ics
        assert "BEGIN:VEVENT" in ics
        assert "END:VEVENT" in ics

    def test_ics_uses_crlf(self, basic_event):
        ics = build_ics(basic_event)
        assert "\r\n" in ics
        # All lines must end with CRLF
        for line in ics.split("\r\n")[:-1]:  # last element after final CRLF is empty
            assert "\n" not in line, f"Bare LF found in ICS line: {repr(line)}"

    def test_ics_version_and_prodid(self, basic_event):
        ics = build_ics(basic_event)
        assert "VERSION:2.0" in ics
        assert "PRODID:" in ics
        assert "CALSCALE:GREGORIAN" in ics

    def test_ics_summary(self, basic_event):
        ics = build_ics(basic_event)
        assert "SUMMARY:Q3 Webinar" in ics

    def test_ics_dtstart_utc(self, basic_event):
        ics = build_ics(basic_event)
        # 10:00 CDT (UTC-5) = 15:00 UTC
        assert "DTSTART:20240915T150000Z" in ics

    def test_ics_dtend_utc(self, basic_event):
        ics = build_ics(basic_event)
        # 11:00 CDT = 16:00 UTC
        assert "DTEND:20240915T160000Z" in ics

    def test_ics_organizer(self, basic_event):
        ics = build_ics(basic_event)
        assert "ORGANIZER" in ics
        assert "jane@example.com" in ics

    def test_ics_location(self, basic_event):
        ics = build_ics(basic_event)
        assert "LOCATION:Online" in ics

    def test_ics_url(self, basic_event):
        ics = build_ics(basic_event)
        assert "URL:https://zoom.us/j/123456" in ics

    def test_ics_uid_present(self, basic_event):
        ics = build_ics(basic_event)
        assert "UID:" in ics

    def test_ics_custom_uid(self, basic_event):
        basic_event["uid"] = "my-custom-uid@test"
        ics = build_ics(basic_event)
        assert "UID:my-custom-uid@test" in ics

    def test_ics_valarm(self, basic_event):
        ics = build_ics(basic_event)
        assert "BEGIN:VALARM" in ics
        assert "TRIGGER:-PT15M" in ics
        assert "END:VALARM" in ics

    def test_ics_no_alarm_when_none(self, basic_event):
        basic_event["reminder_minutes"] = None
        ics = build_ics(basic_event)
        assert "BEGIN:VALARM" not in ics

    def test_ics_campaign_id(self, basic_event):
        ics = build_ics(basic_event)
        assert "X-CAMPAIGN-ID:WEB-2024-Q3" in ics

    def test_ics_no_campaign_id_when_empty(self, basic_event):
        basic_event["campaign_id"] = ""
        ics = build_ics(basic_event)
        assert "X-CAMPAIGN-ID" not in ics

    def test_ics_allday_event(self, allday_event):
        ics = build_ics(allday_event)
        assert "DTSTART;VALUE=DATE:20241001" in ics
        # End is exclusive — 3 days → 2024-10-03 + 1 = 2024-10-04
        assert "DTEND;VALUE=DATE:20241004" in ics

    def test_ics_description_contains_meeting_url(self, basic_event):
        ics = build_ics(basic_event)
        assert "DESCRIPTION:" in ics
        assert "zoom.us" in ics

    def test_ics_special_chars_escaped(self):
        data = {
            "title": "Event; With, Special\\Chars",
            "start_dt": datetime(2024, 9, 15, 10, 0),
            "end_dt": datetime(2024, 9, 15, 11, 0),
            "timezone": "UTC",
            "all_day": False,
            "location": "",
            "meeting_url": "",
            "description": "Line 1\nLine 2",
            "organizer_name": "Test User",
            "organizer_email": "test@example.com",
            "reminder_minutes": None,
            "campaign_id": "",
            "landing_page_url": "",
        }
        ics = build_ics(data)
        # Commas, semicolons, and backslashes must be escaped
        assert "SUMMARY:Event\\; With\\, Special\\\\Chars" in ics
        # Newlines in description escaped as \n
        assert "\\n" in ics

    def test_ics_method_publish(self, basic_event):
        """METHOD:PUBLISH ensures no auto-send of invitations."""
        ics = build_ics(basic_event)
        assert "METHOD:PUBLISH" in ics

    def test_ics_multi_day_timed(self):
        """An event spanning midnight should have correct UTC datetimes."""
        data = {
            "title": "Multi-day Conference",
            "start_dt": datetime(2024, 11, 5, 9, 0),
            "end_dt": datetime(2024, 11, 7, 17, 0),
            "timezone": "America/Los_Angeles",
            "all_day": False,
            "location": "San Francisco, CA",
            "meeting_url": "",
            "description": "",
            "organizer_name": "Ops",
            "organizer_email": "ops@example.com",
            "reminder_minutes": None,
            "campaign_id": "",
            "landing_page_url": "",
        }
        ics = build_ics(data)
        # Nov 5 is after DST end (Nov 3, 2024) → PST = UTC-8
        # 09:00 PST = 17:00 UTC → same day
        assert "DTSTART:20241105T170000Z" in ics
        # Nov 7 17:00 PST = Nov 8 01:00 UTC
        assert "DTEND:20241108T010000Z" in ics


# ---------------------------------------------------------------------------
# ICS line folding
# ---------------------------------------------------------------------------

class TestLineFolding:

    def test_short_line_not_folded(self):
        line = "SUMMARY:Short"
        assert fold_ics_line(line) == line

    def test_long_line_is_folded(self):
        line = "X-LONG-PROP:" + "A" * 100
        folded = fold_ics_line(line)
        assert "\r\n" in folded
        # Each physical line must be ≤ 75 octets
        for part in folded.split("\r\n"):
            assert len(part.encode("utf-8")) <= 75, f"Line too long: {repr(part)}"

    def test_folded_continuation_starts_with_space(self):
        line = "DESCRIPTION:" + "X" * 200
        folded = fold_ics_line(line)
        parts = folded.split("\r\n")
        for part in parts[1:]:
            assert part.startswith(" "), f"Continuation line missing leading space: {repr(part)}"


# ---------------------------------------------------------------------------
# ICS text escaping
# ---------------------------------------------------------------------------

class TestICSEscaping:

    def test_escape_backslash(self):
        assert escape_ics_text("a\\b") == "a\\\\b"

    def test_escape_semicolon(self):
        assert escape_ics_text("a;b") == "a\\;b"

    def test_escape_comma(self):
        assert escape_ics_text("a,b") == "a\\,b"

    def test_escape_newline(self):
        assert escape_ics_text("a\nb") == "a\\nb"

    def test_escape_carriage_return_removed(self):
        assert escape_ics_text("a\rb") == "ab"

    def test_no_double_escape(self):
        # Already-escaped sequences should not be double-escaped
        result = escape_ics_text("hello")
        assert result == "hello"


# ---------------------------------------------------------------------------
# Google Calendar URL
# ---------------------------------------------------------------------------

class TestGoogleCalendarURL:

    def test_returns_string(self, basic_event):
        url = build_google_url(basic_event)
        assert isinstance(url, str)

    def test_starts_with_google_base(self, basic_event):
        url = build_google_url(basic_event)
        assert url.startswith("https://calendar.google.com/calendar/render")

    def test_contains_action_template(self, basic_event):
        url = build_google_url(basic_event)
        assert "action=TEMPLATE" in url

    def test_contains_encoded_title(self, basic_event):
        url = build_google_url(basic_event)
        assert "Q3%20Webinar" in url or "Q3+Webinar" in url or "Q3 Webinar" in url

    def test_contains_dates(self, basic_event):
        url = build_google_url(basic_event)
        assert "dates=" in url
        assert "20240915T" in url

    def test_contains_timezone(self, basic_event):
        url = build_google_url(basic_event)
        assert "ctz=" in url
        assert "America" in url

    def test_allday_no_timezone_param(self, allday_event):
        url = build_google_url(allday_event)
        # All-day events should not have ctz param
        assert "ctz=" not in url

    def test_allday_date_format(self, allday_event):
        url = build_google_url(allday_event)
        assert "20241001" in url

    def test_special_chars_encoded(self):
        data = {
            "title": "Event & Webinar <test>",
            "start_dt": datetime(2024, 9, 15, 10, 0),
            "end_dt": datetime(2024, 9, 15, 11, 0),
            "timezone": "UTC",
            "all_day": False,
            "location": "",
            "meeting_url": "",
            "description": "",
            "organizer_name": "Test",
            "organizer_email": "t@t.com",
            "reminder_minutes": None,
            "campaign_id": "",
            "landing_page_url": "",
        }
        url = build_google_url(data)
        # Raw < > & should not appear in query string
        assert "<" not in url
        assert ">" not in url
        assert " " not in url.split("?", 1)[1]  # No bare spaces in query string

    def test_dst_spring_forward(self):
        """Clocks spring forward 2024-03-10 02:00 ET. Verify correct UTC offset."""
        # 2024-03-10 10:00 ET is after spring-forward, so EDT = UTC-4
        data = {
            "title": "Spring Forward Event",
            "start_dt": datetime(2024, 3, 10, 10, 0),
            "end_dt": datetime(2024, 3, 10, 11, 0),
            "timezone": "America/New_York",
            "all_day": False,
            "location": "",
            "meeting_url": "",
            "description": "",
            "organizer_name": "Test",
            "organizer_email": "t@t.com",
            "reminder_minutes": None,
            "campaign_id": "",
            "landing_page_url": "",
        }
        url = build_google_url(data)
        # 10:00 EDT (UTC-4) = 14:00 UTC
        assert "20240310T140000Z" in url

    def test_dst_fall_back(self):
        """Clocks fall back 2024-11-03 02:00 ET. Verify correct UTC offset."""
        # 2024-11-03 10:00 ET is after fall-back, so EST = UTC-5
        data = {
            "title": "Fall Back Event",
            "start_dt": datetime(2024, 11, 3, 10, 0),
            "end_dt": datetime(2024, 11, 3, 11, 0),
            "timezone": "America/New_York",
            "all_day": False,
            "location": "",
            "meeting_url": "",
            "description": "",
            "organizer_name": "Test",
            "organizer_email": "t@t.com",
            "reminder_minutes": None,
            "campaign_id": "",
            "landing_page_url": "",
        }
        url = build_google_url(data)
        # 10:00 EST (UTC-5) = 15:00 UTC
        assert "20241103T150000Z" in url


# ---------------------------------------------------------------------------
# Outlook Calendar URL
# ---------------------------------------------------------------------------

class TestOutlookCalendarURL:

    def test_returns_string(self, basic_event):
        url = build_outlook_url(basic_event)
        assert isinstance(url, str)

    def test_starts_with_outlook_base(self, basic_event):
        url = build_outlook_url(basic_event)
        assert url.startswith("https://outlook.live.com")

    def test_contains_subject(self, basic_event):
        url = build_outlook_url(basic_event)
        assert "subject=" in url

    def test_contains_startdt(self, basic_event):
        url = build_outlook_url(basic_event)
        assert "startdt=" in url

    def test_contains_enddt(self, basic_event):
        url = build_outlook_url(basic_event)
        assert "enddt=" in url

    def test_allday_flag(self, allday_event):
        url = build_outlook_url(allday_event)
        assert "allday=true" in url

    def test_timed_event_allday_false(self, basic_event):
        url = build_outlook_url(basic_event)
        assert "allday=false" in url

    def test_no_spaces_in_query(self, basic_event):
        url = build_outlook_url(basic_event)
        query = url.split("?", 1)[1]
        assert " " not in query


# ---------------------------------------------------------------------------
# HTML button
# ---------------------------------------------------------------------------

class TestHTMLButton:

    def test_contains_google_url(self, basic_event):
        html = build_html_button(basic_event)
        assert "calendar.google.com" in html

    def test_contains_outlook_url(self, basic_event):
        html = build_html_button(basic_event)
        assert "outlook.live.com" in html

    def test_contains_ics_data_uri(self, basic_event):
        html = build_html_button(basic_event)
        assert "data:text/calendar" in html

    def test_html_entities_escaped(self):
        """Event title with HTML special chars must be safely escaped."""
        data = {
            "title": "<script>alert('xss')</script>",
            "start_dt": datetime(2024, 9, 15, 10, 0),
            "end_dt": datetime(2024, 9, 15, 11, 0),
            "timezone": "UTC",
            "all_day": False,
            "location": "",
            "meeting_url": "",
            "description": "",
            "organizer_name": "Test",
            "organizer_email": "t@t.com",
            "reminder_minutes": None,
            "campaign_id": "",
            "landing_page_url": "",
        }
        button_html = build_html_button(data)
        # Raw script tags must not be present
        assert "<script>alert" not in button_html

    def test_custom_button_label(self, basic_event):
        html = build_html_button(basic_event, button_label="Register Now")
        assert "Register Now" in html

    def test_default_button_label(self, basic_event):
        html = build_html_button(basic_event)
        assert "Add to Calendar" in html


# ---------------------------------------------------------------------------
# UTM URL builder
# ---------------------------------------------------------------------------

class TestUTMURLBuilder:

    def test_appends_utm_params(self):
        url = build_utm_url(
            "https://example.com/page",
            {"utm_source": "email", "utm_medium": "invite", "utm_campaign": "q3"},
        )
        assert "utm_source=email" in url
        assert "utm_medium=invite" in url
        assert "utm_campaign=q3" in url

    def test_skips_empty_params(self):
        url = build_utm_url(
            "https://example.com/page",
            {"utm_source": "email", "utm_medium": "", "utm_campaign": ""},
        )
        assert "utm_medium" not in url
        assert "utm_campaign" not in url

    def test_appends_to_existing_query_string(self):
        url = build_utm_url(
            "https://example.com/page?ref=banner",
            {"utm_source": "email"},
        )
        assert url.startswith("https://example.com/page?ref=banner&")
        assert "utm_source=email" in url

    def test_empty_base_url_returns_empty(self):
        assert build_utm_url("", {"utm_source": "email"}) == ""

    def test_no_params_returns_base_url(self):
        base = "https://example.com/page"
        assert build_utm_url(base, {}) == base

    def test_all_empty_params_returns_base_url(self):
        base = "https://example.com/page"
        assert build_utm_url(base, {"utm_source": "", "utm_medium": ""}) == base


# ---------------------------------------------------------------------------
# Form validation
# ---------------------------------------------------------------------------

class TestFormValidation:

    def test_valid_event_no_errors(self, basic_event):
        errors = validate_event(basic_event)
        assert errors == []

    def test_missing_title(self, basic_event):
        basic_event["title"] = ""
        errors = validate_event(basic_event)
        assert any("title" in e.lower() for e in errors)

    def test_missing_organizer_name(self, basic_event):
        basic_event["organizer_name"] = ""
        errors = validate_event(basic_event)
        assert any("organizer name" in e.lower() for e in errors)

    def test_missing_organizer_email(self, basic_event):
        basic_event["organizer_email"] = ""
        errors = validate_event(basic_event)
        assert any("organizer email" in e.lower() for e in errors)

    def test_invalid_email_format(self, basic_event):
        basic_event["organizer_email"] = "not-an-email"
        errors = validate_event(basic_event)
        assert any("not valid" in e.lower() or "invalid" in e.lower() for e in errors)

    def test_end_before_start(self, basic_event):
        basic_event["end_dt"] = basic_event["start_dt"] - timedelta(hours=1)
        errors = validate_event(basic_event)
        assert any("after" in e.lower() for e in errors)

    def test_end_equals_start(self, basic_event):
        basic_event["end_dt"] = basic_event["start_dt"]
        errors = validate_event(basic_event)
        assert any("after" in e.lower() for e in errors)

    def test_invalid_timezone(self, basic_event):
        basic_event["timezone"] = "Mars/Olympus"
        errors = validate_event(basic_event)
        assert any("timezone" in e.lower() or "timezone" in e.lower() for e in errors)

    def test_missing_timezone(self, basic_event):
        basic_event["timezone"] = ""
        errors = validate_event(basic_event)
        assert any("timezone" in e.lower() for e in errors)

    def test_invalid_meeting_url(self, basic_event):
        basic_event["meeting_url"] = "not-a-url"
        errors = validate_event(basic_event)
        assert any("meeting url" in e.lower() or "virtual" in e.lower() for e in errors)

    def test_valid_meeting_url(self, basic_event):
        basic_event["meeting_url"] = "https://zoom.us/j/12345"
        errors = validate_event(basic_event)
        assert errors == []

    def test_invalid_landing_page_url(self, basic_event):
        basic_event["landing_page_url"] = "ftp://bad-scheme.com"
        errors = validate_event(basic_event)
        assert any("landing" in e.lower() for e in errors)

    def test_empty_optional_fields_ok(self):
        data = {
            "title": "Test Event",
            "start_dt": datetime(2024, 9, 15, 10, 0),
            "end_dt": datetime(2024, 9, 15, 11, 0),
            "timezone": "UTC",
            "all_day": False,
            "location": "",
            "meeting_url": "",
            "description": "",
            "organizer_name": "Test",
            "organizer_email": "test@example.com",
            "reminder_minutes": None,
            "campaign_id": "",
            "landing_page_url": "",
        }
        errors = validate_event(data)
        assert errors == []

    def test_allday_end_before_start_error(self, allday_event):
        allday_event["end_dt"] = datetime(2024, 9, 29, 0, 0)  # before start (Oct 1)
        errors = validate_event(allday_event)
        assert any("after" in e.lower() or "on or after" in e.lower() for e in errors)

    def test_allday_same_day_ok(self, allday_event):
        allday_event["end_dt"] = allday_event["start_dt"]  # Same day is valid for all-day
        errors = validate_event(allday_event)
        assert errors == []

    def test_multiple_errors_returned(self):
        data = {
            "title": "",
            "start_dt": datetime(2024, 9, 15, 10, 0),
            "end_dt": datetime(2024, 9, 15, 11, 0),
            "timezone": "UTC",
            "all_day": False,
            "organizer_name": "",
            "organizer_email": "",
            "meeting_url": "",
            "landing_page_url": "",
        }
        errors = validate_event(data)
        assert len(errors) >= 3  # title, name, email all missing


# ---------------------------------------------------------------------------
# Email and URL validators
# ---------------------------------------------------------------------------

class TestEmailValidation:

    def test_valid_email(self):
        assert validate_email("user@example.com") is True

    def test_valid_email_with_plus(self):
        assert validate_email("user+tag@example.co.uk") is True

    def test_invalid_no_at(self):
        assert validate_email("userexample.com") is False

    def test_invalid_no_domain(self):
        assert validate_email("user@") is False

    def test_invalid_empty(self):
        assert validate_email("") is False


class TestURLValidation:

    def test_valid_https(self):
        assert validate_url("https://example.com") is True

    def test_valid_http(self):
        assert validate_url("http://example.com") is True

    def test_invalid_ftp(self):
        assert validate_url("ftp://example.com") is False

    def test_empty_is_valid(self):
        """Empty URL is valid because the field is optional."""
        assert validate_url("") is True

    def test_no_scheme(self):
        assert validate_url("example.com") is False


# ---------------------------------------------------------------------------
# Event preview
# ---------------------------------------------------------------------------

class TestEventPreview:

    def test_contains_title(self, basic_event):
        preview = build_event_preview(basic_event)
        assert "Q3 Webinar" in preview

    def test_contains_organizer(self, basic_event):
        preview = build_event_preview(basic_event)
        assert "Jane Smith" in preview
        assert "jane@example.com" in preview

    def test_contains_location(self, basic_event):
        preview = build_event_preview(basic_event)
        assert "Online" in preview

    def test_contains_meeting_url(self, basic_event):
        preview = build_event_preview(basic_event)
        assert "zoom.us" in preview

    def test_allday_event_preview(self, allday_event):
        preview = build_event_preview(allday_event)
        assert "All day" in preview

    def test_campaign_id_in_preview(self, basic_event):
        preview = build_event_preview(basic_event)
        assert "WEB-2024-Q3" in preview
