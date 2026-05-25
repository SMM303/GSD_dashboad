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
    "admin": [
        "id", "org_unit", "contact_name", "contact_title",
        "actor_category", "role", "method",
        "access_status", "consultation_window", "engagement_score",
    ],
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
    value = _secret("DEMO_MODE", os.environ.get("DEMO_MODE", "true"))
    return str(value).lower() in ("true", "1", "yes")


def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


@st.cache_resource
def _get_supabase():
    try:
        from supabase import create_client
        url = _secret("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        key = (
            _secret("SUPABASE_SERVICE_ROLE_KEY")
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
            or _secret("SUPABASE_ANON_KEY")
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


def _clean_display_text(value):
    if not isinstance(value, str):
        return value
    return (
        value
        .replace(" / ", " to ")
        .replace("/", " and ")
        .replace("—", "-")
        .replace("–", "-")
        .replace("≤", "<=")
        .replace("≥", ">=")
        .replace("×", "x")
        .replace("·", ",")
    )


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

    raw["phases"] = _merge_rows_by_id(raw.get("phases", []), _fetch_table(client, "phases", "id,name,start_week,end_week,status"))
    raw["milestones"] = _merge_rows_by_id(raw.get("milestones", []), _fetch_table(client, "milestones", "id,description,target_date,completed,completed_date"))

    deliverables = _merge_rows_by_id(raw.get("deliverables", []), _fetch_table(client, "deliverables", "id,name,description,phase_id,due_week,due_date,payment_pct,status,submitted_at,approved_at,reviewer,quality_gate"))
    history_rows = _fetch_table(client, "deliverable_status_history", "deliverable_id,status,changed_at,changed_by")
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

    modules = _merge_rows_by_id(raw.get("modules", []), _fetch_table(client, "modules", "id,title,phase_id,status,applicable_deliverable"))
    standards_rows = _fetch_table(client, "standards_mappings", "module_id,source,standard,status")
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

    stakeholder_rows = _fetch_table(client, "stakeholders", "id,org_unit,contact_name,contact_title,actor_category,role,method,access_status,consultation_window,engagement_score")
    if stakeholder_rows:
        raw["stakeholders"] = stakeholder_rows

    risks = _merge_rows_by_id(raw.get("risks", []), _fetch_table(client, "risks", "id,description,category,likelihood,impact,mitigation,escalation_trigger,status,owner,raised_date"))
    risk_history_rows = _fetch_table(client, "risk_history", "risk_id,date,likelihood,impact,status")
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

    issue_rows = _fetch_table(client, "issues", "id,date_raised,description,category,risk_level,assigned_to,target_date,status")
    if issue_rows:
        raw["issues"] = issue_rows

    snapshots = _fetch_table(client, "kpi_snapshots", "kpi_id,snapshot_date,value")
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


@st.cache_data(ttl=3600)
def get_programme_metadata() -> dict:
    """Return lightweight programme metadata for the home page."""
    with open(_CONFIG_PATH) as f:
        raw = json.load(f)
    programme = raw.get("programme", {})
    reporting_line = programme.get("reporting_line", {})
    return {
        "title": programme.get("title", ""),
        "org": programme.get("org", ""),
        "unit": programme.get("unit", ""),
        "duty_station": programme.get("duty_station", ""),
        "start_date": programme.get("start_date", ""),
        "reporting_direct": reporting_line.get("direct", ""),
        "reporting_overall": reporting_line.get("overall", ""),
    }


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
            "title":                  _clean_display_text(m.title),
            "phase_id":               m.phase_id,
            "status":                 m.status.value,
            "standards_mapped":       [_clean_display_text(item) for item in m.standards_mapped],
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
            "org_unit":            _clean_display_text(s.org_unit),
            "contact_name":        s.contact_name,
            "contact_title":       s.contact_title,
            "actor_category":      s.actor_category.value,
            "role":                s.role.value,
            "method":              s.method.value,
            "access_status":       s.access_status.value,
            "consultation_window": _clean_display_text(s.consultation_window),
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
            "source":   _clean_display_text(s.source),
            "standard": _clean_display_text(s.standard),
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
            "data_source":   _clean_display_text(k.data_source),
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


def clear_programme_cache() -> None:
    load_payload.clear()
    get_programme_metadata.clear()
    fetch_deliverables.clear()
    fetch_milestones.clear()
    fetch_phases.clear()
    fetch_risks.clear()
    fetch_issues.clear()
    fetch_modules.clear()
    fetch_stakeholders.clear()
    fetch_standards.clear()
    fetch_kpis.clear()


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


# ---------------------------------------------------------------------------
# Admin CRUD helpers — require a Supabase connection (not available in demo)
# ---------------------------------------------------------------------------

def _admin_client():
    """Return the Supabase client, or raise AppError if unavailable."""
    from utils.errors import AppError
    client = _get_supabase()
    if not client:
        raise AppError("A Supabase connection is required for data management. Enable production mode.")
    return client


# ── Risks ────────────────────────────────────────────────────────────────────

def write_new_risk(data: dict) -> None:
    """Insert a new risk row. Clears payload cache."""
    client = _admin_client()
    client.table("risks").insert(data).execute()
    fetch_risks.clear()
    load_payload.clear()


#: Fields the admin may edit without touching the risk score or history.
_RISK_DEFINITION_FIELDS = {"description", "category", "mitigation", "escalation_trigger", "owner"}


def write_risk_definition(risk_id: str, updates: dict) -> None:
    """Update descriptive risk fields only.
    likelihood / impact / status are intentionally excluded here —
    those changes must go through write_risk_update (page 3) so history is recorded."""
    safe = {k: v for k, v in updates.items() if k in _RISK_DEFINITION_FIELDS}
    if not safe:
        return
    client = _admin_client()
    client.table("risks").update(safe).eq("id", risk_id).execute()
    fetch_risks.clear()
    load_payload.clear()


def write_risk_close(risk_id: str) -> None:
    """Soft-delete: set risk status to closed. Risks are never hard-deleted."""
    client = _admin_client()
    client.table("risks").update({"status": "closed"}).eq("id", risk_id).execute()
    fetch_risks.clear()
    load_payload.clear()


# ── Deliverables ──────────────────────────────────────────────────────────────

def write_new_deliverable(data: dict) -> None:
    """Insert a new deliverable definition. Clears payload cache."""
    client = _admin_client()
    client.table("deliverables").insert(data).execute()
    fetch_deliverables.clear()
    load_payload.clear()


#: Fields the admin may edit in the definition tab.
#: status / quality_gate changes go through write_deliverable_update (page 4).
_DELIVERABLE_DEFINITION_FIELDS = {"name", "description", "due_date", "due_week", "payment_pct", "reviewer"}


def write_deliverable_definition(deliverable_id: str, updates: dict) -> None:
    """Update definition fields for a deliverable (not status/quality_gate)."""
    safe = {k: v for k, v in updates.items() if k in _DELIVERABLE_DEFINITION_FIELDS}
    if not safe:
        return
    client = _admin_client()
    client.table("deliverables").update(safe).eq("id", deliverable_id).execute()
    fetch_deliverables.clear()
    load_payload.clear()


def write_deliverable_delete(deliverable_id: str) -> None:
    """Hard-delete a deliverable — only permitted when status is not_started."""
    from utils.errors import AppError
    client = _admin_client()
    resp = client.table("deliverables").select("id,status").eq("id", deliverable_id).limit(1).execute()
    rows = resp.data or []
    if not rows:
        raise ValueError(f"Deliverable {deliverable_id!r} not found.")
    if rows[0].get("status", "not_started") != "not_started":
        raise AppError(
            "Only deliverables with status 'Not Started' can be deleted. "
            "Change the status first if you need to remove this record."
        )
    client.table("deliverables").delete().eq("id", deliverable_id).execute()
    fetch_deliverables.clear()
    load_payload.clear()


# ── Stakeholders ──────────────────────────────────────────────────────────────

def write_new_stakeholder(data: dict) -> None:
    """Insert a new stakeholder record."""
    client = _admin_client()
    client.table("stakeholders").insert(data).execute()
    fetch_stakeholders.clear()
    load_payload.clear()


def write_stakeholder_definition(stakeholder_id: str, updates: dict) -> None:
    """Update any stakeholder field (admin has full access)."""
    client = _admin_client()
    client.table("stakeholders").update(updates).eq("id", stakeholder_id).execute()
    fetch_stakeholders.clear()
    load_payload.clear()


def write_stakeholder_delete(stakeholder_id: str) -> None:
    """Hard-delete a stakeholder record."""
    client = _admin_client()
    client.table("stakeholders").delete().eq("id", stakeholder_id).execute()
    fetch_stakeholders.clear()
    load_payload.clear()


# ── Audit log ─────────────────────────────────────────────────────────────────

def fetch_audit_log_admin(
    limit: int = 100,
    user_filter: str = "",
    action_filter: str = "",
) -> pd.DataFrame:
    """
    Fetch audit log rows for the admin viewer.

    In demo mode reads from demo_store.  In production queries Supabase
    directly (bypasses the payload / cache layer).
    """
    empty = pd.DataFrame(columns=["timestamp", "user", "role", "action",
                                   "record_type", "record_id", "session_id"])
    if _is_demo():
        try:
            from data.demo_store import get_audit_log
            rows = get_audit_log() or []
            return pd.DataFrame(rows) if rows else empty
        except Exception:
            return empty

    client = _get_supabase()
    if not client:
        return empty

    try:
        query = (
            client.table("audit_log")
            .select("timestamp,user,role,action,record_type,record_id,session_id")
            .order("timestamp", desc=True)
            .limit(limit)
        )
        if user_filter.strip():
            query = query.eq("user", user_filter.strip())
        if action_filter.strip():
            query = query.ilike("action", f"%{action_filter.strip()}%")
        rows = query.execute().data or []
        return pd.DataFrame(rows) if rows else empty
    except Exception:
        return empty
