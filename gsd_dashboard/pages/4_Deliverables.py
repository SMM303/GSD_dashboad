"""
Page 4 — Deliverables Tracker

Shows deliverable status grid with days-to-deadline, variance,
payment milestones, and quality gates. Includes a Gantt overview,
module status grid, standards reference table, and status update form.
"""
import streamlit as st

st.set_page_config(page_title="Deliverables - GSD Dashboard", layout="wide")

from datetime import date

import pandas as pd

from auth.setup import require_auth, get_user_role, get_display_name
from auth.audit import log_action
from components.branding import inject_luxury_styles, render_sidebar_branding, status_badge
from components.freshness import render_freshness_badges
from components.charts import build_deliverables_gantt, build_standards_coverage
from data.queries import (
    load_payload, fetch_deliverables, fetch_modules, fetch_standards,
    write_deliverable_update, write_module_status,
)

require_auth()
inject_luxury_styles()

role = get_user_role()
name = get_display_name()
render_sidebar_branding(name, role)

with st.sidebar:
    st.page_link("app.py",                            label="Home")
    st.page_link("pages/1_Timeline.py",               label="Timeline")
    st.page_link("pages/2_Stakeholder_Views.py",      label="Stakeholder Views")
    st.page_link("pages/3_Risk_Heat_Map.py",          label="Risk Heat Map")
    st.page_link("pages/4_Deliverables.py",           label="Deliverables")
    st.page_link("pages/5_KPI_Dashboard.py",          label="KPI Dashboard")
    st.page_link("pages/6_Files.py",                  label="Files")
    if role == "admin":
        st.page_link("pages/7_Admin.py",                  label="Admin")
    render_freshness_badges()

log_action("view_deliverables", "page", "deliverables")

# ── Header ────────────────────────────────────────────────────────────────────
payload = load_payload()
prog    = payload.programme

st.markdown(
    '<div class="prog-title">Deliverables Tracker</div>'
    '<div class="prog-sub">TOR section 6 deliverables, payment milestones, quality gates, and module progress</div>',
    unsafe_allow_html=True,
)
st.divider()

# ── Data ──────────────────────────────────────────────────────────────────────
deliverables_df = fetch_deliverables()
modules_df      = fetch_modules()
standards_df    = fetch_standards()

# ── Summary metrics ───────────────────────────────────────────────────────────
total     = len(deliverables_df)
submitted = int(deliverables_df["status"].isin(["submitted","under_review","approved"]).sum())
approved  = int((deliverables_df["status"] == "approved").sum())
overdue   = int(deliverables_df["is_overdue"].sum())

payment_earned = deliverables_df[
    deliverables_df["status"].isin(["submitted","under_review","approved"])
]["payment_pct"].sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total",             total)
c2.metric("Submitted",         submitted)
c3.metric("Approved",          approved)
c4.metric("Overdue",           overdue, delta_color="inverse")
c5.metric("Payment eligible %", f"{payment_earned:.0f}%")

st.divider()

# ── Deliverable Gantt ──────────────────────────────────────────────────────────
gantt_fig = build_deliverables_gantt(deliverables_df, prog.start_date)
st.plotly_chart(gantt_fig, width="stretch")

# ── Deliverables grid ─────────────────────────────────────────────────────────
st.subheader("Deliverable Detail")

show_cols = {
    "id":               "ID",
    "name":             "Deliverable",
    "due_date":         "TOR Due Date",
    "payment_pct":      "Payment %",
    "status":           "Status",
    "quality_gate":     "Quality Gate",
    "days_to_deadline": "Days Remaining",
    "variance_days":    "Variance (days)",
    "reviewer":         "Reviewer",
}
if role in ("implementation",):
    show_cols["submitted_at"] = "Submitted"
    show_cols["approved_at"]  = "Approved"
    show_cols["description"]  = "Description"

display_df = deliverables_df[[c for c in show_cols if c in deliverables_df.columns]].rename(columns=show_cols)

st.dataframe(
    display_df,
    width="stretch",
    hide_index=True,
    column_config={
        "TOR Due Date":   st.column_config.DateColumn("TOR Due Date"),
        "Submitted":      st.column_config.DateColumn("Submitted"),
        "Approved":       st.column_config.DateColumn("Approved"),
        "Payment %":      st.column_config.NumberColumn("Payment %", format="%.0f%%"),
        "Days Remaining": st.column_config.NumberColumn("Days Remaining"),
        "Variance (days)":st.column_config.NumberColumn("Variance (days)"),
    },
)

# ── Deliverable descriptions ──────────────────────────────────────────────────
with st.expander("Deliverable descriptions from TOR section 6"):
    for _, d in deliverables_df.iterrows():
        badge_html = status_badge(d["status"])
        st.markdown(
            f"**{d['id']} - {d['name']}** &nbsp; {badge_html}  \n{d['description']}",
            unsafe_allow_html=True,
        )
        st.markdown("")

