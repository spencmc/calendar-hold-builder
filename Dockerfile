# ── Marketing Calendar Hold Builder — Dockerfile ───────────────────────────
# Multi-stage build for a lean production image.
#
# Build:  docker build -t calendar-hold-builder .
# Run:    docker run -p 8501:8501 calendar-hold-builder
# Open:   http://localhost:8501
# ────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# Install tzdata for full IANA timezone support (required by zoneinfo)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

# ── Dependencies ─────────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────────────────────
COPY app.py calendar_utils.py ./

# The recent_events.json history file is written at runtime.
# Mount a volume at /app if you want the history to persist across container restarts:
#   docker run -p 8501:8501 -v $(pwd)/data:/app calendar-hold-builder

# Switch to non-root user
USER appuser

# ── Streamlit config ──────────────────────────────────────────────────────────
# Disable the "Deploy" button and telemetry for internal deployments.
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
