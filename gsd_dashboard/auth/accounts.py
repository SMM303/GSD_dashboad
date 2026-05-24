"""
Production account store.

Admins manage accounts in Supabase (primary). On every write the module also
syncs to the Fly.io secret AUTH_CREDENTIALS_JSON via fly_secrets so that the
app keeps working if Supabase is temporarily unreachable.

Secret-based credentials (auth_credentials TOML) remain available as a final
bootstrap fallback so the first admin can sign in before any managed accounts
exist.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import bcrypt
import streamlit as st

from auth.fly_secrets import fly_available, remove_fly_user, sync_user, sync_user_fields


ACCOUNT_ROLES = ("admin", "implementation", "executive", "oversight")
ROLE_LABELS = {
    "admin": "Admin",
    "implementation": "Implementation",
    "executive": "Executive",
    "oversight": "Oversight",
}


def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _get_supabase():
    try:
        from supabase import create_client

        url = _secret("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        key = _secret("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def normalize_username(username: str) -> str:
    return username.strip().lower()


def get_account(username: str) -> dict[str, Any] | None:
    client = _get_supabase()
    if not client:
        return None
    try:
        response = (
            client.table("app_users")
            .select("username,display_name,password_hash,role,active")
            .eq("username", normalize_username(username))
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def authenticate_account(username: str, password: str) -> dict[str, str] | None:
    account = get_account(username)
    if not account or not account.get("active", True):
        return None
    if not verify_password(password, account.get("password_hash", "")):
        return None
    return {
        "username": account["username"],
        "name": account.get("display_name") or account["username"],
        "role": account.get("role", "executive"),
    }


def list_accounts() -> list[dict[str, Any]]:
    client = _get_supabase()
    if not client:
        return []
    try:
        return (
            client.table("app_users")
            .select("username,display_name,role,active,created_by,created_at,updated_at")
            .order("username")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def create_account(username: str, display_name: str, password: str, role: str, created_by: str) -> None:
    client = _get_supabase()
    if not client and not fly_available():
        raise RuntimeError(
            "Either Supabase service role credentials or Fly.io credentials "
            "(FLY_API_TOKEN + FLY_APP_NAME) are required to manage accounts."
        )

    username = normalize_username(username)
    if not username:
        raise ValueError("Username is required.")
    if role not in ACCOUNT_ROLES:
        raise ValueError("Role is not valid.")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")

    display = display_name.strip() or username
    pw_hash = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    # --- Primary store: Supabase ---
    if client:
        client.table("app_users").insert({
            "username": username,
            "display_name": display,
            "password_hash": pw_hash,
            "role": role,
            "active": True,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }).execute()

    # --- Backup store: Fly.io secret AUTH_CREDENTIALS_JSON ---
    sync_user(
        username,
        display_name=display,
        password_hash=pw_hash,
        role=role,
        active=True,
    )


def update_account(username: str, display_name: str, role: str, active: bool) -> None:
    client = _get_supabase()
    if not client and not fly_available():
        raise RuntimeError(
            "Either Supabase service role credentials or Fly.io credentials "
            "(FLY_API_TOKEN + FLY_APP_NAME) are required to manage accounts."
        )
    if role not in ACCOUNT_ROLES:
        raise ValueError("Role is not valid.")

    display = display_name.strip() or normalize_username(username)

    # --- Primary store: Supabase ---
    if client:
        client.table("app_users").update({
            "display_name": display,
            "role": role,
            "active": active,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("username", normalize_username(username)).execute()

    # --- Backup store: Fly.io secret ---
    sync_user_fields(
        normalize_username(username),
        display_name=display,
        role=role,
        active=active,
    )


def reset_password(username: str, password: str) -> None:
    client = _get_supabase()
    if not client and not fly_available():
        raise RuntimeError(
            "Either Supabase service role credentials or Fly.io credentials "
            "(FLY_API_TOKEN + FLY_APP_NAME) are required to manage accounts."
        )
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")

    pw_hash = hash_password(password)

    # --- Primary store: Supabase ---
    if client:
        client.table("app_users").update({
            "password_hash": pw_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("username", normalize_username(username)).execute()

    # --- Backup store: Fly.io secret ---
    sync_user_fields(normalize_username(username), password_hash=pw_hash)
