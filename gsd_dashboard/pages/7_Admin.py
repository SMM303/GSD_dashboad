"""
Page 7 - Admin

Admin-only account management: create users, assign roles, activate/deactivate
accounts, and reset passwords.
"""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Admin - GSD Dashboard", layout="wide")

from auth.accounts import ACCOUNT_ROLES, ROLE_LABELS, create_account, list_accounts, reset_password, update_account
from auth.audit import log_action
from auth.fly_secrets import fly_available
from auth.setup import get_display_name, get_user_role, get_username, require_auth
from components.branding import inject_luxury_styles, render_sidebar_branding
from components.freshness import render_freshness_badges
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
    st.error("Admin access is required for account management.")
    st.stop()

log_action("view_account_admin", "page", "admin")

st.markdown(
    '<div class="prog-title">Account Administration</div>'
    '<div class="prog-sub">Create accounts, assign roles, reset passwords, and disable access</div>',
    unsafe_allow_html=True,
)

# ── Credential-sync status banner ──────────────────────────────────────────
_fly_sync = fly_available()
if _fly_sync:
    st.success(
        "✅ **Fly.io credential sync enabled.** "
        "Accounts you create or modify are automatically backed up to the "
        "`AUTH_CREDENTIALS_JSON` Fly.io secret. The app can log users in from "
        "that backup if Supabase is unreachable.",
        icon=None,
    )
else:
    st.info(
        "ℹ️ **Fly.io credential sync is not configured.** "
        "Accounts are stored in Supabase only. "
        "To enable the Fly.io backup, add `FLY_API_TOKEN` and `FLY_APP_NAME` "
        "to your Fly.io secrets (`flyctl secrets set …`).",
        icon=None,
    )

st.divider()

accounts = list_accounts()

if accounts:
    table = pd.DataFrame(accounts)
    table["role"] = table["role"].map(lambda value: ROLE_LABELS.get(value, value.title()))
    table["active"] = table["active"].map(lambda value: "Active" if value else "Disabled")
    st.dataframe(
        table.rename(columns={
            "username": "Username",
            "display_name": "Name",
            "role": "Role",
            "active": "Status",
            "created_by": "Created By",
            "created_at": "Created",
            "updated_at": "Updated",
        }),
        hide_index=True,
        width="stretch",
    )
else:
    st.info("No managed accounts found yet. Use the form below to create the first account.")

st.divider()

create_col, manage_col = st.columns([1, 1])

with create_col:
    st.subheader("Create Account")
    with st.form("create_account_form"):
        new_username = st.text_input("Username", placeholder="e.g. iom.admin")
        new_name = st.text_input("Display name", placeholder="e.g. IOM Admin")
        new_role = st.selectbox(
            "Role",
            ACCOUNT_ROLES,
            format_func=lambda value: ROLE_LABELS.get(value, value.title()),
            index=1,
        )
        new_password = st.text_input("Temporary password", type="password")
        submitted = st.form_submit_button("Create account", width="stretch")

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
    account_usernames = [account["username"] for account in accounts]
    if not account_usernames:
        st.caption("Create an account first, then it will appear here.")
    else:
        selected = st.selectbox("Account", account_usernames)
        account = next(item for item in accounts if item["username"] == selected)

        with st.form("update_account_form"):
            display_name = st.text_input("Display name", value=account.get("display_name") or selected)
            selected_role = st.selectbox(
                "Role",
                ACCOUNT_ROLES,
                index=ACCOUNT_ROLES.index(account.get("role", "executive")),
                format_func=lambda value: ROLE_LABELS.get(value, value.title()),
            )
            active = st.checkbox("Account active", value=bool(account.get("active", True)))
            save = st.form_submit_button("Save account changes", width="stretch")

        if save:
            try:
                update_account(selected, display_name, selected_role, active)
                log_action("update_account", "user", selected)
                st.success("Account updated.")
                st.rerun()
            except Exception as exc:
                ui_error(exc, context="update_account", logger=_log)

        with st.form("reset_password_form"):
            replacement_password = st.text_input("New temporary password", type="password")
            reset = st.form_submit_button("Reset password", width="stretch")

        if reset:
            try:
                reset_password(selected, replacement_password)
                log_action("reset_account_password", "user", selected)
                st.success("Password reset.")
            except Exception as exc:
                ui_error(exc, context="reset_password", logger=_log)
