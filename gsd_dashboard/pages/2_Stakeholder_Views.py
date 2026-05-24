"""
Page 2 — Stakeholder Views

Role-filtered view of the stakeholder map.
Implementation: full detail including PII (contact names, titles).
Executive: org unit, category, access status, engagement score.
Oversight: org unit and category only.

Includes the engagement radar chart and a consultation update form
(Implementation role only).
"""
import streamlit as st

st.set_page_config(page_title="Stakeholder Views · GSD Dashboard", layout="wide")

import pandas as pd

from auth.setup import require_auth, get_user_role, get_display_name
from auth.audit import log_action
from components.branding import inject_luxury_styles, render_sidebar_branding, status_badge
from components.freshness import render_freshness_badges
from components.charts import build_engagement_radar
from data.queries import (
    fetch_stakeholders, fetch_issues,
    write_stakeholder_update, write_issue, write_issue_status,
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
    render_freshness_badges()

log_action("view_stakeholder_map", "page", "stakeholder_views")

st.markdown(
    '<div class="prog-title">Stakeholder Views</div>'
    '<div class="prog-sub">Engagement map · Consultation status · Access tracking</div>',
    unsafe_allow_html=True,
)
st.divider()

# ── Data ─────────────────────────────────────────────────────────────────────
stakeholders_df = fetch_stakeholders(role)
issues_df       = fetch_issues()

# ── Engagement summary metrics ───────────────────────────────────────────────
TOTAL_CATEGORIES = 7
confirmed_cats = 0
if "actor_category" in stakeholders_df.columns and "access_status" in stakeholders_df.columns:
    confirmed_cats = stakeholders_df[
        stakeholders_df["access_status"] == "confirmed"
    ]["actor_category"].nunique()

engagement_pct = round(confirmed_cats / TOTAL_CATEGORIES * 100, 1)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Categories engaged",   f"{confirmed_cats} / {TOTAL_CATEGORIES}")
c2.metric("Engagement %",          f"{engagement_pct}%")
c3.metric("Total stakeholders",   len(stakeholders_df))
pending = int((stakeholders_df.get("access_status", pd.Series([])) == "pending").sum()) if "access_status" in stakeholders_df.columns else 0
c4.metric("Pending confirmation", pending)

st.divider()

# ── Radar chart + stakeholder table ─────────────────────────────────────────
col_chart, col_table = st.columns([1, 2])

with col_chart:
    st.subheader("Engagement by Category")
    radar_fig = build_engagement_radar(stakeholders_df)
    st.plotly_chart(radar_fig, width="stretch")

with col_table:
    st.subheader("Stakeholder Map")

    # Category filter
    if "actor_category" in stakeholders_df.columns:
        cats     = ["All"] + sorted(stakeholders_df["actor_category"].unique().tolist())
        sel_cat  = st.selectbox("Filter by category", cats, key="stk_cat_filter")
        display  = stakeholders_df if sel_cat == "All" else stakeholders_df[stakeholders_df["actor_category"] == sel_cat]
    else:
        display = stakeholders_df

    # Column display labels
    col_labels = {
        "org_unit":            "Organisation / Unit",
        "contact_name":        "Contact Name",
        "contact_title":       "Title",
        "actor_category":      "Category",
        "role":                "Role",
        "method":              "Method",
        "access_status":       "Access Status",
        "consultation_window": "Consultation Window",
        "engagement_score":    "Engagement Score",
    }
    show_cols = [c for c in col_labels if c in display.columns]
    display   = display[show_cols].rename(columns=col_labels)

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "Engagement Score": st.column_config.NumberColumn("Engagement Score", format="%.1f"),
        },
    )

st.divider()

