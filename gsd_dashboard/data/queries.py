"""
Unified data access layer.

In DEMO_MODE (default), reads from programme_config.json + live_data.json
via demo_store. In production, reads from Supabase with RLS enforced.

All public functions return pandas DataFrames or validated Pydantic objects.
The rest of the application never calls demo_store or Supabase directly.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

from models.programme import ProgrammePayload

_CONFIG_PATH = Path(__file__).parent / "programme_config.json"

# ---------------------------------------------------------------------------
# Column visibility map — enforced before data reaches the UI layer
# ---------------------------------------------------------------------------

STAKEHOLDER_COLS_BY_ROLE: dict[str, list[str]] = {
    "implementation": [
        "id", "org_unit", "contact_name", "contact_title",
        "actor_category", "role", "method",
        "access_status", "consultation_window", "engagement_score",
    ],
    "executive": [
        "id", "org_unit", "actor_category", "access_status", "engagement_score",
    ],
    "oversight": [
        "id", "org_unit", "actor_category", "access_status",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_demo() -> bool:
    try:
        value = st.secrets.get("DEMO_MODE", os.environ.get("DEMO_MODE", "true"))
        return str(value).lower() in ("true", "1", "yes")
    except Exception:
        return str(os.environ.get("DEMO_MODE", "true")).lower() in ("true", "1", "yes")


def _get_supabase():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        key = (
            st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
            or st.secrets.get("SUPABASE_ANON_KEY")
            or os.environ.get("SUPABASE_ANON_KEY", "")
        )
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _fetch_table(client: Any, table: str, select: str = "*") -> list[dict]:
    try:
        return client.table(table).select(select).execute().data or []
    except Exception:
        return []


def _by_id(rows: list[dict]) -> dict:
    return {row["id"]: row for row in rows if row.get("id") is not None}


def _merge_rows_by_id(config_rows: list[dict], live_rows: list[dict]) -> list[dict]:
    live_by_id = _by_id(live_rows)
    merged_rows = []
    seen = set()
    for row in config_rows:
        merged = dict(row)
        live = live_by_id.get(row.get("id"))
        if live:
            merged.update({k: v for k, v in live.items() if v is not None})
            seen.add(row.get("id"))
        merged_rows.append(merged)
    for row in live_rows:
        if row.get("id") not in seen:
            merged_rows.append(row)
    return merged_rows


def _load_supabase_payload() -> dict:
    """Merge static programme metadata with live Supabase table state."""
    with open(_CONFIG_PATH) as f:
        raw = json.load(f)

    client = _get_supabase()
    if not client:
        return raw

    raw["phases"] = _merge_rows_by_id(raw.get("phases", []), _fetch_table(client, "phases"))
    raw["milestones"] = _merge_rows_by_id(raw.get("milestones", []), _fetch_table(client, "milestones"))

    deliverables = _merge_rows_by_id(raw.get("deliverables", []), _fetch_table(client, "deliverables"))
    history_rows = _fetch_table(client, "deliverable_status_history")
    history_by_deliverable: dict[str, list[dict]] = {}
    for row in history_rows:
        deliverable_id = row.get("deliverable_id")
        if deliverable_id:
            history_by_deliverable.setdefault(deliverable_id, []).append({
                "status": row.get("status"),
                "changed_at": row.get("changed_at"),
                "changed_by": row.get("changed_by"),
            })
    for row in deliverables:
        if row.get("id") in history_by_deliverable:
            row["status_history"] = history_by_deliverable[row["id"]]
    raw["deliverables"] = deliverables

    modules = _merge_rows_by_id(raw.get("modules", []), _fetch_table(client, "modules"))
    standards_rows = _fetch_table(client, "standards_mappings")
    standards_by_module: dict[str, list[str]] = {}
    for row in standards_rows:
        module_id = row.get("module_id")
        standard = row.get("standard") or row.get("source")
        if module_id and standard:
            standards_by_module.setdefault(module_id, []).append(standard)
    for row in modules:
        if row.get("id") in standards_by_module:
            row["standards_mapped"] = standards_by_module[row["id"]]
    raw["modules"] = modules

    stakeholder_rows = _fetch_table(client, "stakeholders")
    if stakeholder_rows:
        raw["stakeholders"] = stakeholder_rows

    risks = _merge_rows_by_id(raw.get("risks", []), _fetch_table(client, "risks"))
    risk_history_rows = _fetch_table(client, "risk_history")
    risk_history_by_risk: dict[str, list[dict]] = {}
    for row in risk_history_rows:
        risk_id = row.get("risk_id")
        if risk_id:
            risk_history_by_risk.setdefault(risk_id, []).append({
                "date": row.get("date"),
                "likelihood": row.get("likelihood"),
                "impact": row.get("impact"),
                "status": row.get("status"),
            })
    for row in risks:
        if row.get("id") in risk_history_by_risk:
            row["history"] = risk_history_by_risk[row["id"]]
    raw["risks"] = risks

    issue_rows = _fetch_table(client, "issues")
    if issue_rows:
        raw["issues"] = issue_rows

    snapshots = _fetch_table(client, "kpi_snapshots")
    snapshots_by_kpi: dict[str, list[dict]] = {}
    for row in snapshots:
        kpi_id = row.get("kpi_id")
        if kpi_id:
            snapshots_by_kpi.setdefault(kpi_id, []).append(row)
    for kpi in raw.get("kpis", []):
        points = sorted(
            snapshots_by_kpi.get(kpi.get("id"), []),
            key=lambda row: row.get("snapshot_date") or "",
        )
        if points:
            kpi["trend"] = [
                {"date": point.get("snapshot_date"), "value": point.get("value")}
                for point in points
            ]
            kpi["current_value"] = points[-1].get("value")

    return raw


# ---------------------------------------------------------------------------
# Programme config (static — no TTL)
# ---------------------------------------------------------------------------

@st.cache_resource
def load_payload() -> ProgrammePayload:
    """Load, merge, and validate the full programme payload through Pydantic."""
    if _is_demo():
        from data.demo_store import get_full_payload
        raw = get_full_payload()
    else:
        raw = _load_supabase_payload()
    return ProgrammePayload.model_validate(raw)


# ---------------------------------------------------------------------------
# Deliverables
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900)
def fetch_deliverables() -> pd.DataFrame:
    payload = load_payload()
    rows = []
    for d in payload.deliverables:
        rows.append({
            "id":               d.id,
            "name":             d.name,
            "description":      d.description,
            "phase_id":         d.phase_id,
            "due_date":         d.due_date,
            "due_week":         d.due_week,
            "payment_pct":      d.payment_pct,
            "status":           d.status.value,
            "submitted_at":     d.submitted_at,
            "approved_at":      d.approved_at,
            "reviewer":         d.reviewer,
            "quality_gate":     d.quality_gate.value,
            "days_to_deadline": d.days_to_deadline,
            "variance_days":    d.variance_days,
            "is_overdue":       d.is_overdue,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900)
def fetch_milestones() -> pd.DataFrame:
    payload = load_payload()
    rows = []
    for m in payload.milestones:
        rows.append({
            "id":             m.id,
            "description":    m.description,
            "target_date":    m.target_date,
            "completed":      m.completed,
            "completed_date": m.completed_date,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900)
def fetch_phases() -> pd.DataFrame:
    payload = load_payload()
    start   = payload.programme.start_date
    rows = []
    for p in payload.phases:
        rows.append({
            "id":         p.id,
            "name":       p.name,
            "start_week": p.start_week,
            "end_week":   p.end_week,
            "status":     p.status.value,
            "abs_start":  p.abs_start(start),
            "abs_end":    p.abs_end(start),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def fetch_risks() -> pd.DataFrame:
    payload = load_payload()
    rows = []
    for r in payload.risks:
        rows.append({
            "id":                 r.id,
            "description":        r.description,
            "category":           r.category.value,
            "likelihood":         r.likelihood,
            "impact":             r.impact,
            "risk_score":         r.risk_score,
            "mitigation":         r.mitigation,
            "escalation_trigger": r.escalation_trigger,
            "status":             r.status.value,
            "owner":              r.owner,
            "raised_date":        r.raised_date,
            "history":            [h.model_dump() for h in r.history],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_issues() -> pd.DataFrame:
    payload = load_payload()
    if not payload.issues:
        return pd.DataFrame(columns=[
            "id", "date_raised", "description", "category",
            "risk_level", "assigned_to", "target_date", "status", "is_overdue"
        ])
    rows = []
    for i in payload.issues:
        rows.append({
            "id":          i.id,
            "date_raised": i.date_raised,
            "description": i.description,
            "category":    i.category.value,
            "risk_level":  i.risk_level.value,
            "assigned_to": i.assigned_to,
            "target_date": i.target_date,
            "status":      i.status.value,
            "is_overdue":  i.is_overdue,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_modules() -> pd.DataFrame:
    payload = load_payload()
    rows = []
    for m in payload.modules:
        rows.append({
            "id":                     m.id,
            "title":                  m.title,
            "phase_id":               m.phase_id,
            "status":                 m.status.value,
            "standards_mapped":       m.standards_mapped,
            "standards_count":        len(m.standards_mapped),
            "applicable_deliverable": m.applicable_deliverable,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stakeholders (role-filtered)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_stakeholders(user_role: str) -> pd.DataFrame:
    payload = load_payload()
    all_cols = STAKEHOLDER_COLS_BY_ROLE.get(user_role, STAKEHOLDER_COLS_BY_ROLE["oversight"])
    rows = []
    for s in payload.stakeholders:
        row = {
            "id":                  s.id,
            "org_unit":            s.org_unit,
            "contact_name":        s.contact_name,
            "contact_title":       s.contact_title,
            "actor_category":      s.actor_category.value,
            "role":                s.role.value,
            "method":              s.method.value,
            "access_status":       s.access_status.value,
            "consultation_window": s.consultation_window,
            "engagement_score":    s.engagement_score,
        }
        rows.append({k: row[k] for k in all_cols if k in row})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Standards reference
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400)
def fetch_standards() -> pd.DataFrame:
    payload = load_payload()
    rows = []
    for s in payload.standards_reference:
        rows.append({
            "id":       s.id,
            "source":   s.source,
            "standard": s.standard,
            "modules":  ", ".join(s.modules),
            "status":   s.status.value,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_kpis() -> pd.DataFrame:
    payload = load_payload()
    rows = []
    for k in payload.kpis:
        rows.append({
            "id":            k.id,
            "name":          k.name,
            "definition":    k.definition,
            "unit":          k.unit,
            "baseline":      k.baseline,
            "target":        k.target,
            "current_value": k.current_value,
            "trend":         k.trend,
            "trend_delta":   k.trend_delta,
            "pct_to_target": k.pct_to_target,
            "data_source":   k.data_source,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Write helpers — delegate to demo_store or Supabase
# ---------------------------------------------------------------------------

def write_deliverable_update(deliverable_id: str, updates: dict, user: str) -> None:
    fetch_deliverables.clear()
    load_payload.clear()
    if _is_demo():
        from data.demo_store import update_deliverable
        update_deliverable(deliverable_id, updates)
    else:
        client = _get_supabase()
        if client:
            client.table("deliverables").update(updates).eq("id", deliverable_id).execute()


def write_risk_update(risk_id: str, likelihood: int, impact: int, status: str, user: str) -> None:
    fetch_risks.clear()
    load_payload.clear()
    if _is_demo():
        from data.demo_store import update_risk
        update_risk(risk_id, likelihood, impact, status, user)
    else:
        client = _get_supabase()
        if client:
            client.table("risks").update({
                "likelihood": likelihood, "impact": impact, "status": status,
            }).eq("id", risk_id).execute()
            client.table("risk_history").insert({
                "risk_id": risk_id, "likelihood": likelihood,
                "impact": impact, "status": status,
                "date": date.today().isoformat(),
            }).execute()


def write_milestone_complete(milestone_id: str) -> None:
    fetch_milestones.clear()
    load_payload.clear()
    if _is_demo():
        from data.demo_store import complete_milestone
        complete_milestone(milestone_id)
    else:
        client = _get_supabase()
        if client:
            client.table("milestones").update({
                "completed": True,
                "completed_date": date.today().isoformat(),
            }).eq("id", milestone_id).execute()


def write_module_status(module_id: str, status: str) -> None:
    fetch_modules.clear()
    load_payload.clear()
    if _is_demo():
        from data.demo_store import update_module_status
        update_module_status(module_id, status)
    else:
        client = _get_supabase()
        if client:
            client.table("modules").update({"status": status}).eq("id", module_id).execute()


def write_stakeholder_update(stakeholder_id: str, updates: dict) -> None:
    fetch_stakeholders.clear()
    load_payload.clear()
    if _is_demo():
        from data.demo_store import update_stakeholder
        update_stakeholder(stakeholder_id, updates)
    else:
        client = _get_supabase()
        if client:
            client.table("stakeholders").update(updates).eq("id", stakeholder_id).execute()


def write_issue(issue: dict) -> None:
    fetch_issues.clear()
    load_payload.clear()
    if _is_demo():
        from data.demo_store import add_issue
        add_issue(issue)
    else:
        client = _get_supabase()
        if client:
            client.table("issues").insert(issue).execute()


def write_issue_status(issue_id: int, status: str) -> None:
    fetch_issues.clear()
    load_payload.clear()
    if _is_demo():
        from data.demo_store import update_issue_status
        update_issue_status(issue_id, status)
    else:
        client = _get_supabase()
        if client:
            client.table("issues").update({"status": status}).eq("id", issue_id).execute()
