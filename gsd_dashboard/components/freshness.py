"""
Data freshness badge — shown in the sidebar on every page.
Reads etl_sync_log from demo_store or Supabase.
"""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st


_STALE_MINUTES = {
    "issues":        90,
    "stakeholders":  90,
    "standards":     1500,
    "kpi_snapshots": 1500,
}


def render_freshness_badges() -> None:
    """Call inside a `with st.sidebar:` block."""
    try:
        from data.demo_store import _load_or_init
        live = _load_or_init()
        sync_rows = live.get("etl_sync_log", [])
    except Exception:
        return

    if not sync_rows:
        return

    st.sidebar.markdown("---")
    st.sidebar.caption("**Data freshness**")
    now = datetime.now(timezone.utc)

    for row in sync_rows:
        table     = row.get("table_name", "unknown")
        synced_at = row.get("synced_at", "")
        try:
            ts      = datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
            age_min = (now - ts).total_seconds() / 60
        except Exception:
            st.sidebar.caption(f"• {table}: unknown")
            continue

        threshold = _STALE_MINUTES.get(table, 120)
        if age_min > threshold:
            st.sidebar.warning(f"{table}: {int(age_min)} min ago")
        else:
            st.sidebar.caption(f"{table}: {int(age_min)} min ago")
