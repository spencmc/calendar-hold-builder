from __future__ import annotations

"""
styles.py
---------
Global CSS and UI helper components for the Marketing Calendar Hold Builder.

All visual styling lives here — import and call load_css() at the top of
every page. Use the helper functions (page_header, section_header, etc.)
in place of st.title() / st.subheader() for a consistent look.

Brand palette
  Accent     #EF4D36  coral red — CTAs, highlights
  Dark       #1C1C2E  midnight navy — sidebar, headers
  Page bg    #F8F7F5  warm off-white
  Card bg    #FFFFFF  form sections / cards
  Border     #E8E8E4  subtle dividers
"""

import json as _json
import streamlit as st

# ---------------------------------------------------------------------------
# Brand tokens
# ---------------------------------------------------------------------------

ACCENT       = "#EF4D36"
ACCENT_DARK  = "#D93E28"
ACCENT_LIGHT = "#FFF2F0"
DARK         = "#1C1C2E"
DARK_2       = "#2D2D44"
PAGE_BG      = "#F8F7F5"
CARD_BG      = "#FFFFFF"
BORDER       = "#E8E8E4"
TEXT         = "#1A1A2E"
MUTED        = "#6B7280"

EVENT_COLORS = {
    "Webinar":          "#0066CC",
    "In-Person Event":  "#28A745",
    "Product Launch":   "#FF6B35",
    "Customer Session": "#9B59B6",
    "Internal Meeting": "#6C757D",
    "Other":            "#17A2B8",
}

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def load_css() -> None:
    """Inject all custom CSS into the page. Call once per page, before any UI."""
    st.markdown(f"""
<style>

/* ── Fonts ──────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Page shell ─────────────────────────────────────────────────────── */
.stApp {{
    background: {PAGE_BG};
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}
.block-container {{
    padding-top: 1.5rem !important;
    padding-bottom: 4rem !important;
    max-width: 980px !important;
}}

/* ── Sidebar background ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: {DARK} !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    border-right: 1px solid rgba(255,255,255,0.06);
}}

/* Sidebar text colours */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {{
    color: rgba(255,255,255,0.8) !important;
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
    color: white !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.08) !important;
    margin: 10px 0 !important;
}}

/* Sidebar selectbox */
[data-testid="stSidebar"] .stSelectbox > div > div {{
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 8px !important;
    color: rgba(255,255,255,0.9) !important;
}}

/* Sidebar expanders */
[data-testid="stSidebar"] .streamlit-expanderHeader {{
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: rgba(255,255,255,0.85) !important;
}}
[data-testid="stSidebar"] .streamlit-expanderContent {{
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-top: none !important;
}}

/* Sidebar template buttons */
[data-testid="stSidebar"] .stButton > button {{
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: rgba(255,255,255,0.85) !important;
    font-size: 0.78rem !important;
    padding: 6px 4px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
    text-align: left !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(239,77,54,0.18) !important;
    border-color: rgba(239,77,54,0.35) !important;
    color: white !important;
}}

/* ── Sidebar nav ────────────────────────────────────────────────────── */
[data-testid="stSidebarNav"] {{
    padding-top: 0 !important;
}}
[data-testid="stSidebarNav"] ul {{
    padding: 0 !important;
    margin: 0 !important;
}}

/* Hide the main "app" nav item — it's replaced by the brand block below */
[data-testid="stSidebarNav"] ul li:first-child {{
    display: none !important;
}}

[data-testid="stSidebarNav"] a {{
    border-radius: 8px !important;
    padding: 7px 12px !important;
    color: rgba(255,255,255,0.65) !important;
    text-decoration: none !important;
    transition: all 0.15s ease !important;
    display: flex !important;
    align-items: center !important;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: rgba(255,255,255,0.08) !important;
    color: white !important;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: rgba(239,77,54,0.18) !important;
    color: white !important;
    border-left: 3px solid {ACCENT} !important;
    padding-left: 9px !important;
}}

/* ── Primary CTA button ─────────────────────────────────────────────── */
.stFormSubmitButton > button,
button[kind="primary"] {{
    background: {ACCENT} !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    letter-spacing: 0.01em;
    box-shadow: 0 4px 16px rgba(239,77,54,0.28) !important;
    transition: all 0.15s ease !important;
}}
.stFormSubmitButton > button:hover,
button[kind="primary"]:hover {{
    background: {ACCENT_DARK} !important;
    box-shadow: 0 6px 24px rgba(239,77,54,0.38) !important;
    transform: translateY(-1px) !important;
}}
.stFormSubmitButton > button:active,
button[kind="primary"]:active {{
    transform: translateY(0) !important;
}}

/* ── Secondary buttons (main page) ─────────────────────────────────── */
.main .stButton > button,
.main .stButton > button[kind="secondary"] {{
    border: 1.5px solid {BORDER} !important;
    border-radius: 8px !important;
    background: white !important;
    color: {TEXT} !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
}}
.main .stButton > button:hover,
.main .stButton > button[kind="secondary"]:hover {{
    border-color: {ACCENT} !important;
    color: {ACCENT} !important;
    background: {ACCENT_LIGHT} !important;
}}

/* ── Text inputs & textareas ────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {{
    border-radius: 8px !important;
    border: 1.5px solid {BORDER} !important;
    background: white !important;
    color: {TEXT} !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {ACCENT} !important;
    box-shadow: 0 0 0 3px rgba(239,77,54,0.1) !important;
    outline: none !important;
}}

/* Input / selectbox labels — small caps style */
.stTextInput > label,
.stTextArea > label,
.stSelectbox > label,
.stDateInput > label,
.stTimeInput > label,
.stCheckbox > label,
.stRadio > label,
.stMultiSelect > label {{
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: {MUTED} !important;
}}

/* ── Selectbox ──────────────────────────────────────────────────────── */
.stSelectbox > div > div {{
    border: 1.5px solid {BORDER} !important;
    border-radius: 8px !important;
    background: white !important;
}}
.stSelectbox > div > div:focus-within {{
    border-color: {ACCENT} !important;
    box-shadow: 0 0 0 3px rgba(239,77,54,0.1) !important;
}}

/* ── Date & time inputs ─────────────────────────────────────────────── */
.stDateInput > div > div > input,
.stTimeInput > div > div > input {{
    border-radius: 8px !important;
    border: 1.5px solid {BORDER} !important;
    background: white !important;
}}

/* ── Multiselect ────────────────────────────────────────────────────── */
.stMultiSelect > div > div {{
    border: 1.5px solid {BORDER} !important;
    border-radius: 8px !important;
    background: white !important;
}}

/* ── Tabs ───────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: #ECEAE7;
    padding: 4px;
    border-radius: 12px;
    gap: 2px;
    border-bottom: none !important;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 8px 18px !important;
    font-weight: 500 !important;
    font-size: 0.87rem !important;
    color: {MUTED} !important;
    transition: all 0.15s ease !important;
}}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
    background: white !important;
    color: {TEXT} !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08) !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{ display: none !important; }}
.stTabs [data-baseweb="tab-border"]    {{ display: none !important; }}

/* ── Expanders ──────────────────────────────────────────────────────── */
.streamlit-expanderHeader {{
    background: white !important;
    border: 1.5px solid {BORDER} !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    transition: border-color 0.15s ease !important;
}}
.streamlit-expanderHeader:hover {{
    border-color: {ACCENT} !important;
}}
details[open] > summary.streamlit-expanderHeader {{
    border-radius: 10px 10px 0 0 !important;
    border-bottom: none !important;
}}
.streamlit-expanderContent {{
    background: white !important;
    border: 1.5px solid {BORDER} !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    padding: 16px !important;
}}

/* ── Download button ────────────────────────────────────────────────── */
.stDownloadButton > button {{
    border-radius: 8px !important;
    border: 1.5px solid {ACCENT} !important;
    color: {ACCENT} !important;
    font-weight: 600 !important;
    background: white !important;
    transition: all 0.15s ease !important;
}}
.stDownloadButton > button:hover {{
    background: {ACCENT} !important;
    color: white !important;
}}

/* ── Alert / info / success boxes ──────────────────────────────────── */
.stAlert {{ border-radius: 10px !important; }}

/* ── Metric ─────────────────────────────────────────────────────────── */
[data-testid="stMetric"],
[data-testid="metric-container"] {{
    background: white;
    border: 1.5px solid {BORDER};
    border-radius: 12px;
    padding: 14px 18px;
}}

/* ── Dividers ───────────────────────────────────────────────────────── */
hr {{
    border: none !important;
    border-top: 1px solid {BORDER} !important;
    margin: 20px 0 !important;
}}

/* ── Code blocks ────────────────────────────────────────────────────── */
.stCodeBlock pre {{
    border-radius: 10px !important;
    border: 1.5px solid {BORDER} !important;
}}

/* ── File uploader ──────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    border: 2px dashed {BORDER} !important;
    border-radius: 10px !important;
    background: white !important;
    transition: border-color 0.15s ease !important;
}}
[data-testid="stFileUploader"]:hover {{
    border-color: {ACCENT} !important;
}}

/* ── Hide Streamlit chrome ──────────────────────────────────────────── */
#MainMenu {{ visibility: hidden; }}
footer   {{ visibility: hidden; }}
[data-testid="stDecoration"] {{ display: none !important; }}
[data-testid="stHeader"] {{ background: transparent !important; box-shadow: none !important; }}

</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# UI helper components
# ---------------------------------------------------------------------------

def page_header(title: str, subtitle: str = "", logo: str = "📅") -> None:
    """Dark gradient hero header — call once at the top of each page."""
    st.markdown(
        f'<div style="background:linear-gradient(135deg,{DARK} 0%,{DARK_2} 100%);border-radius:16px;padding:28px 36px;margin-bottom:28px;border:1px solid rgba(255,255,255,0.07);box-shadow:0 4px 24px rgba(0,0,0,0.12);">'
        f'<div style="display:flex;align-items:center;gap:18px;">'
        f'<div style="font-size:2.8rem;line-height:1;flex-shrink:0;">{logo}</div>'
        f'<div>'
        f'<div style="color:white;font-size:1.6rem;font-weight:700;letter-spacing:-0.02em;font-family:Inter,sans-serif;line-height:1.15;">{title}</div>'
        f'<div style="color:rgba(255,255,255,0.45);font-size:0.88rem;margin-top:6px;font-family:Inter,sans-serif;">{subtitle}</div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )


def section_header(title: str, icon: str = "", subtitle: str = "") -> None:
    """Red-accented section heading — replaces st.subheader() inside forms."""
    icon_part = f"{icon} " if icon else ""
    sub_part  = f'<div style="color:{MUTED};font-size:0.8rem;margin-top:3px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div style="display:flex;align-items:flex-start;gap:12px;margin:28px 0 14px 0;">'
        f'<div style="width:4px;min-height:26px;background:{ACCENT};border-radius:2px;flex-shrink:0;margin-top:3px;"></div>'
        f'<div><div style="font-weight:700;font-size:0.82rem;color:{TEXT};text-transform:uppercase;letter-spacing:0.06em;font-family:Inter,sans-serif;">{icon_part}{title}</div>{sub_part}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    """Product brand block at the top of the sidebar content area."""
    st.markdown(
        f'<div style="padding:12px 4px 14px 4px;border-bottom:1px solid rgba(255,255,255,0.08);margin-bottom:8px;">'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<div style="background:{ACCENT};border-radius:9px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;box-shadow:0 3px 10px rgba(239,77,54,0.35);">📅</div>'
        f'<div>'
        f'<div style="color:white;font-weight:700;font-size:0.88rem;font-family:Inter,sans-serif;line-height:1.2;letter-spacing:-0.01em;">Calendar Hold Builder</div>'
        f'<div style="color:rgba(255,255,255,0.3);font-size:0.68rem;font-family:Inter,sans-serif;margin-top:1px;">G2 Marketing</div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )


def sidebar_label(text: str) -> None:
    """Small uppercase section label inside the sidebar."""
    st.markdown(
        f'<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:rgba(255,255,255,0.3);margin:20px 0 8px 0;font-family:Inter,sans-serif;">{text}</div>',
        unsafe_allow_html=True,
    )


def results_banner(title: str, subtitle: str = "") -> None:
    """Green success banner shown after generating calendar assets."""
    sub = f'<div style="color:rgba(255,255,255,0.55);font-size:0.82rem;margin-top:3px;font-family:Inter,sans-serif;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#064E3B 0%,#065F46 100%);border-radius:12px;padding:18px 24px;margin:20px 0;border:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;gap:16px;box-shadow:0 4px 16px rgba(0,0,0,0.12);">'
        f'<div style="font-size:1.8rem;flex-shrink:0;line-height:1;">📅</div>'
        f'<div><div style="color:white;font-weight:700;font-size:0.95rem;font-family:Inter,sans-serif;">{title}</div>{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def event_type_badge(event_type: str) -> str:
    """Return inline HTML for a coloured event-type pill badge."""
    color = EVENT_COLORS.get(event_type, "#17A2B8")
    return (
        f"<span style='background:{color};color:white;padding:3px 11px;"
        f"border-radius:20px;font-size:11px;font-weight:600;"
        f"letter-spacing:0.04em;font-family:Inter,sans-serif;'>{event_type}</span>"
    )


# ---------------------------------------------------------------------------
# Copy-to-clipboard button
# ---------------------------------------------------------------------------

_copy_counter = 0


def copy_button(text: str, label: str = "📋 Copy", key: str = "") -> None:
    """Styled copy-to-clipboard button (no Streamlit state required)."""
    global _copy_counter
    _copy_counter += 1
    uid = key or f"cpbtn_{_copy_counter}"
    js_text = _json.dumps(text)

    html = f"""
<script>
function cp_{uid}() {{
    var t = {js_text};
    var btn = document.getElementById('{uid}');
    if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(t).then(function() {{
            btn.innerText = '✅ Copied!';
            btn.style.background = '#D1FAE5';
            btn.style.borderColor = '#34D399';
            btn.style.color = '#065F46';
            setTimeout(function() {{
                btn.innerText = {_json.dumps(label)};
                btn.style.background = 'white';
                btn.style.borderColor = '{BORDER}';
                btn.style.color = '{TEXT}';
            }}, 1600);
        }});
    }} else {{
        var ta = document.createElement('textarea');
        ta.value = t;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        btn.innerText = '✅ Copied!';
        setTimeout(function() {{ btn.innerText = {_json.dumps(label)}; }}, 1600);
    }}
}}
</script>
<button id="{uid}" onclick="cp_{uid}()" style="
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    background: white;
    color: {TEXT};
    transition: all 0.15s ease;
    font-family: 'Inter', sans-serif;
    line-height: 1;
">{label}</button>
"""
    st.components.v1.html(html, height=44)
