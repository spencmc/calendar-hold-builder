# 📅 Marketing Calendar Hold Builder

An internal web application for marketing teams to create calendar assets for webinars, events, product launches, customer sessions, and internal meetings.

## What It Generates

| Output | Description |
|--------|-------------|
| **ICS file** | RFC 5545-compliant, works in Google Calendar, Outlook, and Apple Calendar |
| **Google Calendar link** | Pre-filled "New Event" form — no sign-in required |
| **Outlook link** | Pre-filled form for outlook.live.com or outlook.office.com |
| **HTML button** | Self-contained "Add to Calendar" dropdown for Marketo emails |
| **Event preview** | Human-readable plain-text summary |

All links are fully URL-encoded. HTML output is safely escaped. DST is handled correctly via IANA timezone data.

---

## Quick Start (Local)

### Requirements

- Python 3.11 or newer
- pip

### Install

```bash
# Clone or download the project folder, then:
pip install -r requirements.txt
```

> **Windows / some Linux distros:** `tzdata` (in requirements.txt) provides the IANA timezone database. On macOS and most Linux systems this is already present.

### Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Features

### Form Fields

| Field | Required | Notes |
|-------|----------|-------|
| Event Title | ✅ | Appears in all calendar apps |
| Start / End Date & Time | ✅ | 5-minute increment time picker |
| IANA Time Zone | ✅ | Common zones listed first; full IANA list available |
| All-day event | — | Toggle; disables time pickers |
| Physical Location | — | Address, venue name, etc. |
| Virtual Meeting URL | — | Zoom, Teams, Google Meet, etc. |
| Event Description | — | Included in ICS and links |
| Organizer Name & Email | ✅ | Embedded in ICS ORGANIZER field |
| Reminder Timing | — | Embedded as VALARM in ICS |
| Campaign / Event ID | — | Stored as `X-CAMPAIGN-ID` in ICS |
| Landing-Page URL | — | Appended to description |
| UTM Parameters | — | Appended to landing-page URL |

### Templates

Five pre-built templates are available in the sidebar:

- **Webinar** — virtual event with registration copy
- **In-Person Event** — venue + agenda structure
- **Product Launch** — announcement copy
- **Customer Session** — check-in agenda
- **Internal Meeting** — recurring sync format

### Recent Events

The last 10 generated events are stored locally in `recent_events.json`. Only the event title, dates, timezone, and campaign ID are saved — no organizer email, meeting URLs, or attendee information.

---

## Running Tests

```bash
pytest test_calendar_utils.py -v
```

With coverage:

```bash
pytest test_calendar_utils.py -v --cov=calendar_utils --cov-report=term-missing
```

### Test Coverage

The test suite covers:

- ICS structure, CRLF line endings, RFC 5545 compliance
- DST-aware datetime conversion (spring-forward and fall-back)
- UTC offset correctness for summer and winter dates
- URL encoding for Google Calendar and Outlook links
- HTML button generation and XSS escaping
- Form validation (required fields, email format, end > start, URL format)
- UTM parameter appending
- All-day and multi-day events
- ICS line folding (75-octet limit)
- ICS text escaping (semicolons, commas, backslashes, newlines)

---

## Deployment

### Streamlit Community Cloud

1. Push the project to a GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in.
3. Click **New app** → select your repo, branch, and `app.py`.
4. Click **Deploy**.

> The free tier is suitable for internal teams. For larger teams, consider a paid plan or self-hosted deployment.

**Required files in the repo root:**
- `app.py`
- `calendar_utils.py`
- `requirements.txt`

### Docker (Internal / Self-hosted)

#### Build and run

```bash
# Build the image
docker build -t calendar-hold-builder .

# Run (foreground)
docker run -p 8501:8501 calendar-hold-builder

# Run (detached)
docker run -d -p 8501:8501 --name calendar-hold calendar-hold-builder
```

Open [http://localhost:8501](http://localhost:8501).

#### Persist recent-events history across restarts

```bash
mkdir -p ./data
docker run -d -p 8501:8501 \
  -v "$(pwd)/data:/app" \
  --name calendar-hold \
  calendar-hold-builder
```

#### Docker Compose (recommended for internal infrastructure)

```yaml
# docker-compose.yml
version: "3.9"
services:
  calendar-hold:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    environment:
      - STREAMLIT_SERVER_HEADLESS=true
      - STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

```bash
docker compose up -d
```

#### Behind a reverse proxy (nginx)

```nginx
location /calendar/ {
    proxy_pass http://localhost:8501/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;
}
```

> Streamlit uses WebSockets — ensure your proxy passes `Upgrade` headers.

---

## Project Structure

```
.
├── app.py                  # Streamlit front-end
├── calendar_utils.py       # Core logic (ICS, URLs, validation)
├── test_calendar_utils.py  # Unit tests
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build
└── README.md               # This file
```

---

## RFC 5545 Compliance Notes

- All datetimes are stored in UTC (`DTSTART:...Z` format)
- `METHOD:PUBLISH` is set — no automatic invitation sending
- `VALARM` is included only when a reminder is specified
- ICS lines are folded at 75 octets per RFC 5545 §3.1
- Text values escape `;`, `,`, `\`, and newlines per §3.3.11
- All-day events use `VALUE=DATE` format; end date is exclusive (day after last day)
- A unique `UID` is generated per event using UUID4

---

## Privacy Notes

- No Google or Microsoft authentication is required or used
- The app does not send invitations or emails
- `recent_events.json` stores only: title, dates, timezone, and campaign ID
- No attendee information or organizer email is persisted to disk
- All processing is done locally in the browser/server — no data is sent to external services

---

## License

Internal use. Not for distribution.
