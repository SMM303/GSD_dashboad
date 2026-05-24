"""
Entry point — handles authentication and redirects to the Timeline page.
Run with:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="IOM GSD Programme Dashboard",
    page_icon="GSD",
    layout="wide",
    initial_sidebar_state="expanded",
)

from auth.setup import enforce_session_timeout, is_authenticated, render_login_page
from components.branding import inject_luxury_styles, render_sidebar_branding, status_badge
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
        st.page_link("pages/1_Timeline.py",           label="Timeline",           icon=None)
        st.page_link("pages/2_Stakeholder_Views.py",  label="Stakeholder Views",  icon=None)
        st.page_link("pages/3_Risk_Heat_Map.py",      label="Risk Heat Map",      icon=None)
        st.page_link("pages/4_Deliverables.py",       label="Deliverables",        icon=None)
        st.page_link("pages/5_KPI_Dashboard.py",      label="KPI Dashboard",       icon=None)
        st.page_link("pages/6_Files.py",              label="Files",               icon=None)
        if role == "admin":
            st.page_link("pages/7_Admin.py",          label="Admin",               icon=None)

    render_freshness_badges()

    # ── Home splash ─────────────────────────────────────────────────────────
    from datetime import datetime
    from data.queries import fetch_deliverables, get_programme_metadata

    prog    = get_programme_metadata()
    df_del  = fetch_deliverables()
    start_date = datetime.fromisoformat(prog["start_date"]).strftime("%d %b %Y")

    st.markdown(
        f'<div class="prog-title">{prog["title"]}</div>'
        f'<div class="prog-sub">{prog["org"]}, {prog["unit"]}, {prog["duty_station"]}, '
        f'Start: {start_date}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="overview-strip">'
        '<strong>Use this dashboard for weekly programme control.</strong> '
        'Start with deadlines and overdue items, then move into the relevant view to update evidence, risks, issues, or deliverables.'
        '</div>',
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
    c1.metric("Deliverables",           f"{submitted} of {total} submitted")
    c2.metric("Approved",               approved)
    c3.metric("Overdue",                overdue,   delta_color="inverse")
    c4.metric("Days to next deadline",  days_left, delta_color="normal" if days_left >= 0 else "inverse")

    st.divider()

    role_display = {"admin": "Admin", "implementation": "Implementation", "executive": "Executive", "oversight": "Oversight"}.get(role, role.title())
    open_deliverables = df_del[~df_del["status"].isin(["approved"])]
    next_deliverables = open_deliverables.sort_values("due_date").head(3) if not open_deliverables.empty else df_del.sort_values("due_date").head(3)
    next_items = "".join(
        f"<li><strong>{row['id']}</strong> {row['name']}<br><small>{row['due_date'].strftime('%d %b %Y')}, {row['status'].replace('_', ' ').title()}</small></li>"
        for _, row in next_deliverables.iterrows()
    )
    if not next_items:
        next_items = "<li>No deliverables available.</li>"

    urgent_lines = []
    if overdue:
        urgent_lines.append(f"<li><strong>{overdue}</strong> deliverable{'s are' if overdue != 1 else ' is'} overdue.</li>")
    if submitted:
        urgent_lines.append(f"<li><strong>{submitted}</strong> deliverable{'s have' if submitted != 1 else ' has'} been submitted or moved into review.</li>")
    if days_left < 0:
        urgent_lines.append("<li>The nearest open deadline has already passed.</li>")
    elif days_left <= 7:
        urgent_lines.append(f"<li>The nearest open deadline is in <strong>{days_left}</strong> day{'s' if days_left != 1 else ''}.</li>")
    if not urgent_lines:
        urgent_lines.append("<li>No urgent deadline flags. Continue routine review.</li>")
    urgent_html = "".join(urgent_lines)

    c_start, c_attention = st.columns([1.2, 1])
    with c_start:
        st.markdown(
            f"""
            <div class="home-panel">
              <h3>Start here</h3>
              <p>You are signed in as <strong>{role_display}</strong>. The dashboard only shows the data and actions available to this role.</p>
              <p>Reporting line: <strong>{prog["reporting_direct"]}</strong> direct, <strong>{prog["reporting_overall"]}</strong> overall.</p>
              <div class="status-key">
                {status_badge("not_started")}
                {status_badge("in_progress")}
                {status_badge("submitted")}
                {status_badge("approved")}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c_attention:
        st.markdown(
            f"""
            <div class="home-panel">
              <h3>Needs attention</h3>
              <ul class="attention-list">{urgent_html}</ul>
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
              <p>The top numbers summarize progress. Badges show workflow stage. Editable forms only appear where your role can make changes.</p>
              <p>Sessions expire automatically after inactivity for security. Sign out from the sidebar when finished.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Common next actions")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.markdown('<div class="home-panel compact"><div class="action-title">Check the timeline</div><div class="action-copy">Review phases, milestones, and upcoming dates.</div></div>', unsafe_allow_html=True)
        st.page_link("pages/1_Timeline.py", label="Open Timeline")
    with a2:
        st.markdown('<div class="home-panel compact"><div class="action-title">Review deliverables</div><div class="action-copy">See due dates, quality gates, and module progress.</div></div>', unsafe_allow_html=True)
        st.page_link("pages/4_Deliverables.py", label="Open Deliverables")
    with a3:
        st.markdown('<div class="home-panel compact"><div class="action-title">Scan risk status</div><div class="action-copy">Focus on high-score risks and escalation triggers.</div></div>', unsafe_allow_html=True)
        st.page_link("pages/3_Risk_Heat_Map.py", label="Open Risks")
    with a4:
        st.markdown('<div class="home-panel compact"><div class="action-title">Upload evidence</div><div class="action-copy">Keep supporting files connected to the programme record.</div></div>', unsafe_allow_html=True)
        st.page_link("pages/6_Files.py", label="Open Files")


if __name__ == "__main__":
    main()
