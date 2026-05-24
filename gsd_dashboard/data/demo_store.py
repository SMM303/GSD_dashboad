"""
Demo-mode persistence layer.

Reads the initial state from programme_config.json and maintains
a mutable copy in live_data.json for the duration of the demo.
All write operations that would go to Supabase in production
are handled here when DEMO_MODE = true.
"""
from __future__ import annotations

import copy
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

_DATA_DIR  = Path(__file__).parent
_CONFIG    = _DATA_DIR / "programme_config.json"
_LIVE_FILE = _DATA_DIR / "live_data.json"

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    with open(_CONFIG) as f:
        return json.load(f)


def _init_live_data(config: dict) -> dict:
    """Create the mutable live_data structure from the static config."""
    return {
        "phases": [
            {"id": p["id"], "status": p["status"]}
            for p in config["phases"]
        ],
        "milestones": [
            {"id": m["id"], "completed": m["completed"], "completed_date": m["completed_date"]}
            for m in config["milestones"]
        ],
        "deliverables": [
            {
                "id":          d["id"],
                "status":      d["status"],
                "submitted_at": d["submitted_at"],
                "approved_at": d["approved_at"],
                "quality_gate": d["quality_gate"],
                "status_history": d.get("status_history", []),
            }
            for d in config["deliverables"]
        ],
        "modules": [
            {"id": m["id"], "status": m["status"]}
            for m in config["modules"]
        ],
        "stakeholders": [
            {
                "id": s["id"],
                "contact_name":  s.get("contact_name"),
                "contact_title": s.get("contact_title"),
                "access_status": s["access_status"],
                "consultation_window": s.get("consultation_window"),
                "engagement_score":    s.get("engagement_score"),
            }
            for s in config["stakeholders"]
        ],
        "risks": [
            {
                "id":         r["id"],
                "likelihood": r["likelihood"],
                "impact":     r["impact"],
                "status":     r["status"],
                "history":    r.get("history", []),
            }
            for r in config["risks"]
        ],
        "issues": copy.deepcopy(config.get("issues", [])),
        "kpis": [
            {
                "id":            k["id"],
                "current_value": k.get("current_value"),
                "trend":         k.get("trend", []),
            }
            for k in config.get("kpis", [])
        ],
        "kpi_snapshots": [],
        "audit_log": [],
        "etl_sync_log": [
            {"table_name": "issues",        "synced_at": datetime.utcnow().isoformat()},
            {"table_name": "stakeholders",  "synced_at": datetime.utcnow().isoformat()},
            {"table_name": "standards",     "synced_at": datetime.utcnow().isoformat()},
            {"table_name": "kpi_snapshots", "synced_at": datetime.utcnow().isoformat()},
        ],
    }


def _load_or_init() -> dict:
    if _LIVE_FILE.exists():
        with open(_LIVE_FILE) as f:
            return json.load(f)
    config = _load_config()
    live   = _init_live_data(config)
    _save(live)
    return live


