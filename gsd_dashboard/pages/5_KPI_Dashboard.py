"""
Page 5 — KPI Dashboard

Five KPI tiles (luxury dark-blue metric cards) with sparklines.
Derived directly from the three TOR §7 performance indicators plus
two operational KPIs from the action plan.
Includes a manual KPI override form for the IBG PM.
Audit logged on every view.
"""
import streamlit as st

st.set_page_config(page_title="KPI Dashboard - GSD Dashboard", layout="wide")

import pandas as pd

from auth.setup import require_auth, get_user_role, get_display_name
from auth.audit import log_action
from components.branding import inject_luxury_styles, render_sidebar_branding
from components.freshness import render_freshness_badges
from components.charts import build_sparkline
from utils.errors import get_logger

_log = get_logger(__name__)
from data.queries import (
    fetch_kpis, fetch_deliverables, fetch_stakeholders,
    fetch_modules, fetch_issues,
    load_payload,
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

log_action("view_kpi_dashboard", "page", "kpi_dashboard")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="prog-title">KPI Dashboard</div>'
    '<div class="prog-sub">TOR section 7 performance indicators, live calculations, and trend sparklines</div>',
    unsafe_allow_html=True,
)
st.divider()

# ── Live KPI recalculation ────────────────────────────────────────────────────
# We recalculate from live data rather than relying solely on stored kpi_snapshots.

payload          = load_payload()
deliverables_df  = fetch_deliverables()
stakeholders_df  = fetch_stakeholders(role)
modules_df       = fetch_modules()
issues_df        = fetch_issues()
kpis_df          = fetch_kpis()

TOTAL_CATEGORIES = 7

# KPI001 — Stakeholder Engagement
confirmed_cats = 0
if "actor_category" in stakeholders_df.columns and "access_status" in stakeholders_df.columns:
    confirmed_cats = stakeholders_df[
        stakeholders_df["access_status"] == "confirmed"
    ]["actor_category"].nunique()
kpi001_value = round(confirmed_cats / TOTAL_CATEGORIES * 100, 1)

# KPI002 — Delivery Timeliness (mean variance of submitted deliverables)
submitted_del = deliverables_df[deliverables_df["variance_days"].notna()]
if not submitted_del.empty:
    kpi002_value = round(float(submitted_del["variance_days"].mean()), 1)
    kpi002_label = f"{kpi002_value:+.1f} days avg"
else:
    kpi002_value = None
    kpi002_label = "No submissions yet"

# KPI003 — Standards Coverage
aligned_count = int(modules_df["status"].isin(["standards_aligned","finalized"]).sum())
kpi003_value  = round(aligned_count / len(modules_df) * 100, 1)

# KPI004 — Open Issues
kpi004_value = int((issues_df["status"] == "open").sum()) if not issues_df.empty else 0

# KPI005 — Curriculum Completion
finalized_count = int((modules_df["status"] == "finalized").sum())
kpi005_value    = round(finalized_count / len(modules_df) * 100, 1)

live_values = {
    "KPI001": kpi001_value,
    "KPI002": kpi002_value,
    "KPI003": kpi003_value,
    "KPI004": kpi004_value,
    "KPI005": kpi005_value,
}

# ── KPI tiles row ─────────────────────────────────────────────────────────────
kpi_meta = [
    {
        "id":         "KPI001",
        "name":       "Stakeholder Engagement",
        "value":      kpi001_value,
        "unit":       "percent",
        "target":     100.0,
        "label":      f"{kpi001_value:.1f}%",
        "help":       "TOR §7: Effective coordination with IOM, GSD, and relevant stakeholders. "
                      f"{confirmed_cats} of {TOTAL_CATEGORIES} actor categories have at least one confirmed consultation.",
        "delta_invert": False,
    },
    {
        "id":         "KPI002",
        "name":       "Delivery Timeliness",
        "value":      kpi002_value,
        "unit":       "days",
        "target":     0,
        "label":      kpi002_label,
        "help":       "TOR §7: Timely submission of all deliverables per approved workplan. "
                      "Average days variance across submitted deliverables. Negative = early.",
        "delta_invert": True,
    },
    {
        "id":         "KPI003",
        "name":       "Standards Coverage",
        "value":      kpi003_value,
        "unit":       "percent",
        "target":     100.0,
        "label":      f"{kpi003_value:.1f}%",
        "help":       "TOR §7: High-quality materials aligned with IOM IBG framework. "
                      f"{aligned_count} of 10 modules at standards aligned or finalized status.",
        "delta_invert": False,
    },
    {
        "id":         "KPI004",
        "name":       "Open Issues",
        "value":      kpi004_value,
        "unit":       "count",
        "target":     0,
        "label":      str(kpi004_value),
        "help":       "Issue log count of issues with status set to open. Target is zero open issues.",
        "delta_invert": True,
    },
    {
        "id":         "KPI005",
        "name":       "Curriculum Completion",
        "value":      kpi005_value,
        "unit":       "percent",
        "target":     100.0,
        "label":      f"{kpi005_value:.1f}%",
        "help":       f"{finalized_count} of 10 modules at finalized status.",
        "delta_invert": False,
    },
]

