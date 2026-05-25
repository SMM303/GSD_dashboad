"""
Page 7 — Admin

Five tabs:
  Accounts     — create / update / disable user accounts
  Risks        — add new risks, edit definitions (not scores), soft-close
  Deliverables — add new deliverables, edit definitions (not workflow status)
  Stakeholders — full CRUD with hard-delete guard
  Audit Log    — read-only, searchable, no mutations
"""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Admin - GSD Dashboard", layout="wide")

from datetime import date

from auth.accounts import ACCOUNT_ROLES, ROLE_LABELS, create_account, list_accounts, reset_password, update_account
from auth.audit import log_action
from auth.fly_secrets import fly_available
from auth.setup import get_display_name, get_user_role, get_username, require_auth
from components.branding import (
    inject_luxury_styles, render_sidebar_branding,
    STATUS_LABELS, QUALITY_GATE_LABELS, RISK_LEVEL_LABELS,
    ACCESS_STATUS_LABELS, ISSUE_CATEGORY_LABELS,
)
from components.freshness import render_freshness_badges
from data.queries import (
    _is_demo,
    fetch_deliverables, fetch_risks, fetch_stakeholders, fetch_audit_log_admin,
    write_new_risk, write_risk_definition, write_risk_close,
    write_new_deliverable, write_deliverable_definition, write_deliverable_delete,
    write_new_stakeholder, write_stakeholder_definition, write_stakeholder_delete,
)
from utils.errors import get_logger, ui_error

_log = get_logger(__name__)

require_auth()
inject_luxury_styles()

role = get_user_role()
name = get_display_name()
username = get_username()
render_sidebar_branding(name, role)

with st.sidebar:
    st.page_link("app.py", label="Home")
    st.page_link("pages/1_Timeline.py", label="Timeline")
    st.page_link("pages/2_Stakeholder_Views.py", label="Stakeholder Views")
    st.page_link("pages/3_Risk_Heat_Map.py", label="Risk Heat Map")
    st.page_link("pages/4_Deliverables.py", label="Deliverables")
    st.page_link("pages/5_KPI_Dashboard.py", label="KPI Dashboard")
    st.page_link("pages/6_Files.py", label="Files")
    if role == "admin":
        st.page_link("pages/7_Admin.py", label="Admin")
    render_freshness_badges()

if role != "admin":
    st.error("Admin access is required for this page.")
    st.stop()

log_action("view_account_admin", "page", "admin")

st.markdown(
    '<div class="prog-title">Administration</div>'
    '<div class="prog-sub">Manage accounts, programme data, and review the audit trail</div>',
    unsafe_allow_html=True,
)
if not fly_available():
    st.caption("ℹ Account backup is not enabled. Accounts are stored in the primary database only.")
st.divider()

# ── Enum value lists (from Pydantic models) ──────────────────────────────────
_ACTOR_CATEGORIES  = ["GSD_leadership", "GSD_academy", "GSD_operational",
                       "GSD_legal_it", "IOM", "national_partner", "international_partner"]
_ACTOR_CAT_LABELS  = {v: v.replace("_", " ").replace("GSD", "GSD").title() for v in _ACTOR_CATEGORIES}
_STK_ROLES         = ["informant", "reviewer", "approver", "end_user"]
_STK_ROLE_LABELS   = {v: v.replace("_", " ").title() for v in _STK_ROLES}
_CONSULT_METHODS   = ["interview", "focus_group", "document_review", "workshop"]
_METHOD_LABELS     = {v: v.replace("_", " ").title() for v in _CONSULT_METHODS}
_RISK_CATEGORIES   = ["access", "coordination", "scope", "delivery"]
_RISK_CAT_LABELS   = {v: v.title() for v in _RISK_CATEGORIES}
_ACCESS_STATUSES   = ["confirmed", "pending", "to_be_requested"]
_RISK_STATUSES     = ["active", "mitigated", "escalated", "closed"]


