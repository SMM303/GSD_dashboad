"""
ETL: Google Sheets → Supabase

Used when DEMO_MODE = false. Pulled on a schedule by etl/scheduler.py.
Each function reads one tab from the configured spreadsheet and upserts
to the corresponding Supabase table via the service-role key.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID", "")
CREDS_JSON     = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
SUPABASE_URL   = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY   = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")   # service role — ETL only


# ── Actor category lookup ─────────────────────────────────────────────────────

ACTOR_CATEGORY_MAP = {
    "GSD Leadership":                       "GSD_leadership",
    "GSD Training Academy":                 "GSD_academy",
    "GSD Land Border Units":                "GSD_operational",
    "GSD Airport Unit":                     "GSD_operational",
    "GSD Maritime Unit":                    "GSD_operational",
    "GSD Legal Unit":                       "GSD_legal_it",
    "GSD IT/Data Unit":                     "GSD_legal_it",
    "IOM Lebanon IBG Programme Team":       "IOM",
    "Lebanese Armed Forces (LAF)":          "national_partner",
    "Lebanese Customs Directorate":         "national_partner",
    "Ministry of Public Health":            "national_partner",
    "Ministry of Interior":                 "national_partner",
    "UNHCR Lebanon":                        "international_partner",
    "UNODC Regional Office":               "international_partner",
    "European Union Delegation":            "international_partner",
    "INTERPOL National Central Bureau":     "international_partner",
}


# ── Clients ───────────────────────────────────────────────────────────────────

def _gspread_client():
    import gspread
    creds = json.loads(CREDS_JSON)
    return gspread.service_account_from_dict(creds)


def _supabase_client():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Generic upsert ─────────────────────────────────────────────────────────────

def _upsert(table: str, records: list[dict], on_conflict: str = "id") -> int:
    if not records:
        return 0
    client = _supabase_client()
    client.table(table).upsert(records, on_conflict=on_conflict).execute()
    return len(records)


def _log_sync(table_name: str, rows_upserted: int) -> None:
    client = _supabase_client()
    client.table("etl_sync_log").insert({
        "table_name":    table_name,
        "synced_at":     datetime.now(timezone.utc).isoformat(),
        "rows_upserted": rows_upserted,
    }).execute()
    log.info("Synced %s: %d rows upserted.", table_name, rows_upserted)


# ── Sheet fetcher with retry ───────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=30))
def _fetch_sheet(tab_name: str) -> list[dict]:
    gc = _gspread_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(tab_name).get_all_records()


# ── Sync functions ─────────────────────────────────────────────────────────────

def sync_issue_log() -> None:
    log.info("Syncing Issue Log…")
    rows = _fetch_sheet("Issue Log")
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Normalise expected columns
    column_map = {
        "issue_number": "id",
        "issue_#":      "id",
        "#":            "id",
    }
    df = df.rename(columns=column_map)

    records = df.to_dict(orient="records")
    n = _upsert("issues", records, on_conflict="id")
    _log_sync("issues", n)


def sync_stakeholders() -> None:
    log.info("Syncing Stakeholder Map…")
    rows = _fetch_sheet("Stakeholder Map")
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Map organisation to actor_category
    org_col = next((c for c in df.columns if "organ" in c or "unit" in c), None)
    if org_col:
        df["actor_category"] = df[org_col].map(ACTOR_CATEGORY_MAP).fillna("national_partner")

    records = df.to_dict(orient="records")
    n = _upsert("stakeholders", records, on_conflict="id")
    _log_sync("stakeholders", n)


def sync_standards() -> None:
    log.info("Syncing Standards Reference…")
    rows = _fetch_sheet("Standards Reference")
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    records = df.to_dict(orient="records")
    n = _upsert("standards_mappings", records, on_conflict="id")
    _log_sync("standards", n)
