"""
Page 1 — Programme Timeline

Shows the luxury Gantt with phase bands, deliverable markers,
milestone indicators, consultation windows, and a Today line.
"""
import streamlit as st

st.set_page_config(page_title="Timeline · GSD Dashboard", layout="wide")

from auth.setup import require_auth, get_user_role, get_display_name
from auth.audit import log_action
from components.branding import inject_luxury_styles, render_sidebar_branding, status_badge
from components.freshness import render_freshness_badges
from components.charts import build_timeline_figure
from data.queries import (
    load_payload, fetch_phases, fetch_deliverables,
    fetch_milestones, write_milestone_complete,
)

require_auth()
inject_luxury_styles()

role = get_user_role()
name = get_display_name()
render_sidebar_branding(name, role)

with st.sidebar:
    st.page_link("app.py",                            label="🏠  Home")
    st.page_link("pages/1_Timeline.py",               label="📅  Timeline")
    st.page_link("pages/2_Stakeholder_Views.py",      label="👥  Stakeholder Views")
    st.page_link("pages/3_Risk_Heat_Map.py",          label="⚠️   Risk Heat Map")
    st.page_link("pages/4_Deliverables.py",           label="📋  Deliverables")
    st.page_link("pages/5_KPI_Dashboard.py",          label="📊  KPI Dashboard")
    st.page_link("pages/6_Files.py",                  label="📁  Files")
    render_freshness_badges()

log_action("view_timeline", "page", "timeline")

# ── Header ──────────────────────────────────────────────────────────────────
payload   = load_payload()
prog      = payload.programme
prog_start = prog.start_date

st.markdown(
    '<div class="prog-title">Programme Timeline</div>'
    '<div class="prog-sub">Phase bands · Deliverable deadlines · Milestones · Consultation windows</div>',
    unsafe_allow_html=True,
)
st.divider()

# ── Data ─────────────────────────────────────────────────────────────────────
phases_df      = fetch_phases()
deliverables_df = fetch_deliverables()
milestones_df   = fetch_milestones()

# ── Gantt ────────────────────────────────────────────────────────────────────
fig = build_timeline_figure(phases_df, deliverables_df, milestones_df, prog_start)
st.plotly_chart(fig, width="stretch")

st.divider()

# ── Phase status table ───────────────────────────────────────────────────────
col_l, col_r = st.columns([2, 1])

with col_l:
    st.subheader("Phase Summary")
    for _, p in phases_df.iterrows():
        badge_html = status_badge(p["status"])
        st.markdown(
            f"**{p['name']}** &nbsp;&nbsp; {badge_html} &nbsp;&nbsp; "
            f"Weeks {p['start_week']}–{p['end_week']} &nbsp;·&nbsp; "
            f"{p['abs_start'].strftime('%d %b')} – {p['abs_end'].strftime('%d %b %Y')}",
            unsafe_allow_html=True,
        )

with col_r:
    st.subheader("Deliverable Calendar")
    for _, d in deliverables_df.iterrows():
        badge_html = status_badge(d["status"])
        overdue_flag = " 🔴" if d["is_overdue"] else ""
        st.markdown(
            f"**{d['id']}** {d['name']}  \n"
            f"{badge_html} &nbsp; Due: {d['due_date'].strftime('%d %b %Y')}"
            f" &nbsp; ({d['days_to_deadline']:+d} days){overdue_flag}",
            unsafe_allow_html=True,
        )
        st.markdown("")

st.divider()

# ── Milestone checklist (Implementation only) ────────────────────────────────
if role == "implementation":
    st.subheader("Milestones")
    st.caption("Check off milestones as they are completed. Changes persist immediately.")

    cols = st.columns(2)
    for i, (_, ms) in enumerate(milestones_df.iterrows()):
        col = cols[i % 2]
        with col:
            checked = ms["completed"]
            icon    = "✅" if checked else "⬜"
            label   = f"{icon} **{ms['description']}**  \n"
            label  += f"Target: {ms['target_date'].strftime('%d %b %Y')}"
            if checked and ms["completed_date"]:
                label += f" · Done: {ms['completed_date']}"

            if not checked:
                if st.button(f"Mark complete — {ms['id']}", key=f"ms_{ms['id']}",
                             width="stretch"):
                    write_milestone_complete(ms["id"])
                    log_action("complete_milestone", "milestone", ms["id"])
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.success(label)

else:
    # Executive / Oversight: read-only count
    st.subheader("Milestone Progress")
    completed = int(milestones_df["completed"].sum())
    total     = len(milestones_df)
    st.metric("Milestones complete", f"{completed} / {total}")
    st.progress(completed / total if total else 0)
