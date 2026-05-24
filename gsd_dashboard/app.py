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

from auth.setup import enforce_session_timeout, is_authenticated, render_login_page
from components.branding import inject_luxury_styles, render_sidebar_branding
from components.freshness import render_freshness_badges


def main():
    inject_luxury_styles()

    if not is_authenticated() or not enforce_session_timeout():
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
        if role == "admin":
            st.page_link("pages/7_Admin.py",          label="🔐  Admin",               icon=None)

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
    st.divider()

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

    st.divider()

    role_display = {"admin": "Admin", "implementation": "Implementation", "executive": "Executive", "oversight": "Oversight"}.get(role, role.title())
    next_deliverables = df_del.sort_values("due_date").head(3)
    next_items = "".join(
        f"<li><strong>{row['id']}</strong> {row['name']} · {row['due_date'].strftime('%d %b %Y')} · {row['status'].replace('_', ' ').title()}</li>"
        for _, row in next_deliverables.iterrows()
    )
    if not next_items:
        next_items = "<li>No deliverables available.</li>"

    st.markdown(
        f"""
        <div class="home-panel">
          <h3>Start here</h3>
          <p>Your current role is <strong>{role_display}</strong>. Use the sidebar to move between timeline, stakeholder, risk, deliverable, KPI, and file views. Each view only shows the data and actions available to your role.</p>
          <p>Reporting line: <strong>{prog.reporting_line.direct}</strong> direct · <strong>{prog.reporting_line.overall}</strong> overall.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_next, col_access = st.columns([1.4, 1])
    with col_next:
        st.markdown(
            f"""
            <div class="home-panel">
              <h3>Next deliverables</h3>
              <ul>{next_items}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_access:
        st.markdown(
            """
            <div class="home-panel">
              <h3>How to read the dashboard</h3>
              <p>The top numbers summarize progress. Status badges show the current workflow stage. Editable forms are available only where your role is allowed to make changes.</p>
              <p>Sessions expire automatically after inactivity for security.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