# ── Status update form (Implementation only) ──────────────────────────────────
if role in ("admin", "implementation"):
    st.divider()
    st.subheader("Update Deliverable Status")
    with st.form("deliverable_status_form"):
        opts    = {r["id"]: f"{r['id']} - {r['name']}" for _, r in deliverables_df.iterrows()}
        sel_id  = st.selectbox("Deliverable", list(opts.keys()), format_func=lambda x: opts[x])
        sel_row = deliverables_df[deliverables_df["id"] == sel_id].iloc[0]

        col_a, col_b = st.columns(2)
        with col_a:
            new_status = st.selectbox(
                "New Status",
                ["not_started","in_progress","submitted","under_review","approved","rejected"],
                index=["not_started","in_progress","submitted","under_review","approved","rejected"].index(sel_row["status"]),
            )
        with col_b:
            new_gate = st.selectbox(
                "Quality Gate",
                ["draft","internal_review","iom_review","approved"],
                index=["draft","internal_review","iom_review","approved"].index(sel_row["quality_gate"]),
            )

        submitted_on = None
        if new_status == "submitted":
            submitted_on = st.date_input("Submission Date", value=date.today(), min_value=prog.start_date)

        if st.form_submit_button("Save"):
            updates = {"status": new_status, "quality_gate": new_gate}
            if submitted_on:
                updates["submitted_at"] = submitted_on.isoformat()
            write_deliverable_update(sel_id, updates, st.session_state.get("username",""))
            log_action("update_deliverable_status", "deliverable", sel_id)
            st.success(f"Deliverable {sel_id} updated to '{new_status}'.")
            st.rerun()

st.divider()

# ── Curriculum Module Grid ────────────────────────────────────────────────────
st.subheader("Curriculum Module Progress")
st.caption("10 modules, Phase 2, Curriculum Design, Weeks 5 to 8, Deliverable D3")

finalized = int((modules_df["status"] == "finalized").sum())
aligned   = int((modules_df["status"].isin(["standards_aligned","finalized"])).sum())

mc1, mc2, mc3 = st.columns(3)
mc1.metric("Finalized",         finalized)
mc2.metric("Standards aligned", aligned)
mc3.metric("Completion %",      f"{finalized / len(modules_df) * 100:.0f}%")
st.progress(finalized / len(modules_df) if len(modules_df) else 0)

# Module status chart
cov_fig = build_standards_coverage(modules_df)
st.plotly_chart(cov_fig, width="stretch")

# Module detail table
st.dataframe(
    modules_df[["id","title","status","standards_count","applicable_deliverable"]].rename(columns={
        "id":                     "Module",
        "title":                  "Title",
        "status":                 "Status",
        "standards_count":        "Standards Mapped",
        "applicable_deliverable": "Deliverable",
    }),
    width="stretch", hide_index=True,
)

# ── Module status update (Implementation only) ───────────────────────────────
if role in ("admin", "implementation"):
    st.subheader("Update Module Status")
    with st.form("module_status_form"):
        mod_opts = {r["id"]: f"{r['id']} - {r['title']}" for _, r in modules_df.iterrows()}
        sel_mod  = st.selectbox("Module", list(mod_opts.keys()), format_func=lambda x: mod_opts[x])
        sel_mod_row = modules_df[modules_df["id"] == sel_mod].iloc[0]
        status_opts = ["not_started","outline_complete","draft_complete","standards_aligned","finalized"]
        new_mod_status = st.selectbox(
            "New Status", status_opts,
            index=status_opts.index(sel_mod_row["status"]),
        )
        if st.form_submit_button("Save Module Status"):
            write_module_status(sel_mod, new_mod_status)
            log_action("update_module_status", "module", sel_mod)
            st.success(f"Module {sel_mod} updated to '{new_mod_status}'.")
            st.rerun()

# ── Standards Reference Table (Oversight + Implementation) ────────────────────
if role in ("implementation", "oversight"):
    st.divider()
    st.subheader("Standards Reference Table")
    st.caption("12 reference sources mapped to curriculum modules (Day 2 desk review)")

    sel_std_mod = st.selectbox(
        "Filter by module",
        ["All"] + [f"M{str(i).zfill(2)}" for i in range(1, 11)],
        key="std_mod_filter",
    )
    std_display = standards_df.copy()
    if sel_std_mod != "All":
        std_display = std_display[std_display["modules"].str.contains(sel_std_mod)]

    st.dataframe(
        std_display[["id","source","standard","modules","status"]].rename(columns={
            "id":       "Ref",
            "source":   "Source Document",
            "standard": "Standard and Principle",
            "modules":  "Applicable Modules",
            "status":   "Mapping Status",
        }),
        width="stretch", hide_index=True,
    )

# ── CSV export ─────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Export")
col_e1, col_e2 = st.columns(2)
with col_e1:
    csv_del = deliverables_df.to_csv(index=False).encode()
    st.download_button("Download Deliverables CSV", csv_del, "deliverables.csv", "text/csv")
with col_e2:
    csv_mod = modules_df.to_csv(index=False).encode()
    st.download_button("Download Modules CSV", csv_mod, "modules.csv", "text/csv")