# ── Issue Log (role-filtered) ─────────────────────────────────────────────────
if role in ("implementation",):
    st.subheader("Issue Log")

    col_filters = st.columns(3)
    with col_filters[0]:
        status_filter = st.selectbox("Status", ["All", "open", "resolved", "escalated"], key="iss_status")
    with col_filters[1]:
        risk_filter = st.selectbox("Risk Level", ["All", "high", "medium", "low"], key="iss_risk")
    with col_filters[2]:
        cat_filter = st.selectbox("Category", ["All", "access", "document", "coordination", "scope"], key="iss_cat")

    filtered = issues_df.copy()
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]
    if risk_filter != "All":
        filtered = filtered[filtered["risk_level"] == risk_filter]
    if cat_filter != "All":
        filtered = filtered[filtered["category"] == cat_filter]

    st.dataframe(
        filtered[["id","date_raised","description","category","risk_level","assigned_to","target_date","status","is_overdue"]],
        width="stretch",
        hide_index=True,
        column_config={
            "id":          "Issue #",
            "date_raised": st.column_config.DateColumn("Date Raised"),
            "target_date": st.column_config.DateColumn("Target Date"),
            "is_overdue":  st.column_config.CheckboxColumn("Overdue"),
        },
    )

    # ── Mark issue resolved ──────────────────────────────────────────────────
    open_issues = issues_df[issues_df["status"] == "open"]
    if not open_issues.empty:
        st.subheader("Resolve an Issue")
        with st.form("resolve_issue_form"):
            opts   = {int(r["id"]): f"#{r['id']} — {str(r['description'])[:60]}" for _, r in open_issues.iterrows()}
            sel_id = st.selectbox("Select issue", list(opts.keys()), format_func=lambda x: opts[x])
            new_status = st.selectbox("New status", ["resolved", "escalated"])
            if st.form_submit_button("Update Issue"):
                write_issue_status(sel_id, new_status)
                log_action("update_issue_status", "issue", str(sel_id))
                st.cache_data.clear()
                st.success(f"Issue #{sel_id} marked as {new_status}.")
                st.rerun()

    # ── Add new issue ─────────────────────────────────────────────────────────
    st.subheader("Log New Issue")
    with st.form("new_issue_form"):
        desc       = st.text_area("Description", placeholder="Describe the issue clearly…")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            category = st.selectbox("Category", ["access","document","coordination","scope"])
        with col_b:
            risk_level = st.selectbox("Risk Level", ["high","medium","low"])
        with col_c:
            from datetime import date, timedelta
            target_date = st.date_input("Target Resolution", value=date.today() + timedelta(days=5))
        assigned_to = st.text_input("Assigned to", value=st.session_state.get("display_name",""))
        if st.form_submit_button("Log Issue"):
            if desc.strip():
                write_issue({
                    "date_raised": date.today().isoformat(),
                    "description": desc.strip(),
                    "category":    category,
                    "risk_level":  risk_level,
                    "assigned_to": assigned_to,
                    "target_date": target_date.isoformat(),
                    "status":      "open",
                })
                log_action("add_issue", "issue", "new")
                st.cache_data.clear()
                st.success("Issue logged.")
                st.rerun()
            else:
                st.warning("Description cannot be empty.")

elif role == "oversight":
    st.subheader("Open High-Risk Issues")
    high_open = issues_df[(issues_df["status"] == "open") & (issues_df["risk_level"] == "high")]
    if high_open.empty:
        st.success("No high-risk open issues.")
    else:
        st.dataframe(
            high_open[["id","date_raised","category","risk_level","target_date","status"]],
            width="stretch", hide_index=True,
        )

else:
    # Executive: count only
    open_count = int((issues_df["status"] == "open").sum())
    high_open  = int(((issues_df["status"] == "open") & (issues_df["risk_level"] == "high")).sum())
    st.metric("Open issues", open_count)
    if high_open:
        st.warning(f"⚠ {high_open} high-risk issue(s) require attention.")

# ── Stakeholder update form (Implementation only) ────────────────────────────
if role == "implementation":
    st.divider()
    st.subheader("Update Stakeholder Access Status")
    with st.form("stakeholder_update_form"):
        raw_stk = fetch_stakeholders("implementation")
        opts    = {r["id"]: r["org_unit"] for _, r in raw_stk.iterrows()}
        sel_id  = st.selectbox("Stakeholder", list(opts.keys()), format_func=lambda x: opts[x])
        new_access  = st.selectbox("Access Status", ["confirmed","pending","to_be_requested"])
        new_window  = st.text_input("Consultation Window (free text)", placeholder="e.g. 2026-06-03")
        new_score   = st.slider("Engagement Score (post-consultation)", 0.0, 10.0, step=0.5, value=0.0)
        save_score  = st.checkbox("Save engagement score")
        if st.form_submit_button("Save"):
            updates = {"access_status": new_access, "consultation_window": new_window}
            if save_score:
                updates["engagement_score"] = new_score
            write_stakeholder_update(sel_id, updates)
            log_action("update_stakeholder", "stakeholder", sel_id)
            st.cache_data.clear()
            st.success("Stakeholder record updated.")
            st.rerun()
