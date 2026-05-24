"""
Seed Supabase from data/programme_config.json.

Run after db/migrations.sql has been applied:
  SUPABASE_URL="..." SUPABASE_SERVICE_ROLE_KEY="..." python scripts/seed_supabase.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from supabase import create_client


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "programme_config.json"


def _client():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY before running this script.")
    return create_client(url, key)


def _upsert(client: Any, table: str, rows: list[dict], on_conflict: str = "id") -> None:
    if rows:
        client.table(table).upsert(rows, on_conflict=on_conflict).execute()
        print(f"Seeded {len(rows):>3} rows into {table}")


def _table_has_rows(client: Any, table: str) -> bool:
    result = client.table(table).select("id").limit(1).execute()
    return bool(result.data)


def main() -> None:
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    client = _client()

    _upsert(client, "phases", [
        {
            "id": row["id"],
            "name": row["name"],
            "start_week": row["start_week"],
            "end_week": row["end_week"],
            "status": row["status"],
        }
        for row in config.get("phases", [])
    ])

    _upsert(client, "milestones", [
        {
            "id": row["id"],
            "description": row["description"],
            "target_date": row["target_date"],
            "completed": row["completed"],
            "completed_date": row["completed_date"],
        }
        for row in config.get("milestones", [])
    ])

    _upsert(client, "deliverables", [
        {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "phase_id": row["phase_id"],
            "due_week": row["due_week"],
            "due_date": row["due_date"],
            "payment_pct": row["payment_pct"],
            "status": row["status"],
            "submitted_at": row["submitted_at"],
            "approved_at": row["approved_at"],
            "reviewer": row["reviewer"],
            "quality_gate": row["quality_gate"],
        }
        for row in config.get("deliverables", [])
    ])

    _upsert(client, "modules", [
        {
            "id": row["id"],
            "title": row["title"],
            "phase_id": row["phase_id"],
            "status": row["status"],
            "applicable_deliverable": row["applicable_deliverable"],
        }
        for row in config.get("modules", [])
    ])

    _upsert(client, "stakeholders", [
        {
            "id": row["id"],
            "org_unit": row["org_unit"],
            "contact_name": row.get("contact_name"),
            "contact_title": row.get("contact_title"),
            "actor_category": row["actor_category"],
            "role": row["role"],
            "method": row["method"],
            "access_status": row["access_status"],
            "consultation_window": row.get("consultation_window"),
            "engagement_score": row.get("engagement_score"),
        }
        for row in config.get("stakeholders", [])
    ])

    _upsert(client, "risks", [
        {
            "id": row["id"],
            "description": row["description"],
            "category": row["category"],
            "likelihood": row["likelihood"],
            "impact": row["impact"],
            "mitigation": row["mitigation"],
            "escalation_trigger": row["escalation_trigger"],
            "status": row["status"],
            "owner": row["owner"],
            "raised_date": row["raised_date"],
        }
        for row in config.get("risks", [])
    ])

    issues = config.get("issues", [])
    if issues:
        _upsert(client, "issues", issues)

    if not _table_has_rows(client, "risk_history"):
        risk_history = []
        for risk in config.get("risks", []):
            for row in risk.get("history", []):
                risk_history.append({
                    "risk_id": risk["id"],
                    "date": row["date"],
                    "likelihood": row["likelihood"],
                    "impact": row["impact"],
                    "status": row["status"],
                })
        if risk_history:
            client.table("risk_history").insert(risk_history).execute()
            print(f"Seeded {len(risk_history):>3} rows into risk_history")

    if not _table_has_rows(client, "standards_mappings"):
        mappings = []
        for ref in config.get("standards_reference", []):
            for module_id in ref.get("modules", []):
                mappings.append({
                    "module_id": module_id,
                    "source": ref["source"],
                    "standard": ref["standard"],
                    "status": ref.get("status", "mapped"),
                })
        if mappings:
            client.table("standards_mappings").insert(mappings).execute()
            print(f"Seeded {len(mappings):>3} rows into standards_mappings")

    print("Supabase seed complete.")


if __name__ == "__main__":
    main()
