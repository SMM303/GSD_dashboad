"""
Authentication layer.

DEMO_MODE = true  : simple username/password dict, no bcrypt.
                    Passwords intentionally short — for local demo only.
DEMO_MODE = false : streamlit-authenticator with bcrypt-hashed credentials
                    stored in st.secrets["auth_credentials"].
                    Run scripts/generate_hashes.py to produce hashes.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import streamlit as st


# ---------------------------------------------------------------------------
# Demo users — plain-text passwords, roles assigned directly
# ---------------------------------------------------------------------------

DEMO_USERS: dict[str, dict] = {
    "saleh.mansour": {
        "password": "consultant123",
        "name":     "Saleh Mansour",
        "role":     "implementation",
    },
    "iom.pm": {
        "password": "pm123",
        "name":     "IBG Programme Manager",
        "role":     "implementation",
    },
    "iom.hoo": {
        "password": "hoo123",
        "name":     "Head of Office",
        "role":     "executive",
    },
    "iom.oversight": {
        "password": "oversight123",
        "name":     "IOM Oversight Reviewer",
        "role":     "oversight",
    },
}


def _is_demo() -> bool:
    return str(_secret("DEMO_MODE", os.environ.get("DEMO_MODE", "true"))).lower() in ("true", "1", "yes")


def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


def get_session_timeout_minutes() -> int:
    raw_value = _secret("SESSION_TIMEOUT_MINUTES", os.environ.get("SESSION_TIMEOUT_MINUTES", "30"))
    try:
        return max(5, int(raw_value))
    except (TypeError, ValueError):
        return 30


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_session_time(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _start_session(username: str, display_name: str, role: str) -> None:
    now = _now_utc().isoformat()
    st.session_state["authenticated"] = True
    st.session_state["username"] = username
    st.session_state["display_name"] = display_name
    st.session_state["user_role"] = role
    st.session_state["session_id"] = str(uuid.uuid4())
    st.session_state["authenticated_at"] = now
    st.session_state["last_activity_at"] = now


def _clear_session(expired: bool = False) -> None:
    for key in [
        "authenticated",
        "username",
        "display_name",
        "user_role",
        "session_id",
        "authenticated_at",
        "last_activity_at",
    ]:
        st.session_state.pop(key, None)
    if expired:
        st.session_state["session_expired"] = True


def enforce_session_timeout() -> bool:
    """Return True when the active session is still valid."""
    if not is_authenticated():
        return False

    last_activity = _parse_session_time(st.session_state.get("last_activity_at"))
    if last_activity is None:
        _clear_session(expired=True)
        return False

    timeout = timedelta(minutes=get_session_timeout_minutes())
    if _now_utc() - last_activity > timeout:
        _clear_session(expired=True)
        return False

    st.session_state["last_activity_at"] = _now_utc().isoformat()
    return True


def get_session_remaining_minutes() -> int:
    last_activity = _parse_session_time(st.session_state.get("last_activity_at"))
    if not last_activity:
        return 0
    expires_at = last_activity + timedelta(minutes=get_session_timeout_minutes())
    remaining = expires_at - _now_utc()
    remaining_seconds = max(0, remaining.total_seconds())
    return int((remaining_seconds + 59) // 60)


def get_user_role() -> str:
    return st.session_state.get("user_role", "executive")


def get_username() -> str:
    return st.session_state.get("username", "")


def get_display_name() -> str:
    return st.session_state.get("display_name", "")


# ---------------------------------------------------------------------------
# Login form
# ---------------------------------------------------------------------------

def render_login_page() -> None:
    """Render the login screen and set session state on success."""
    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        st.markdown('<div class="login-header">IOM Lebanon / GSD</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Curriculum Development Consultancy — Programme Dashboard</div>', unsafe_allow_html=True)
        if st.session_state.pop("session_expired", False):
            st.warning("Your session expired for security. Please sign in again.")

        if _is_demo():
            _demo_login_form()
        else:
            _production_login_form()


def _demo_login_form() -> None:
    st.info("Demo mode - use the credentials below.")
    st.caption(
        "**saleh.mansour** / consultant123 (Implementation)  \n"
        "**iom.pm** / pm123 (Implementation - IBG PM)  \n"
        "**iom.hoo** / hoo123 (Executive)  \n"
        "**iom.oversight** / oversight123 (Oversight)"
    )

    with st.form("demo_login"):
        username = st.text_input("Username", placeholder="e.g. saleh.mansour")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign in", width="stretch")

    if submit:
        user = DEMO_USERS.get(username.strip().lower())
        if user and user["password"] == password:
            _start_session(username.strip().lower(), user["name"], user["role"])
            st.rerun()
        else:
            st.error("Incorrect username or password.")


def _production_login_form() -> None:
    """Use private bcrypt-hashed credentials from secrets or environment."""
    import yaml

    from auth.accounts import authenticate_account, verify_password

    try:
        raw_config = _secret("auth_credentials") or os.environ.get("AUTH_CREDENTIALS_YAML")
        config = yaml.safe_load(raw_config) if isinstance(raw_config, str) and raw_config else raw_config
    except Exception:
        config = None

    users = (config or {}).get("credentials", {}).get("usernames", {})
    st.caption(f"Production mode · Sessions expire after {get_session_timeout_minutes()} minutes of inactivity.")

    with st.form("production_login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign in", width="stretch")

    if submit:
        username = username.strip().lower()
        account = authenticate_account(username, password)
        if account:
            _start_session(
                account["username"],
                account["name"],
                account["role"],
            )
            st.rerun()

        user_cfg = users.get(username)
        hashed = str(user_cfg.get("password", "")) if user_cfg else ""
        if user_cfg and verify_password(password, hashed):
            _start_session(
                username,
                user_cfg.get("name", username),
                user_cfg.get("role", "executive"),
            )
            st.rerun()

        st.error("Incorrect username or password.")

    if st.session_state.get("authenticated"):
        st.rerun()


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout() -> None:
    _clear_session()
    st.rerun()


# ---------------------------------------------------------------------------
# Guard — call at the top of every page
# ---------------------------------------------------------------------------

def require_auth() -> None:
    """Redirect to login if not authenticated. Call at top of every page."""
    if not is_authenticated() or not enforce_session_timeout():
        st.switch_page("app.py")
        st.stop()
