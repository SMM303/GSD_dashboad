"""
Luxury branding — CSS injection, fonts, badge helpers.
Call inject_luxury_styles() at the top of every page render function.
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
/* ---- Fonts ------------------------------------------------------------ */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Inter:wght@300;400;500;600&display=swap');

html, body, [class*="css"]                { font-family: 'Inter', sans-serif; }
h1, h2, h3, .stMetric label              { font-family: 'Playfair Display', serif; letter-spacing: 0.02em; }

/* ---- Sidebar ---------------------------------------------------------- */
[data-testid="stSidebar"]                { background: #EEE9E0; border-right: 1px solid #D2CBBC; }
[data-testid="stSidebarContent"] h1      { font-size: 14px; color: #1B3A6B; font-family:'Inter',sans-serif; font-weight:600; }

/* ---- Metric cards ----------------------------------------------------- */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1B3A6B 0%, #2D5A9E 100%);
    border-radius: 8px;
    padding: 18px 16px;
    border: 1px solid rgba(255,255,255,0.14);
}
[data-testid="metric-container"] label,
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"]             { color: #FFFFFF !important; }

/* ---- Dataframe -------------------------------------------------------- */
[data-testid="stDataFrame"]               { border-radius: 6px; }

/* ---- Divider ---------------------------------------------------------- */
hr                                        { border-color: #D2CBBC; }

/* ---- Buttons ---------------------------------------------------------- */
.stButton > button {
    background: #1B3A6B; color: #FFFFFF;
    border: none; border-radius: 6px;
    font-family: 'Inter', sans-serif; font-size: 13px; font-weight: 500;
    padding: 6px 18px;
}
.stButton > button:hover                  { background: #2D5A9E; }

/* ---- Status badges ---------------------------------------------------- */
.badge {
    display: inline-block; padding: 2px 10px;
    border-radius: 12px; font-size: 11px; font-weight: 600;
    letter-spacing: 0.05em; text-transform: uppercase;
}
.badge-not_started   { background:#e5e7eb; color:#374151; }
.badge-in_progress   { background:#dbeafe; color:#1e40af; }
.badge-submitted     { background:#fef3c7; color:#92400e; }
.badge-under_review  { background:#ede9fe; color:#5b21b6; }
.badge-approved      { background:#d1fae5; color:#065f46; }
.badge-rejected      { background:#fee2e2; color:#991b1b; }
.badge-active        { background:#fee2e2; color:#991b1b; }
.badge-mitigated     { background:#d1fae5; color:#065f46; }
.badge-escalated     { background:#fef3c7; color:#92400e; }
.badge-closed        { background:#e5e7eb; color:#374151; }
.badge-confirmed     { background:#d1fae5; color:#065f46; }
.badge-pending       { background:#fef3c7; color:#92400e; }
.badge-to_be_requested { background:#e5e7eb; color:#374151; }
.badge-high          { background:#fee2e2; color:#991b1b; }
.badge-medium        { background:#fef3c7; color:#92400e; }
.badge-low           { background:#d1fae5; color:#065f46; }
.badge-open          { background:#fee2e2; color:#991b1b; }
.badge-resolved      { background:#d1fae5; color:#065f46; }

/* ---- Programme title band --------------------------------------------- */
.prog-title {
    font-family: 'Playfair Display', serif;
    font-size: 22px; color: #1B3A6B; font-weight: 600;
    margin-bottom: 0px;
}
.prog-sub {
    font-family: 'Inter', sans-serif;
    font-size: 12px; color: #6b7280; margin-top: 0px;
}
</style>
"""


def inject_luxury_styles() -> None:
    """Inject luxury CSS. Call once at the top of every page render."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Badge helpers
# ---------------------------------------------------------------------------

def badge(label: str, status: str) -> str:
    """Return an HTML badge string for inline markdown rendering."""
    slug = status.lower().replace(" ", "_")
    return f'<span class="badge badge-{slug}">{label}</span>'


def status_badge(status: str) -> str:
    label_map = {
        "not_started":   "Not Started",
        "in_progress":   "In Progress",
        "submitted":     "Submitted",
        "under_review":  "Under Review",
        "approved":      "Approved",
        "rejected":      "Rejected",
        "active":        "Active",
        "mitigated":     "Mitigated",
        "escalated":     "Escalated",
        "closed":        "Closed",
        "confirmed":     "Confirmed",
        "pending":       "Pending",
        "to_be_requested": "To Request",
        "open":          "Open",
        "resolved":      "Resolved",
        "high":          "High",
        "medium":        "Medium",
        "low":           "Low",
    }
    label = label_map.get(status, status.replace("_", " ").title())
    return badge(label, status)


# ---------------------------------------------------------------------------
# Sidebar branding
# ---------------------------------------------------------------------------

def render_sidebar_branding(display_name: str, role: str) -> None:
    inject_luxury_styles()
    with st.sidebar:
        st.markdown(
            '<div class="prog-title">IOM Lebanon · GSD</div>'
            '<div class="prog-sub">Curriculum Development Consultancy</div>',
            unsafe_allow_html=True,
        )
        st.divider()
        role_display = {"implementation": "Implementation", "executive": "Executive", "oversight": "Oversight"}.get(role, role.title())
        st.caption(f"Signed in as **{display_name}**  \nRole: **{role_display}**")
        st.divider()
