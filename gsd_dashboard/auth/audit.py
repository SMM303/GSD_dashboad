"""
Audit logging — writes every sensitive page access and form submission to
the backing store (demo_store JSON or Supabase audit_log table).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import streamlit as st


def _is_demo() -> bool:
    try:
        return str(st.secrets.get("DEMO_MODE", "true")).lower() in ("true", "1", "yes")
    except Exception:
        return True


def log_action(action: str, record_type: str, record_id: str = "") -> None:
    """
    Log a user action.

    Parameters
    ----------
    action      : e.g. "view_risk_register", "update_deliverable_status"
    record_type : e.g. "page", "risk", "deliverable", "milestone"
    record_id   : the ID of the affected record (empty string for page-level events)
    """
    user     = st.session_state.get("username", "anonymous")
    role     = st.session_state.get("user_role", "unknown")
    session  = st.session_state.get("session_id")
    if not session:
        session = str(uuid.uuid4())
        st.session_state["session_id"] = session

    ts = datetime.now(timezone.utc).isoformat()

    if _is_demo():
        from data.demo_store import log_audit
        log_audit(user, role, action, record_type, str(record_id), session)
    else:
        try:
            from data.queries import _get_supabase
            client = _get_supabase()
            if client:
                client.table("audit_log").insert({
                    "user":        user,
                    "role":        role,
                    "action":      action,
                    "record_type": record_type,
                    "record_id":   str(record_id),
                    "session_id":  session,
                    "timestamp":   ts,
                }).execute()
        except Exception:
            pass  # Audit failure must never break the application
