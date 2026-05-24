"""
Application error handling.

Two rules:
  1. Users only see safe, friendly messages (or their own validation feedback).
  2. Full exception detail — stack trace, context, correlation ref — goes to
     the server log (stdout → Fly.io log drain) and nowhere else.

Usage
-----
from utils.errors import AppError, get_logger, ui_error

log = get_logger(__name__)

try:
    do_something_risky()
except AppError:
    raise                           # let it propagate to the page handler
except Exception as exc:
    ui_error(exc, context="save_deliverable", logger=log)

# In library code, raise typed errors that have safe messages:
if not username:
    raise ValueError("Username is required.")           # safe to show
if supabase_down:
    raise AppError("Account service is unavailable. Please try again.")  # safe to show
# Never raise RuntimeError / generic Exception with internal detail to the UI.
"""
from __future__ import annotations

import logging
import uuid

import streamlit as st


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger.  Formatting is set once in app.py."""
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Typed application error
# ---------------------------------------------------------------------------

class AppError(Exception):
    """
    A typed exception whose message is safe to show directly to users.

    Raise this (not RuntimeError) when you want a specific human-readable
    message displayed in the UI without leaking internals.

    Example
    -------
        raise AppError("Account service is unavailable. Please try again.")
    """
    def __init__(self, user_message: str) -> None:
        self.user_message = user_message
        super().__init__(user_message)


# ---------------------------------------------------------------------------
# UI error handler
# ---------------------------------------------------------------------------

def ui_error(
    exc: Exception,
    *,
    context: str = "",
    logger: logging.Logger | None = None,
) -> None:
    """
    Handle an exception at the Streamlit UI boundary.

    - Logs the full exception with a short correlation reference.
    - Shows a clean, non-leaking message in the UI.

    Parameters
    ----------
    exc     : the caught exception
    context : a short label for where this happened, e.g. "create_account"
    logger  : module logger; falls back to the root 'app' logger

    Exception → user message rules
    --------------------------------
    ValueError   → show the message as-is  (our own input validation)
    AppError     → show exc.user_message   (our own typed safe messages)
    anything else → generic message + ref  (never leak internals)
    """
    log = logger or logging.getLogger("app")
    ref = _short_ref()

    log.error(
        "Unhandled error [ref=%s] context=%r: %s",
        ref,
        context or "unknown",
        exc,
        exc_info=True,
    )

    if isinstance(exc, ValueError):
        # Our own validation errors — messages are intentionally user-facing.
        st.error(str(exc))

    elif isinstance(exc, AppError):
        # Our own typed safe messages.
        st.error(exc.user_message)

    else:
        # Unknown / system error — show nothing internal.
        st.error(
            f"Something went wrong. "
            f"Reference: **{ref}** — contact your administrator if this persists."
        )


def _short_ref() -> str:
    """Return an 8-character uppercase correlation ID."""
    return uuid.uuid4().hex[:8].upper()
