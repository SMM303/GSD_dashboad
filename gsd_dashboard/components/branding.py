"""
Dashboard branding — CSS injection, badge helpers, and sidebar shell.
Call inject_luxury_styles() at the top of every page render function.
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
/* ---- Fonts ------------------------------------------------------------ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"]                { font-family: 'Inter', sans-serif; }
h1, h2, h3, .stMetric label              { font-family: 'Inter', sans-serif; letter-spacing: 0; }

html, body, .stApp                       { background: #F7F8FA; color: #172033; }
.block-container                         { padding-top: 2rem; padding-bottom: 3rem; max-width: 1280px; }
p, li, label, [data-testid="stMarkdownContainer"] { color: #283548; }

/* ---- Sidebar ---------------------------------------------------------- */
[data-testid="stSidebar"]                { background: #FFFFFF; border-right: 1px solid #D7DDE8; }
[data-testid="stSidebarContent"]         { padding-top: 1.25rem; }
[data-testid="stSidebarContent"] h1      { font-size: 14px; color: #16315F; font-family:'Inter',sans-serif; font-weight:700; }
[data-testid="stSidebar"] a              { border-radius: 6px; font-weight: 500; }

.sidebar-brand {
    border-bottom: 1px solid #E4E8F0;
    padding-bottom: 14px;
    margin-bottom: 10px;
}
.sidebar-title {
    color: #16315F;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0;
}
.sidebar-sub {
    color: #667085;
    font-size: 12px;
    line-height: 1.4;
    margin-top: 3px;
}
.sidebar-session {
    background: #F5F7FA;
    border: 1px solid #E4E8F0;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 10px 0 12px;
    font-size: 12px;
    color: #344054;
}
.role-pill {
    display: inline-flex;
    border-radius: 999px;
    background: #E8F0FE;
    color: #16315F;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0;
    padding: 3px 8px;
    margin-top: 6px;
}

/* ---- Metric cards ----------------------------------------------------- */
[data-testid="metric-container"] {
    background: #FFFFFF;
    border-radius: 8px;
    padding: 16px 16px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}
[data-testid="metric-container"] label,
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"]             { color: #172033 !important; }
[data-testid="metric-container"] label    { color: #667085 !important; font-size: 12px; font-weight: 600; }
[data-testid="stMetricValue"]             { font-weight: 700; }

/* ---- Dataframe -------------------------------------------------------- */
[data-testid="stDataFrame"]               { border-radius: 8px; border: 1px solid #E2E8F0; }

/* ---- Divider ---------------------------------------------------------- */
hr                                        { border-color: #E4E8F0; margin: 1.35rem 0; }

/* ---- Buttons ---------------------------------------------------------- */
.stButton > button {
    background: #16315F; color: #FFFFFF;
    border: 1px solid #16315F; border-radius: 6px;
    font-family: 'Inter', sans-serif; font-size: 13px; font-weight: 500;
    padding: 7px 16px;
}
.stButton > button:hover                  { background: #244A86; border-color: #244A86; color: #FFFFFF; }
.stButton > button:disabled               { background: #E4E8F0; border-color: #E4E8F0; color: #98A2B3; }

/* ---- Forms and controls ----------------------------------------------- */
[data-testid="stForm"] {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 18px;
    background: #FFFFFF;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}
[data-baseweb="input"],
[data-baseweb="select"]                   { border-radius: 6px; }

/* ---- Status badges ---------------------------------------------------- */
.badge {
    display: inline-block; padding: 2px 10px;
    border-radius: 999px; font-size: 11px; font-weight: 700;
    letter-spacing: 0; text-transform: uppercase;
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
    font-family: 'Inter', sans-serif;
    font-size: 24px; color: #16315F; font-weight: 700;
    margin-bottom: 4px;
    letter-spacing: 0;
}
.prog-sub {
    font-family: 'Inter', sans-serif;
    font-size: 13px; color: #667085; margin-top: 0px;
    line-height: 1.5;
}
.home-panel {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 18px;
    min-height: 150px;
    margin-bottom: 16px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}
.home-panel h3 {
    color: #16315F;
    font-size: 15px;
    font-weight: 700;
    margin: 0 0 8px 0;
}
.home-panel p, .home-panel li {
    font-size: 13px;
    line-height: 1.5;
    color: #475467;
}
.login-header {
    font-size: 24px;
    color: #16315F;
    text-align: center;
    font-weight: 700;
    margin-top: 7vh;
    margin-bottom: 4px;
}
.login-sub {
    font-size: 13px;
    color: #667085;
    text-align: center;
    margin-bottom: 22px;
}
div[data-testid="stForm"]:has([data-testid="stFormSubmitButton"]) {
    margin-bottom: 10px;
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
    from auth.audit import log_action
    from auth.setup import get_session_remaining_minutes, logout

    with st.sidebar:
        st.markdown(
            '<div class="sidebar-brand">'
            '<div class="sidebar-title">IOM Lebanon · GSD</div>'
            '<div class="sidebar-sub">Curriculum Development Consultancy</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        role_display = {"admin": "Admin", "implementation": "Implementation", "executive": "Executive", "oversight": "Oversight"}.get(role, role.title())
        remaining = get_session_remaining_minutes()
        st.markdown(
            f'<div class="sidebar-session">'
            f'<strong>{display_name or "Signed in"}</strong><br>'
            f'<span class="role-pill">{role_display}</span><br>'
            f'<span style="display:block;margin-top:8px;">Session expires after inactivity: '
            f'<strong>{remaining} min</strong></span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Sign out", width="stretch", key="global_sign_out"):
            log_action("logout", "session")
            logout()
        st.divider()