def _save(live: dict) -> None:
    with open(_LIVE_FILE, "w") as f:
        json.dump(live, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Public helpers — merge static config with live mutable state
# ---------------------------------------------------------------------------

def get_full_payload() -> dict:
    """Return the merged programme payload ready for Pydantic validation."""
    config = _load_config()
    live   = _load_or_init()

    live_del  = {d["id"]: d for d in live["deliverables"]}
    live_mod  = {m["id"]: m for m in live["modules"]}
    live_ph   = {p["id"]: p for p in live["phases"]}
    live_ms   = {m["id"]: m for m in live["milestones"]}
    live_stk  = {s["id"]: s for s in live["stakeholders"]}
    live_risk = {r["id"]: r for r in live["risks"]}
    live_kpi  = {k["id"]: k for k in live.get("kpis", [])}

    # Merge deliverables
    deliverables = []
    for d in config["deliverables"]:
        merged = copy.deepcopy(d)
        if d["id"] in live_del:
            merged.update(live_del[d["id"]])
        deliverables.append(merged)

    # Merge modules
    modules = []
    for m in config["modules"]:
        merged = copy.deepcopy(m)
        if m["id"] in live_mod:
            merged["status"] = live_mod[m["id"]]["status"]
        modules.append(merged)

    # Merge phases
    phases = []
    for p in config["phases"]:
        merged = copy.deepcopy(p)
        if p["id"] in live_ph:
            merged["status"] = live_ph[p["id"]]["status"]
        phases.append(merged)

    # Merge milestones
    milestones = []
    for m in config["milestones"]:
        merged = copy.deepcopy(m)
        if m["id"] in live_ms:
            merged.update(live_ms[m["id"]])
        milestones.append(merged)

    # Merge stakeholders
    stakeholders = []
    for s in config["stakeholders"]:
        merged = copy.deepcopy(s)
        if s["id"] in live_stk:
            merged.update(live_stk[s["id"]])
        stakeholders.append(merged)

    # Merge risks
    risks = []
    for r in config["risks"]:
        merged = copy.deepcopy(r)
        if r["id"] in live_risk:
            live_r = live_risk[r["id"]]
            merged["likelihood"] = live_r["likelihood"]
            merged["impact"]     = live_r["impact"]
            merged["status"]     = live_r["status"]
            merged["history"]    = live_r.get("history", merged["history"])
        risks.append(merged)

    # Merge KPIs
    kpis = []
    for k in config.get("kpis", []):
        merged = copy.deepcopy(k)
        if k["id"] in live_kpi:
            live_k = live_kpi[k["id"]]
            if live_k.get("current_value") is not None:
                merged["current_value"] = live_k["current_value"]
            if live_k.get("trend"):
                merged["trend"] = live_k["trend"]
        kpis.append(merged)

    return {
        "programme":          config["programme"],
        "phases":             phases,
        "milestones":         milestones,
        "deliverables":       deliverables,
        "modules":            modules,
        "stakeholders":       stakeholders,
        "risks":              risks,
        "standards_reference": config.get("standards_reference", []),
        "issues":             live.get("issues", config.get("issues", [])),
        "kpis":               kpis,
    }


# ---------------------------------------------------------------------------
# Write operations (mirror Supabase table.update / insert)
# ---------------------------------------------------------------------------

def update_deliverable(deliverable_id: str, updates: dict) -> None:
    live = _load_or_init()
    for d in live["deliverables"]:
        if d["id"] == deliverable_id:
            d.update(updates)
            break
    _save(live)


def update_risk(risk_id: str, likelihood: int, impact: int, status: str, changed_by: str) -> None:
    live = _load_or_init()
    today = date.today().isoformat()
    for r in live["risks"]:
        if r["id"] == risk_id:
            r["likelihood"] = likelihood
            r["impact"]     = impact
            r["status"]     = status
            r.setdefault("history", []).append({
                "date":       today,
                "likelihood": likelihood,
                "impact":     impact,
                "status":     status,
            })
            break
    _save(live)


def complete_milestone(milestone_id: str) -> None:
    live = _load_or_init()
    today = date.today().isoformat()
    for m in live["milestones"]:
        if m["id"] == milestone_id:
            m["completed"]      = True
            m["completed_date"] = today
            break
    _save(live)


def update_module_status(module_id: str, status: str) -> None:
    live = _load_or_init()
    for m in live["modules"]:
        if m["id"] == module_id:
            m["status"] = status
            break
    _save(live)


def update_stakeholder(stakeholder_id: str, updates: dict) -> None:
    live = _load_or_init()
    for s in live["stakeholders"]:
        if s["id"] == stakeholder_id:
            s.update(updates)
            break
    _save(live)


def add_issue(issue: dict) -> None:
    live = _load_or_init()
    existing_ids = [i["id"] for i in live.get("issues", [])]
    issue["id"] = max(existing_ids, default=0) + 1
    live.setdefault("issues", []).append(issue)
    _save(live)


def update_issue_status(issue_id: int, status: str) -> None:
    live = _load_or_init()
    for i in live.get("issues", []):
        if i["id"] == issue_id:
            i["status"] = status
            break
    _save(live)


def log_audit(user: str, role: str, action: str, record_type: str, record_id: str, session_id: str) -> None:
    live = _load_or_init()
    live.setdefault("audit_log", []).append({
        "user":        user,
        "role":        role,
        "action":      action,
        "record_type": record_type,
        "record_id":   record_id,
        "session_id":  session_id,
        "timestamp":   datetime.utcnow().isoformat(),
    })
    _save(live)


def get_audit_log() -> list:
    live = _load_or_init()
    return live.get("audit_log", [])


def reset_to_defaults() -> None:
    """Wipe live_data.json and re-initialise from programme_config.json."""
    if _LIVE_FILE.exists():
        _LIVE_FILE.unlink()
    _load_or_init()