cols = st.columns(len(kpi_meta))
for col, kpi in zip(cols, kpi_meta):
    # Retrieve stored trend from kpis_df for delta calculation
    stored = kpis_df[kpis_df["id"] == kpi["id"]]
    delta  = None
    if not stored.empty and stored.iloc[0]["trend_delta"] is not None:
        delta = float(stored.iloc[0]["trend_delta"])

    with col:
        col.metric(
            label=kpi["name"],
            value=kpi["label"],
            delta=f"{delta:+.1f}" if delta is not None else None,
            delta_color="inverse" if kpi["delta_invert"] else "normal",
            help=kpi["help"],
        )

st.divider()

# ── Sparklines ────────────────────────────────────────────────────────────────
st.subheader("Trend History")
spark_cols = st.columns(len(kpi_meta))

for col, kpi in zip(spark_cols, kpi_meta):
    stored = kpis_df[kpis_df["id"] == kpi["id"]]
    trend  = []
    if not stored.empty:
        raw_trend = stored.iloc[0]["trend"]
        if isinstance(raw_trend, list):
            trend = raw_trend

    with col:
        st.caption(kpi["name"])
        fig = build_sparkline(trend, kpi["unit"], kpi["target"])
        st.plotly_chart(fig, width="stretch", key=f"spark_{kpi['id']}")

st.divider()

# ── TOR Performance Indicator detail ──────────────────────────────────────────
st.subheader("TOR Section 7 Performance Indicators")

pi_data = [
    {
        "Indicator": "Stakeholder Engagement Effectiveness",
        "TOR Text":  "Effective coordination and engagement with IOM, GSD, and relevant national and international stakeholders throughout the curriculum development process.",
        "Measure":   "% of defined actor categories with at least 1 confirmed consultation",
        "Current":   f"{kpi001_value:.1f}%",
        "Target":    "100%",
    },
    {
        "Indicator": "Delivery Timeliness",
        "TOR Text":  "Timely submission of all deliverables in accordance with the approved workplan, scope, and agreed methodological standards.",
        "Measure":   "Days variance per deliverable (submitted_at − due_date)",
        "Current":   kpi002_label,
        "Target":    "0 days (no late deliverables)",
    },
    {
        "Indicator": "Materials Quality",
        "TOR Text":  "Production of high-quality, comprehensive, and context-appropriate training materials fully aligned with IOM IBG framework and international best practices.",
        "Measure":   "% of 10 modules at standards_aligned or finalized status",
        "Current":   f"{kpi003_value:.1f}%",
        "Target":    "100%",
    },
]

for pi in pi_data:
    with st.expander(pi["Indicator"]):
        st.markdown(f"**TOR language:** *{pi['TOR Text']}*")
        st.markdown(f"**Measurement approach:** {pi['Measure']}")
        st.markdown(f"**Current:** {pi['Current']}, **Target:** {pi['Target']}")

# ── Deliverable timeliness detail ─────────────────────────────────────────────
if role in ("implementation", "oversight", "executive"):
    st.divider()
    st.subheader("Deliverable Timeliness Detail")

    timeline_data = []
    for _, d in deliverables_df.iterrows():
        variance = d["variance_days"]
        timeline_data.append({
            "Deliverable": f"{d['id']} - {d['name']}",
            "Due Date":    d["due_date"],
            "Status":      d["status"],
            "Days Remaining": d["days_to_deadline"],
            "Variance (days)": variance if pd.notna(variance) else "Not available",
            "Payment %":   f"{d['payment_pct']:.0f}%",
        })

    st.dataframe(
        pd.DataFrame(timeline_data),
        width="stretch", hide_index=True,
        column_config={
            "Due Date":       st.column_config.DateColumn("Due Date"),
            "Days Remaining": st.column_config.NumberColumn("Days Remaining"),
        },
    )

# ── Audit log viewer (IBG PM / Implementation only) ──────────────────────────
if role in ("admin", "implementation") and st.sidebar.checkbox("Show audit log", value=False):
    st.divider()
    st.subheader("Audit Log")
    try:
        from data.demo_store import get_audit_log
        audit = get_audit_log()
        if audit:
            st.dataframe(
                pd.DataFrame(audit),
                width="stretch", hide_index=True,
            )
        else:
            st.info("No audit entries yet.")
    except Exception as e:
        _log.error("Could not load audit log: %s", e, exc_info=True)
        st.warning("Audit log is temporarily unavailable.")
