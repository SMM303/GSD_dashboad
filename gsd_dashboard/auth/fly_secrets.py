"""
Fly.io Machines API — credential sync.

When Supabase is the primary store, this module keeps a JSON copy of all
managed accounts in the Fly.io app secret AUTH_CREDENTIALS_JSON.  That copy
is read at login time whenever Supabase is unreachable, so the app keeps
working through outages.

Required secrets / env vars (both are optional — if absent the sync is
silently skipped):
  FLY_API_TOKEN  — a Fly.io token with write access to the app's secrets
                   (personal token or deploy token scoped to the app)
  FLY_APP_NAME   — the Fly.io app name, e.g. gsd-programme-dashboard
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import streamlit as st

_FLY_API = "https://api.machines.dev/v1"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _token() -> str | None:
    return _secret("FLY_API_TOKEN") or os.environ.get("FLY_API_TOKEN")


def _app() -> str | None:
    return (
        _secret("FLY_APP_NAME")
        or os.environ.get("FLY_APP_NAME")
        or os.environ.get("FLY_APP")          # set automatically inside Fly machines
    )


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }


def _post(url: str, body: Any, *, timeout: int = 15) -> None:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    try:
        urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Fly.io API {exc.code}: {exc.read().decode(errors='replace')}"
        ) from exc


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def fly_available() -> bool:
    """Return True when both token and app name are configured."""
    return bool(_token() and _app())


def get_fly_credentials() -> dict[str, dict]:
    """
    Return the users dict from AUTH_CREDENTIALS_JSON as loaded by Streamlit.

    The secret is already present in st.secrets / os.environ when the app
    starts; we never need to fetch it via the API.

    Structure: { "username": { "display_name", "password_hash", "role", "active" } }
    """
    raw = _secret("AUTH_CREDENTIALS_JSON") or os.environ.get("AUTH_CREDENTIALS_JSON", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def push_credentials(users: dict[str, dict]) -> None:
    """
    Overwrite AUTH_CREDENTIALS_JSON on Fly.io with *users*.

    Does NOT restart machines — existing sessions keep running and new
    machines (next deploy or scale-up) will pick up the updated secret.

    Raises RuntimeError if the API call fails.
    """
    if not fly_available():
        raise RuntimeError(
            "FLY_API_TOKEN and FLY_APP_NAME must be set to sync with Fly.io."
        )
    app = _app()
    url = f"{_FLY_API}/apps/{app}/secrets"
    body = [{"key": "AUTH_CREDENTIALS_JSON", "value": json.dumps(users), "type": "opaque"}]
    _post(url, body)


def sync_user(
    username: str,
    *,
    display_name: str,
    password_hash: str,
    role: str,
    active: bool = True,
) -> None:
    """
    Add or update a single user in AUTH_CREDENTIALS_JSON on Fly.io.

    Silently skips if Fly.io credentials are not configured.
    Raises RuntimeError on API error.
    """
    if not fly_available():
        return
    users = get_fly_credentials()
    users[username] = {
        "display_name": display_name,
        "password_hash": password_hash,
        "role": role,
        "active": active,
    }
    push_credentials(users)


def sync_user_fields(username: str, **fields) -> None:
    """
    Patch specific fields for an existing user in AUTH_CREDENTIALS_JSON.

    Silently skips if the user is not in the current secret or Fly.io is
    not configured.
    """
    if not fly_available():
        return
    users = get_fly_credentials()
    if username not in users:
        return
    users[username].update(fields)
    push_credentials(users)


def remove_fly_user(username: str) -> None:
    """
    Remove a user from AUTH_CREDENTIALS_JSON on Fly.io.

    Silently skips if user not present or Fly.io not configured.
    """
    if not fly_available():
        return
    users = get_fly_credentials()
    if username not in users:
        return
    del users[username]
    push_credentials(users)
