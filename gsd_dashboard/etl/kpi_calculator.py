"""
ETL: KPI snapshot calculator

Runs daily at 07:00 UTC (Asia/Beirut = 10:00 local).
Computes current KPI values from Supabase tables and inserts
a daily snapshot into kpi_snapshots. Used in production mode.

In DEMO_MODE the app calculates KPIs live from the static JSON;
this module is not invoked.
"""
from __future__ import annotations

import logging
import os
from datetime import date

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _client():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def calculate_and_snapshot_kpis() -> None:
    log.info("Calculating KPI snapshots…")
    client = _client()
    today  = date.today().isoformat()

    # ── KPI001: Stakeholder Engagement ────────────────────────────────────────
    stk_rows  = client.table("stakeholders").select("actor_category, access_status").execute().data
    total_cats = 7
    confirmed  = {r["actor_category"] for r in stk_rows if r.get("access_status") == "confirmed"}
    kpi001     = round(len(confirmed) / total_cats * 100, 1)
    _upsert_snapshot(client, "KPI001", kpi001, today)

    # ── KPI002: Delivery Timeliness ───────────────────────────────────────────
    del_rows = client.table("deliverables").select("due_date, submitted_at").execute().data
    variances = []
    for r in del_rows:
        if r.get("submitted_at") and r.get("due_date"):
            from datetime import datetime
            delta = (
                datetime.fromisoformat(r["submitted_at"]) -
                datetime.fromisoformat(r["due_date"])
            ).days
            variances.append(delta)
    kpi002 = round(sum(variances) / len(variances), 1) if variances else None
    if kpi002 is not None:
        _upsert_snapshot(client, "KPI002", kpi002, today)

    # ── KPI003: Standards Coverage ────────────────────────────────────────────
    mod_rows  = client.table("modules").select("status").execute().data
    aligned   = sum(1 for r in mod_rows if r["status"] in ("standards_aligned", "finalized"))
    kpi003    = round(aligned / max(len(mod_rows), 1) * 100, 1)
    _upsert_snapshot(client, "KPI003", kpi003, today)

    # ── KPI004: Open Issues ───────────────────────────────────────────────────
    issue_rows = client.table("issues").select("status").execute().data
    kpi004     = sum(1 for r in issue_rows if r["status"] == "open")
    _upsert_snapshot(client, "KPI004", float(kpi004), today)

    # ── KPI005: Curriculum Completion ─────────────────────────────────────────
    finalized = sum(1 for r in mod_rows if r["status"] == "finalized")
    kpi005    = round(finalized / max(len(mod_rows), 1) * 100, 1)
    _upsert_snapshot(client, "KPI005", kpi005, today)

    log.info("KPI snapshots written for %s.", today)


def _upsert_snapshot(client, kpi_id: str, value: float, snapshot_date: str) -> None:
    client.table("kpi_snapshots").upsert({
        "kpi_id":        kpi_id,
        "snapshot_date": snapshot_date,
        "value":         value,
    }, on_conflict="kpi_id,snapshot_date").execute()
