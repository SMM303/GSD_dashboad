"""
Entry point — handles authentication and redirects to the Timeline page.
Run with:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="IOM/GSD Programme Dashboard",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

from auth.setup import is_authenticated, render_login_page, logout
from auth.audit import log_action
from components.branding import inject_luxury_styles, render_sidebar_branding
from components.freshness import render_freshness_badges


def main():
    inject_luxury_styles()

    if not is_authenticated():
        render_login_page()
        return

    # ── Authenticated ───────────────────────────────────────────────────────
    role    = st.session_state.get("user_role", "executive")
    name    = st.session_state.get("display_name", "")

    render_sidebar_branding(name, role)

    with st.sidebar:
        st.page_link("pages/1_Timeline.py",           label="📅  Timeline",           icon=None)
        st.page_link("pages/2_Stakeholder_Views.py",  label="👥  Stakeholder Views",  icon=None)
        st.page_link("pages/3_Risk_Heat_Map.py",      label="⚠️   Risk Heat Map",      icon=None)
        st.page_link("pages/4_Deliverables.py",       label="📋  Deliverables",        icon=None)
        st.page_link("pages/5_KPI_Dashboard.py",      label="📊  KPI Dashboard",       icon=None)
        st.page_link("pages/6_Files.py",              label="📁  Files",               icon=None)
        st.divider()
        if st.button("Sign Out", width="stretch"):
            log_action("logout", "session")
            logout()

    render_freshness_badges()

    # ── Home splash ─────────────────────────────────────────────────────────
    from data.queries import load_payload, fetch_deliverables
    from datetime import date

    payload = load_payload()
    prog    = payload.programme
    df_del  = fetch_deliverables()

    st.markdown(
        f'<div class="prog-title">{prog.title}</div>'
        f'<div class="prog-sub">{prog.org} · {prog.unit} · {prog.duty_station} · '
        f'Start: {prog.start_date.strftime("%d %b %Y")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Summary metrics row
    total      = len(df_del)
    submitted  = df_del["status"].isin(["submitted","under_review","approved"]).sum()
    approved   = (df_del["status"] == "approved").sum()
    overdue    = int(df_del["is_overdue"].sum())
    days_left  = int(df_del[
        df_del["status"].isin(["not_started","in_progress"])
    ]["days_to_deadline"].min()) if not df_del.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Deliverables",           f"{submitted} / {total} submitted")
    c2.metric("Approved",               approved)
    c3.metric("Overdue",                overdue,   delta_color="inverse")
    c4.metric("Days to next deadline",  days_left, delta_color="normal" if days_left >= 0 else "inverse")

    st.markdown("---")
    st.markdown(
        "Use the **sidebar** to navigate between views.  \n"
        "Role-based access is enforced — what you see depends on your role.  \n\n"
        f"Reporting to: **{prog.reporting_line.direct}** (direct) · "
        f"**{prog.reporting_line.overall}** (overall)"
    )


if __name__ == "__main__":
    main()