def _demo_notice():
    st.info(
        "Data management requires a Supabase connection. "
        "Set **DEMO_MODE = false** and configure Supabase credentials to enable."
    )


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_accounts, tab_risks, tab_deliverables, tab_stakeholders, tab_audit = st.tabs([
    "Accounts",
    "Risks",
    "Deliverables",
    "Stakeholders",
    "Audit Log",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Accounts
# ═══════════════════════════════════════════════════════════════════════════════
with tab_accounts:
    accounts = list_accounts()

    if accounts:
        table = pd.DataFrame(accounts)
        table["role"]   = table["role"].map(lambda v: ROLE_LABELS.get(v, v.replace("_", " ").title()))
        table["active"] = table["active"].map(lambda v: "Active" if v else "Disabled")
        for col in ("created_at", "updated_at"):
            if col in table.columns:
                table[col] = pd.to_datetime(table[col], utc=True, errors="coerce").dt.strftime("%-d %b %Y, %H:%M")
        st.dataframe(
            table.rename(columns={
                "username":     "Username",
                "display_name": "Name",
                "role":         "Role",
                "active":       "Status",
                "created_by":   "Created By",
                "created_at":   "Created",
                "updated_at":   "Last Updated",
            }),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No accounts yet. Use the form below to create the first account.")

    st.divider()
    create_col, manage_col = st.columns(2)

    with create_col:
        st.subheader("Create Account")
        with st.form("create_account_form"):
            new_username = st.text_input("Username", placeholder="e.g. iom.admin")
            new_name     = st.text_input("Display name", placeholder="e.g. IOM Admin")
            new_role     = st.selectbox(
                "Role", ACCOUNT_ROLES,
                format_func=lambda v: ROLE_LABELS.get(v, v.title()),
                index=1,
            )
            new_password = st.text_input("Temporary password", type="password")
            submitted    = st.form_submit_button("Create account", width="stretch")

        if submitted:
            try:
                create_account(new_username, new_name, new_password, new_role, username)
                log_action("create_account", "user", new_username.strip().lower())
                st.success("Account created.")
                st.rerun()
            except Exception as exc:
                ui_error(exc, context="create_account", logger=_log)

    with manage_col:
        st.subheader("Manage Existing Account")
        account_usernames = [a["username"] for a in accounts]
        if not account_usernames:
            st.caption("Create an account first.")
        else:
            selected = st.selectbox("Account", account_usernames, key="mgmt_acct_sel")
            account  = next(a for a in accounts if a["username"] == selected)

            with st.form("update_account_form"):
                display_name  = st.text_input("Display name", value=account.get("display_name") or selected)
                selected_role = st.selectbox(
                    "Role", ACCOUNT_ROLES,
                    index=ACCOUNT_ROLES.index(account.get("role", "executive")),
                    format_func=lambda v: ROLE_LABELS.get(v, v.title()),
                )
                active = st.checkbox("Account active", value=bool(account.get("active", True)))
                save   = st.form_submit_button("Save changes", width="stretch")

            if save:
                try:
                    update_account(selected, display_name, selected_role, active)
                    log_action("update_account", "user", selected)
                    st.success("Account updated.")
                    st.rerun()
                except Exception as exc:
                    ui_error(exc, context="update_account", logger=_log)

            with st.form("reset_password_form"):
                replacement = st.text_input("New temporary password", type="password")
                reset = st.form_submit_button("Reset password", width="stretch")

            if reset:
                try:
                    reset_password(selected, replacement)
                    log_action("reset_account_password", "user", selected)
                    st.success("Password reset.")
                except Exception as exc:
                    ui_error(exc, context="reset_password", logger=_log)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Risks
# ═══════════════════════════════════════════════════════════════════════════════
with tab_risks:
    if _is_demo():
        _demo_notice()
        st.stop()

    risks_df = fetch_risks()

    # ── Browse ───────────────────────────────────────────────────────────────
    browse_cols = ["id", "description", "category", "likelihood", "impact", "risk_score", "status", "owner"]
    st.dataframe(
        risks_df[[c for c in browse_cols if c in risks_df.columns]].rename(columns={
            "id":          "ID",
            "description": "Description",
            "category":    "Category",
            "likelihood":  "L",
            "impact":      "I",
            "risk_score":  "Score",
            "status":      "Status",
            "owner":       "Owner",
        }),
        hide_index=True,
        width="stretch",
        column_config={
            "L":     st.column_config.NumberColumn("L", help="Likelihood (1–5)"),
            "I":     st.column_config.NumberColumn("I", help="Impact (1–5)"),
            "Score": st.column_config.NumberColumn("Score"),
        },
    )
    st.divider()

    # ── Add / Edit ────────────────────────────────────────────────────────────
    add_col, edit_col = st.columns(2)

    with add_col:
        st.subheader("Add Risk")
        st.caption("Likelihood and impact can be adjusted later from the Risk page.")
        with st.form("add_risk_form"):
            r_id    = st.text_input("Risk ID", placeholder="e.g. R006")
            r_desc  = st.text_area("Description")
            r_cat   = st.selectbox("Category", _RISK_CATEGORIES,
                                   format_func=lambda x: _RISK_CAT_LABELS.get(x, x.title()))
            r_like  = st.select_slider("Likelihood", options=[1, 2, 3, 4, 5], value=3,
                                       format_func=lambda x: f"{x} — " + ["Rare","Unlikely","Possible","Likely","Almost Certain"][x-1])
            r_imp   = st.select_slider("Impact", options=[1, 2, 3, 4, 5], value=3,
                                       format_func=lambda x: f"{x} — " + ["Negligible","Minor","Moderate","Significant","Critical"][x-1])
            r_mit   = st.text_area("Mitigation")
            r_esc   = st.text_area("Escalation trigger")
            r_owner = st.text_input("Owner")
            r_date  = st.date_input("Raised date", value=date.today())
            add_r   = st.form_submit_button("Add risk", width="stretch")

        if add_r:
            if not r_id.strip() or not r_desc.strip():
                st.error("Risk ID and description are required.")
            else:
                try:
                    write_new_risk({
                        "id": r_id.strip(), "description": r_desc.strip(),
                        "category": r_cat, "likelihood": r_like, "impact": r_imp,
                        "mitigation": r_mit.strip(), "escalation_trigger": r_esc.strip(),
                        "owner": r_owner.strip(), "status": "active",
                        "raised_date": r_date.isoformat(),
                    })
                    log_action("admin_add_risk", "risk", r_id.strip())
                    st.success(f"Risk {r_id.strip()} added.")
                    st.rerun()
                except Exception as exc:
                    ui_error(exc, context="admin_add_risk", logger=_log)

    with edit_col:
        st.subheader("Edit Risk Definition")
        st.caption("To update scores or status, use the Risk page. Only description and ownership are editable here.")
        risk_opts = {r["id"]: f"{r['id']} — {str(r['description'])[:50]}" for _, r in risks_df.iterrows()}
        sel_risk  = st.selectbox("Risk", list(risk_opts.keys()),
                                 format_func=lambda x: risk_opts[x], key="edit_risk_sel")
        sel_risk_row = risks_df[risks_df["id"] == sel_risk].iloc[0]

        with st.form("edit_risk_form"):
            er_desc  = st.text_area("Description",         value=sel_risk_row["description"])
            er_cat   = st.selectbox("Category", _RISK_CATEGORIES,
                                    index=_RISK_CATEGORIES.index(sel_risk_row["category"]),
                                    format_func=lambda x: _RISK_CAT_LABELS.get(x, x.title()))
            er_mit   = st.text_area("Mitigation",          value=str(sel_risk_row.get("mitigation") or ""))
            er_esc   = st.text_area("Escalation trigger",  value=str(sel_risk_row.get("escalation_trigger") or ""))
            er_owner = st.text_input("Owner",              value=str(sel_risk_row.get("owner") or ""))
            save_r   = st.form_submit_button("Save changes", width="stretch")

        if save_r:
            try:
                write_risk_definition(sel_risk, {
                    "description": er_desc.strip(), "category": er_cat,
                    "mitigation": er_mit.strip(), "escalation_trigger": er_esc.strip(),
                    "owner": er_owner.strip(),
                })
                log_action("admin_edit_risk", "risk", sel_risk)
                st.success("Risk updated.")
                st.rerun()
            except Exception as exc:
                ui_error(exc, context="admin_edit_risk", logger=_log)

    # ── Soft-close ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Close Risk")
    st.caption("Risks are never hard-deleted — closing them marks status as Closed and removes them from the active register.")
    open_risks = risks_df[risks_df["status"] != "closed"]
    if open_risks.empty:
        st.info("No open risks.")
    else:
        close_opts  = {r["id"]: f"{r['id']} — {str(r['description'])[:55]}" for _, r in open_risks.iterrows()}
        sel_close   = st.selectbox("Risk to close", list(close_opts.keys()),
                                   format_func=lambda x: close_opts[x], key="close_risk_sel")
        if st.button("Close risk", key="close_risk_btn"):
            try:
                write_risk_close(sel_close)
                log_action("admin_close_risk", "risk", sel_close)
                st.success(f"Risk {sel_close} closed.")
                st.rerun()
            except Exception as exc:
                ui_error(exc, context="admin_close_risk", logger=_log)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Deliverables
# ═══════════════════════════════════════════════════════════════════════════════
with tab_deliverables:
    if _is_demo():
        _demo_notice()
        st.stop()

    del_df = fetch_deliverables()

    # ── Browse ───────────────────────────────────────────────────────────────
    browse_del_cols = ["id", "name", "phase_id", "due_date", "payment_pct", "status", "reviewer"]
    st.dataframe(
        del_df[[c for c in browse_del_cols if c in del_df.columns]].rename(columns={
            "id":          "ID",
            "name":        "Name",
            "phase_id":    "Phase",
            "due_date":    "Due Date",
            "payment_pct": "Payment %",
            "status":      "Status",
            "reviewer":    "Reviewer",
        }),
        hide_index=True,
        width="stretch",
        column_config={
            "Due Date":   st.column_config.DateColumn("Due Date"),
            "Payment %":  st.column_config.NumberColumn("Payment %", format="%.0f%%"),
        },
    )
    st.divider()

    # ── Add / Edit ────────────────────────────────────────────────────────────
    add_col, edit_col = st.columns(2)

    with add_col:
        st.subheader("Add Deliverable")
        with st.form("add_del_form"):
            d_id      = st.text_input("Deliverable ID", placeholder="e.g. D6")
            d_name    = st.text_input("Name")
            d_desc    = st.text_area("Description")
            d_phase   = st.text_input("Phase ID", placeholder="e.g. P1")
            d_week    = st.number_input("Due week", min_value=1, max_value=52, value=8)
            d_due     = st.date_input("Due date", value=date.today())
            d_pct     = st.number_input("Payment %", min_value=0.0, max_value=100.0, value=0.0, step=5.0)
            d_rev     = st.text_input("Reviewer")
            add_d     = st.form_submit_button("Add deliverable", width="stretch")

        if add_d:
            if not d_id.strip() or not d_name.strip():
                st.error("ID and name are required.")
            else:
                try:
                    write_new_deliverable({
                        "id": d_id.strip(), "name": d_name.strip(),
                        "description": d_desc.strip(), "phase_id": d_phase.strip(),
                        "due_week": int(d_week), "due_date": d_due.isoformat(),
                        "payment_pct": float(d_pct), "reviewer": d_rev.strip(),
                        "status": "not_started", "quality_gate": "draft",
                    })
                    log_action("admin_add_deliverable", "deliverable", d_id.strip())
                    st.success(f"Deliverable {d_id.strip()} added.")
                    st.rerun()
                except Exception as exc:
                    ui_error(exc, context="admin_add_deliverable", logger=_log)

    with edit_col:
        st.subheader("Edit Definition")
        st.caption("Status and quality gate are managed from the Deliverables page. Only definition fields are editable here.")
        del_opts  = {r["id"]: f"{r['id']} — {r['name']}" for _, r in del_df.iterrows()}
        sel_del   = st.selectbox("Deliverable", list(del_opts.keys()),
                                 format_func=lambda x: del_opts[x], key="edit_del_sel")
        sel_del_row = del_df[del_df["id"] == sel_del].iloc[0]

        with st.form("edit_del_form"):
            ed_name = st.text_input("Name",        value=sel_del_row["name"])
            ed_desc = st.text_area("Description",  value=str(sel_del_row.get("description") or ""))
            ed_due  = st.date_input("Due date",    value=pd.to_datetime(sel_del_row["due_date"]).date())
            ed_week = st.number_input("Due week",  value=int(sel_del_row.get("due_week") or 1),
                                      min_value=1, max_value=52)
            ed_pct  = st.number_input("Payment %", value=float(sel_del_row.get("payment_pct") or 0),
                                      min_value=0.0, max_value=100.0, step=5.0)
            ed_rev  = st.text_input("Reviewer",    value=str(sel_del_row.get("reviewer") or ""))
            save_d  = st.form_submit_button("Save changes", width="stretch")

        if save_d:
            try:
                write_deliverable_definition(sel_del, {
                    "name": ed_name.strip(), "description": ed_desc.strip(),
                    "due_date": ed_due.isoformat(), "due_week": int(ed_week),
                    "payment_pct": float(ed_pct), "reviewer": ed_rev.strip(),
                })
                log_action("admin_edit_deliverable", "deliverable", sel_del)
                st.success("Deliverable updated.")
                st.rerun()
            except Exception as exc:
                ui_error(exc, context="admin_edit_deliverable", logger=_log)

    # ── Delete guard ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Delete Deliverable")
    st.caption("Only deliverables with status **Not Started** can be deleted. This cannot be undone.")

    not_started = del_df[del_df["status"] == "not_started"]
    if not_started.empty:
        st.info("No deliverables are in 'Not Started' status.")
    else:
        del_del_opts = {r["id"]: f"{r['id']} — {r['name']}" for _, r in not_started.iterrows()}
        sel_del_del  = st.selectbox("Deliverable to delete", list(del_del_opts.keys()),
                                    format_func=lambda x: del_del_opts[x], key="delete_del_sel")
        confirm_del  = st.text_input(f"Type **{sel_del_del}** to confirm deletion:", key="confirm_del_input")
        if st.button("Delete permanently", key="delete_del_btn",
                     disabled=(confirm_del != sel_del_del)):
            try:
                write_deliverable_delete(sel_del_del)
                log_action("admin_delete_deliverable", "deliverable", sel_del_del)
                st.success(f"Deliverable {sel_del_del} deleted.")
                st.rerun()
            except Exception as exc:
                ui_error(exc, context="admin_delete_deliverable", logger=_log)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Stakeholders
# ═══════════════════════════════════════════════════════════════════════════════
with tab_stakeholders:
    if _is_demo():
        _demo_notice()
        st.stop()

    stk_df = fetch_stakeholders("admin")

    # ── Browse (admin sees all columns including PII) ─────────────────────────
    st.dataframe(
        stk_df.rename(columns={
            "id":                  "ID",
            "org_unit":            "Organisation",
            "contact_name":        "Contact",
            "contact_title":       "Title",
            "actor_category":      "Category",
            "role":                "Role",
            "method":              "Method",
            "access_status":       "Access",
            "consultation_window": "Consultation Window",
            "engagement_score":    "Score",
        }),
        hide_index=True,
        width="stretch",
        column_config={
            "Score": st.column_config.NumberColumn("Score", format="%.1f"),
        },
    )
    st.divider()

    # ── Add / Edit ────────────────────────────────────────────────────────────
    add_col, edit_col = st.columns(2)

    with add_col:
        st.subheader("Add Stakeholder")
        with st.form("add_stk_form"):
            s_id     = st.text_input("ID", placeholder="e.g. S013")
            s_org    = st.text_input("Organisation and unit")
            s_cname  = st.text_input("Contact name")
            s_ctitle = st.text_input("Contact title")
            s_cat    = st.selectbox("Category", _ACTOR_CATEGORIES,
                                    format_func=lambda x: _ACTOR_CAT_LABELS.get(x, x))
            s_role   = st.selectbox("Role", _STK_ROLES,
                                    format_func=lambda x: _STK_ROLE_LABELS.get(x, x))
            s_method = st.selectbox("Consultation method", _CONSULT_METHODS,
                                    format_func=lambda x: _METHOD_LABELS.get(x, x))
            s_access = st.selectbox("Access status", _ACCESS_STATUSES,
                                    format_func=lambda x: ACCESS_STATUS_LABELS.get(x, x))
            s_window = st.text_input("Consultation window", placeholder="e.g. Week 3–4")
            s_score  = st.number_input("Engagement score (0–10)", min_value=0.0, max_value=10.0,
                                       step=0.5, value=0.0)
            add_s    = st.form_submit_button("Add stakeholder", width="stretch")

        if add_s:
            if not s_id.strip() or not s_org.strip():
                st.error("ID and organisation are required.")
            else:
                try:
                    write_new_stakeholder({
                        "id": s_id.strip(), "org_unit": s_org.strip(),
                        "contact_name": s_cname.strip() or None,
                        "contact_title": s_ctitle.strip() or None,
                        "actor_category": s_cat, "role": s_role, "method": s_method,
                        "access_status": s_access,
                        "consultation_window": s_window.strip() or None,
                        "engagement_score": float(s_score) if s_score else None,
                    })
                    log_action("admin_add_stakeholder", "stakeholder", s_id.strip())
                    st.success(f"Stakeholder {s_id.strip()} added.")
                    st.rerun()
                except Exception as exc:
                    ui_error(exc, context="admin_add_stakeholder", logger=_log)

    with edit_col:
        st.subheader("Edit Stakeholder")
        if stk_df.empty:
            st.caption("No stakeholders yet.")
        else:
            stk_opts    = {r["id"]: f"{r['id']} — {r.get('org_unit','')[:45]}" for _, r in stk_df.iterrows()}
            sel_stk     = st.selectbox("Stakeholder", list(stk_opts.keys()),
                                       format_func=lambda x: stk_opts[x], key="edit_stk_sel")
            sel_stk_row = stk_df[stk_df["id"] == sel_stk].iloc[0]

            with st.form("edit_stk_form"):
                es_org    = st.text_input("Organisation",    value=str(sel_stk_row.get("org_unit") or ""))
                es_cname  = st.text_input("Contact name",   value=str(sel_stk_row.get("contact_name") or ""))
                es_ctitle = st.text_input("Contact title",  value=str(sel_stk_row.get("contact_title") or ""))
                es_cat    = st.selectbox("Category", _ACTOR_CATEGORIES,
                                         index=_ACTOR_CATEGORIES.index(sel_stk_row.get("actor_category", _ACTOR_CATEGORIES[0])) if sel_stk_row.get("actor_category") in _ACTOR_CATEGORIES else 0,
                                         format_func=lambda x: _ACTOR_CAT_LABELS.get(x, x))
                es_role   = st.selectbox("Role", _STK_ROLES,
                                         index=_STK_ROLES.index(sel_stk_row.get("role", _STK_ROLES[0])) if sel_stk_row.get("role") in _STK_ROLES else 0,
                                         format_func=lambda x: _STK_ROLE_LABELS.get(x, x))
                es_method = st.selectbox("Consultation method", _CONSULT_METHODS,
                                         index=_CONSULT_METHODS.index(sel_stk_row.get("method", _CONSULT_METHODS[0])) if sel_stk_row.get("method") in _CONSULT_METHODS else 0,
                                         format_func=lambda x: _METHOD_LABELS.get(x, x))
                es_access = st.selectbox("Access status", _ACCESS_STATUSES,
                                         index=_ACCESS_STATUSES.index(sel_stk_row.get("access_status", _ACCESS_STATUSES[2])) if sel_stk_row.get("access_status") in _ACCESS_STATUSES else 2,
                                         format_func=lambda x: ACCESS_STATUS_LABELS.get(x, x))
                es_window = st.text_input("Consultation window", value=str(sel_stk_row.get("consultation_window") or ""))
                es_score  = st.number_input("Engagement score", min_value=0.0, max_value=10.0,
                                            step=0.5, value=float(sel_stk_row.get("engagement_score") or 0.0))
                save_s    = st.form_submit_button("Save changes", width="stretch")

            if save_s:
                try:
                    write_stakeholder_definition(sel_stk, {
                        "org_unit": es_org.strip(), "contact_name": es_cname.strip() or None,
                        "contact_title": es_ctitle.strip() or None,
                        "actor_category": es_cat, "role": es_role, "method": es_method,
                        "access_status": es_access,
                        "consultation_window": es_window.strip() or None,
                        "engagement_score": float(es_score),
                    })
                    log_action("admin_edit_stakeholder", "stakeholder", sel_stk)
                    st.success("Stakeholder updated.")
                    st.rerun()
                except Exception as exc:
                    ui_error(exc, context="admin_edit_stakeholder", logger=_log)

    # ── Hard-delete guard ─────────────────────────────────────────────────────
    if not stk_df.empty:
        st.divider()
        st.subheader("Delete Stakeholder")
        st.caption("This permanently removes the record and cannot be undone.")

        del_stk_opts = {r["id"]: f"{r['id']} — {r.get('org_unit','')[:45]}" for _, r in stk_df.iterrows()}
        sel_del_stk  = st.selectbox("Stakeholder to delete", list(del_stk_opts.keys()),
                                    format_func=lambda x: del_stk_opts[x], key="delete_stk_sel")
        confirm_stk  = st.text_input(f"Type **{sel_del_stk}** to confirm deletion:", key="confirm_stk_input")
        if st.button("Delete permanently", key="delete_stk_btn",
                     disabled=(confirm_stk != sel_del_stk)):
            try:
                write_stakeholder_delete(sel_del_stk)
                log_action("admin_delete_stakeholder", "stakeholder", sel_del_stk)
                st.success(f"Stakeholder {sel_del_stk} deleted.")
                st.rerun()
            except Exception as exc:
                ui_error(exc, context="admin_delete_stakeholder", logger=_log)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Audit Log
# ═══════════════════════════════════════════════════════════════════════════════
with tab_audit:
    st.caption("Read-only record of all user actions. No entries can be edited or deleted.")
    st.divider()

    f1, f2, f3 = st.columns([1, 2, 1])
    with f1:
        af_user   = st.text_input("Filter by username", placeholder="e.g. saleh")
    with f2:
        af_action = st.text_input("Filter by action", placeholder="e.g. update_risk")
    with f3:
        af_limit  = st.selectbox("Rows", [50, 100, 250, 500], index=0)

    audit_df = fetch_audit_log_admin(
        limit=af_limit,
        user_filter=af_user,
        action_filter=af_action,
    )

    if audit_df.empty:
        st.info("No audit entries found.")
    else:
        # Format timestamp column
        if "timestamp" in audit_df.columns:
            audit_df["timestamp"] = pd.to_datetime(
                audit_df["timestamp"], utc=True, errors="coerce"
            ).dt.strftime("%-d %b %Y, %H:%M")

        st.dataframe(
            audit_df.rename(columns={
                "timestamp":   "Time",
                "user":        "User",
                "role":        "Role",
                "action":      "Action",
                "record_type": "Record Type",
                "record_id":   "Record ID",
                "session_id":  "Session",
            }),
            hide_index=True,
            width="stretch",
        )
        st.caption(f"Showing {len(audit_df)} of the most recent {af_limit} matching entries.")
