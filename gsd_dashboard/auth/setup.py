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

import streamlit as st
from typing import Optional, Tuple


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
    try:
        value = st.secrets.get("DEMO_MODE", os.environ.get("DEMO_MODE", "true"))
        return str(value).lower() in ("true", "1", "yes")
    except Exception:
        return str(os.environ.get("DEMO_MODE", "true")).lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


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
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=Inter:wght@300;400&display=swap');
    .login-header { font-family: 'Playfair Display', serif; font-size: 26px;
                    color: #1B3A6B; text-align: center; margin-bottom: 4px; }
    .login-sub    { font-family: 'Inter', sans-serif; font-size: 13px;
                    color: #6b7280; text-align: center; margin-bottom: 28px; }
    </style>
    """, unsafe_allow_html=True)

    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.markdown('<div class="login-header">IOM Lebanon / GSD</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Curriculum Development Consultancy — Programme Dashboard</div>', unsafe_allow_html=True)

        if _is_demo():
            _demo_login_form()
        else:
            _production_login_form()


def _demo_login_form() -> None:
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.info("Demo mode — use the credentials below.")
        st.caption(
            "**saleh.mansour** / consultant123 (Implementation)  \n"
            "**iom.pm** / pm123 (Implementation — IBG PM)  \n"
            "**iom.hoo** / hoo123 (Executive)  \n"
            "**iom.oversight** / oversight123 (Oversight)"
        )

        with st.form("demo_login"):
            username = st.text_input("Username", placeholder="e.g. saleh.mansour")
            password = st.text_input("Password", type="password")
            submit   = st.form_submit_button("Sign In", width="stretch")

        if submit:
            user = DEMO_USERS.get(username.strip().lower())
            if user and user["password"] == password:
                import uuid
                st.session_state["authenticated"]  = True
                st.session_state["username"]        = username.strip().lower()
                st.session_state["display_name"]    = user["name"]
                st.session_state["user_role"]       = user["role"]
                st.session_state["session_id"]      = str(uuid.uuid4())
                st.rerun()
            else:
                st.error("Incorrect username or password.")


def _production_login_form() -> None:
    """Uses streamlit-authenticator with bcrypt-hashed credentials."""
    import streamlit_authenticator as stauth
    import yaml

    try:
        raw_config = st.secrets.get("auth_credentials") or os.environ.get("AUTH_CREDENTIALS_YAML")
        if not raw_config:
            raise KeyError("auth_credentials")
        config     = yaml.safe_load(raw_config) if isinstance(raw_config, str) else raw_config
    except Exception:
        st.error("auth_credentials not found. Set AUTH_CREDENTIALS_YAML or use DEMO_MODE=true.")
        return

    cookie = st.secrets.get("auth_cookie", {})
    cookie_name = cookie.get("name") or os.environ.get("AUTH_COOKIE_NAME", "gsd_auth")
    cookie_key = cookie.get("key") or os.environ.get("AUTH_COOKIE_KEY", "CHANGE_ME")
    cookie_expiry = cookie.get("expiry_days") or int(os.environ.get("AUTH_COOKIE_EXPIRY_DAYS", "1"))
    authenticator = stauth.Authenticate(
        config["credentials"],
        cookie_name,
        cookie_key,
        cookie_expiry,
    )

    authenticator.login()

    status = st.session_state.get("authentication_status")
    if status:
        import uuid
        username = st.session_state.get("username", "")
        user_cfg = config["credentials"]["usernames"].get(username, {})
        st.session_state["authenticated"] = True
        st.session_state["user_role"]     = user_cfg.get("role", "executive")
        st.session_state["display_name"]  = st.session_state.get("name", username)
        st.session_state.setdefault("session_id", str(uuid.uuid4()))
        st.rerun()
    elif status is False:
        st.error("Incorrect username or password.")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout() -> None:
    for key in ["authenticated", "username", "display_name", "user_role", "session_id"]:
        st.session_state.pop(key, None)
    st.rerun()


# ---------------------------------------------------------------------------
# Guard — call at the top of every page
# ---------------------------------------------------------------------------

def require_auth() -> None:
    """Redirect to login if not authenticated. Call at top of every page."""
    if not is_authenticated():
        st.switch_page("app.py")
        st.stop()
