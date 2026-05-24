"""
Page 3 — Risk Heat Map

Plotly scatter on a 5×5 likelihood × impact grid.
Colour = risk category. Symbol = risk status.
Dotted lines show historical position trajectories.
Tooltips include full mitigation text and escalation triggers.
Risk update form available to Implementation role.
Audit logged on every view and every update.
"""
import streamlit as st

st.set_page_config(page_title="Risk Heat Map · GSD Dashboard", layout="wide")

from auth.setup import require_auth, get_user_role, get_display_name
from auth.audit import log_action
from components.branding import inject_luxury_styles, render_sidebar_branding, status_badge
from components.freshness import render_freshness_badges
from components.charts import build_risk_heatmap, RISK_CAT_COLOURS
from data.queries import fetch_risks, write_risk_update

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

log_action("view_risk_register", "page", "risk_heatmap")

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="prog-title">Risk Register</div>'
    '<div class="prog-sub">Likelihood × Impact heat map · Category colour · Status symbol · Mitigation detail</div>',
    unsafe_allow_html=True,
)
st.divider()

# ── Data ─────────────────────────────────────────────────────────────────────
risks_df = fetch_risks()

# ── Summary metrics ──────────────────────────────────────────────────────────
active    = int((risks_df["status"] == "active").sum())
escalated = int((risks_df["status"] == "escalated").sum())
mitigated = int((risks_df["status"] == "mitigated").sum())
high_score = int((risks_df["risk_score"] >= 12).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Risks",    active)
c2.metric("Escalated",       escalated, delta_color="inverse")
c3.metric("Mitigated",       mitigated)
c4.metric("Score ≥ 12",      high_score, delta_color="inverse")

# ── Heat Map ──────────────────────────────────────────────────────────────────
col_chart, col_legend = st.columns([3, 1])

with col_chart:
    fig = build_risk_heatmap(risks_df)
    st.plotly_chart(fig, width="stretch")

with col_legend:
    st.markdown("**Legend — Category**")
    for cat, colour in RISK_CAT_COLOURS.items():
        st.markdown(
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'background:{colour};border-radius:50%;margin-right:6px;"></span>'
            f'{cat.title()}',
            unsafe_allow_html=True,
        )
    st.markdown("---")
    st.markdown("**Legend — Status**")
    for sym, label in [("●","Active"), ("■","Mitigated"), ("✕","Escalated"), ("◆","Closed")]:
        st.markdown(f"{sym} {label}")
    st.markdown("---")
    st.markdown("**Zone colours**")
    st.markdown("🟢 Low risk (score ≤ 6)")
    st.markdown("🟡 Medium risk (score 7–11)")
    st.markdown("🔴 High risk (score ≥ 12)")

st.divider()

# ── Risk detail table ─────────────────────────────────────────────────────────
st.subheader("Risk Detail")

# Executive sees summary only; Implementation and Oversight see full detail
if role == "executive":
    show_cols = ["id","description","category","likelihood","impact","risk_score","status"]
else:
    show_cols = ["id","description","category","likelihood","impact","risk_score",
                 "status","mitigation","escalation_trigger","owner","raised_date"]

# Filter by status
sel_status = st.selectbox("Filter by status", ["All","active","mitigated","escalated","closed"])
display    = risks_df if sel_status == "All" else risks_df[risks_df["status"] == sel_status]

st.dataframe(
    display[show_cols],
    width="stretch",
    hide_index=True,
    column_config={
        "id":           "Risk ID",
        "description":  "Description",
        "category":     "Category",
        "likelihood":   st.column_config.NumberColumn("Likelihood (1-5)"),
        "impact":       st.column_config.NumberColumn("Impact (1-5)"),
        "risk_score":   st.column_config.NumberColumn("Score"),
        "raised_date":  st.column_config.DateColumn("Raised"),
    },
)

# ── Escalation alerts ─────────────────────────────────────────────────────────
escalated_risks = risks_df[risks_df["status"] == "escalated"]
if not escalated_risks.empty:
    st.error(f"⚠ {len(escalated_risks)} escalated risk(s). Immediate attention required.")
    for _, r in escalated_risks.iterrows():
        with st.expander(f"{r['id']} — {r['description']}"):
            st.markdown(f"**Escalation trigger:** {r['escalation_trigger']}")
            st.markdown(f"**Mitigation:** {r['mitigation']}")
            st.markdown(f"**Owner:** {r['owner']}")

# ── Risk update form (Implementation only) ────────────────────────────────────
if role == "implementation":
    st.divider()
    st.subheader("Update Risk Position")
    st.caption(
        "Updating likelihood or impact saves the new position to history "
        "and redraws the trajectory on the heat map."
    )

    with st.form("risk_update_form"):
        opts    = {r["id"]: f"{r['id']} — {str(r['description'])[:55]}" for _, r in risks_df.iterrows()}
        sel_id  = st.selectbox("Risk", list(opts.keys()), format_func=lambda x: opts[x])

        sel_row = risks_df[risks_df["id"] == sel_id].iloc[0]

        col_a, col_b = st.columns(2)
        with col_a:
            likelihood_labels = {1:"1 – Rare", 2:"2 – Unlikely", 3:"3 – Possible", 4:"4 – Likely", 5:"5 – Almost Certain"}
            new_l = st.select_slider(
                "Likelihood", options=[1,2,3,4,5],
                value=int(sel_row["likelihood"]),
                format_func=lambda x: likelihood_labels[x],
            )
        with col_b:
            impact_labels = {1:"1 – Negligible", 2:"2 – Minor", 3:"3 – Moderate", 4:"4 – Significant", 5:"5 – Critical"}
            new_i = st.select_slider(
                "Impact", options=[1,2,3,4,5],
                value=int(sel_row["impact"]),
                format_func=lambda x: impact_labels[x],
            )

        new_status = st.selectbox(
            "Status", ["active","mitigated","escalated","closed"],
            index=["active","mitigated","escalated","closed"].index(sel_row["status"]),
        )
        new_score = new_l * new_i
        st.markdown(f"**New risk score: {new_score}** (likelihood {new_l} × impact {new_i})")

        if st.form_submit_button("Save Risk Update"):
            write_risk_update(
                sel_id, new_l, new_i, new_status,
                st.session_state.get("username","unknown"),
            )
            log_action("update_risk", "risk", sel_id)
            st.cache_data.clear()
            st.success(f"Risk {sel_id} updated. New score: {new_score}.")
            st.rerun()

# ── Risk history (Implementation and Oversight) ───────────────────────────────
if role in ("implementation", "oversight"):
    st.divider()
    st.subheader("Risk Position History")
    sel_hist = st.selectbox("Select risk to view history", risks_df["id"].tolist(), key="hist_sel")
    row = risks_df[risks_df["id"] == sel_hist].iloc[0]
    history = row.get("history", [])
    if isinstance(history, list) and history:
        import pandas as pd
        hist_df = pd.DataFrame(history)
        hist_df["score"] = hist_df["likelihood"] * hist_df["impact"]
        st.dataframe(
            hist_df,
            width="stretch", hide_index=True,
            column_config={
                "date":       st.column_config.DateColumn("Date"),
                "likelihood": st.column_config.NumberColumn("Likelihood"),
                "impact":     st.column_config.NumberColumn("Impact"),
                "score":      st.column_config.NumberColumn("Score"),
                "status":     "Status",
            },
        )
    else:
        st.info("No history recorded yet for this risk.")
