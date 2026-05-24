-- ============================================================
-- GSD Dashboard — Supabase schema
-- Run in the Supabase SQL editor when DEMO_MODE = false.
-- All tables have RLS enabled.  Policies are at the bottom.
-- ============================================================

-- Enable pgcrypto for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── phases ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS phases (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  start_week INT  NOT NULL,
  end_week   INT  NOT NULL,
  status     TEXT NOT NULL DEFAULT 'not_started'
             CHECK (status IN ('not_started','in_progress','complete'))
);

-- ── milestones ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS milestones (
  id             TEXT PRIMARY KEY,
  description    TEXT NOT NULL,
  target_date    DATE NOT NULL,
  completed      BOOLEAN NOT NULL DEFAULT FALSE,
  completed_date DATE
);

-- ── deliverables ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deliverables (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  description   TEXT,
  phase_id      TEXT REFERENCES phases(id),
  due_week      INT  NOT NULL,
  due_date      DATE NOT NULL,
  payment_pct   NUMERIC(5,2) NOT NULL DEFAULT 0,
  status        TEXT NOT NULL DEFAULT 'not_started'
                CHECK (status IN ('not_started','in_progress','submitted','under_review','approved','rejected')),
  submitted_at  DATE,
  approved_at   DATE,
  reviewer      TEXT,
  quality_gate  TEXT NOT NULL DEFAULT 'draft'
                CHECK (quality_gate IN ('draft','internal_review','iom_review','approved'))
);

CREATE TABLE IF NOT EXISTS deliverable_status_history (
  id             BIGSERIAL PRIMARY KEY,
  deliverable_id TEXT REFERENCES deliverables(id),
  status         TEXT NOT NULL,
  changed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  changed_by     TEXT NOT NULL
);

-- ── modules ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS modules (
  id                     TEXT PRIMARY KEY,
  title                  TEXT NOT NULL,
  phase_id               TEXT REFERENCES phases(id),
  status                 TEXT NOT NULL DEFAULT 'not_started'
                         CHECK (status IN ('not_started','outline_complete','draft_complete','standards_aligned','finalized')),
  applicable_deliverable TEXT REFERENCES deliverables(id)
);

CREATE TABLE IF NOT EXISTS standards_mappings (
  id          BIGSERIAL PRIMARY KEY,
  module_id   TEXT REFERENCES modules(id),
  source      TEXT NOT NULL,
  standard    TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'mapped'
              CHECK (status IN ('pending','mapped','validated'))
);

-- ── stakeholders ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stakeholders (
  id                  TEXT PRIMARY KEY,
  org_unit            TEXT NOT NULL,
  contact_name        TEXT,          -- PII: visible to implementation role only
  contact_title       TEXT,          -- PII: visible to implementation role only
  actor_category      TEXT NOT NULL,
  role                TEXT NOT NULL,
  method              TEXT NOT NULL,
  access_status       TEXT NOT NULL DEFAULT 'to_be_requested'
                      CHECK (access_status IN ('confirmed','pending','to_be_requested')),
  consultation_window TEXT,
  engagement_score    NUMERIC(4,2) CHECK (engagement_score BETWEEN 0 AND 10)
);

-- ── risks ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risks (
  id                 TEXT PRIMARY KEY,
  description        TEXT NOT NULL,
  category           TEXT NOT NULL CHECK (category IN ('access','coordination','scope','delivery')),
  likelihood         INT  NOT NULL CHECK (likelihood BETWEEN 1 AND 5),
  impact             INT  NOT NULL CHECK (impact     BETWEEN 1 AND 5),
  mitigation         TEXT,
  escalation_trigger TEXT,
  status             TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','mitigated','escalated','closed')),
  owner              TEXT,
  raised_date        DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS risk_history (
  id          BIGSERIAL PRIMARY KEY,
  risk_id     TEXT REFERENCES risks(id),
  date        DATE NOT NULL DEFAULT CURRENT_DATE,
  likelihood  INT  NOT NULL,
  impact      INT  NOT NULL,
  status      TEXT NOT NULL
);

-- ── issues ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS issues (
  id          BIGSERIAL PRIMARY KEY,
  date_raised DATE NOT NULL DEFAULT CURRENT_DATE,
  description TEXT NOT NULL,
  category    TEXT NOT NULL CHECK (category IN ('access','document','coordination','scope')),
  risk_level  TEXT NOT NULL CHECK (risk_level IN ('high','medium','low')),
  assigned_to TEXT,
  target_date DATE,
  status      TEXT NOT NULL DEFAULT 'open'
              CHECK (status IN ('open','resolved','escalated'))
);

-- ── kpi_snapshots ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kpi_snapshots (
  id            BIGSERIAL PRIMARY KEY,
  kpi_id        TEXT NOT NULL,
  snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
  value         NUMERIC NOT NULL,
  UNIQUE (kpi_id, snapshot_date)
);

-- ── audit_log ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  id          BIGSERIAL PRIMARY KEY,
  "user"      TEXT NOT NULL,
  role        TEXT NOT NULL,
  action      TEXT NOT NULL,
  record_type TEXT NOT NULL,
  record_id   TEXT,
  session_id  TEXT,
  timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── etl_sync_log ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS etl_sync_log (
  id         BIGSERIAL PRIMARY KEY,
  table_name TEXT NOT NULL,
  synced_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  rows_upserted INT DEFAULT 0
);

-- ============================================================
-- Row Level Security policies
-- ============================================================

ALTER TABLE deliverables           ENABLE ROW LEVEL SECURITY;
ALTER TABLE milestones             ENABLE ROW LEVEL SECURITY;
ALTER TABLE phases                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE modules                ENABLE ROW LEVEL SECURITY;
ALTER TABLE standards_mappings     ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakeholders           ENABLE ROW LEVEL SECURITY;
ALTER TABLE risks                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_history           ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE kpi_snapshots          ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log              ENABLE ROW LEVEL SECURITY;
ALTER TABLE etl_sync_log           ENABLE ROW LEVEL SECURITY;

-- All roles: read phases, milestones, modules, risks, kpi_snapshots, etl_sync_log
CREATE POLICY "phases_read_all"        ON phases           FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "milestones_read_all"    ON milestones       FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "modules_read_all"       ON modules          FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "risks_read_all"         ON risks            FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "risk_history_read_all"  ON risk_history     FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "kpi_read_all"           ON kpi_snapshots    FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "etl_sync_read_all"      ON etl_sync_log     FOR SELECT USING (auth.role() = 'authenticated');

-- Deliverables: all roles read
CREATE POLICY "deliverables_read_all"  ON deliverables     FOR SELECT USING (auth.role() = 'authenticated');

-- Stakeholders: all roles read (column filtering done in application layer)
CREATE POLICY "stakeholders_read_all"  ON stakeholders     FOR SELECT USING (auth.role() = 'authenticated');

-- Issues: implementation sees all; oversight sees high-risk only; executive sees none (uses summary view)
CREATE POLICY "issues_implementation"  ON issues FOR SELECT
  USING ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');
CREATE POLICY "issues_oversight_high"  ON issues FOR SELECT
  USING (
    (auth.jwt()->'user_metadata'->>'dashboard_role') = 'oversight'
    AND risk_level = 'high'
  );

-- Audit log: implementation role reads (IBG PM); all authenticated roles can insert
CREATE POLICY "audit_log_insert"       ON audit_log FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "audit_log_read_impl"    ON audit_log FOR SELECT
  USING ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');

-- Write policies: implementation role only
CREATE POLICY "deliverables_update_impl" ON deliverables FOR UPDATE
  USING ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');
CREATE POLICY "milestones_update_impl"   ON milestones   FOR UPDATE
  USING ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');
CREATE POLICY "risks_update_impl"        ON risks        FOR UPDATE
  USING ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');
CREATE POLICY "risk_history_insert_impl" ON risk_history FOR INSERT
  WITH CHECK ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');
CREATE POLICY "modules_update_impl"      ON modules      FOR UPDATE
  USING ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');
CREATE POLICY "stakeholders_update_impl" ON stakeholders FOR UPDATE
  USING ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');
CREATE POLICY "issues_insert_impl"       ON issues       FOR INSERT
  WITH CHECK ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');
CREATE POLICY "issues_update_impl"       ON issues       FOR UPDATE
  USING ((auth.jwt()->'user_metadata'->>'dashboard_role') = 'implementation');

-- ── Convenience view for Executive issue summary ────────────────────────
CREATE OR REPLACE VIEW issues_summary AS
  SELECT category, risk_level, status, COUNT(*) AS count
  FROM issues
  GROUP BY category, risk_level, status;

-- ============================================================
-- API privileges
-- ============================================================
-- RLS policies decide which rows each role may access, but Postgres still
-- requires table-level privileges for the Supabase API roles.

GRANT USAGE ON SCHEMA public TO authenticated, service_role;

GRANT SELECT ON
  phases,
  milestones,
  deliverables,
  deliverable_status_history,
  modules,
  standards_mappings,
  stakeholders,
  risks,
  risk_history,
  issues,
  kpi_snapshots,
  audit_log,
  etl_sync_log,
  issues_summary
TO authenticated, service_role;

GRANT UPDATE ON
  milestones,
  deliverables,
  modules,
  stakeholders,
  risks,
  issues
TO authenticated, service_role;

GRANT INSERT ON
  risk_history,
  issues,
  audit_log,
  kpi_snapshots,
  etl_sync_log
TO authenticated, service_role;

GRANT INSERT, UPDATE, DELETE ON
  phases,
  milestones,
  deliverables,
  deliverable_status_history,
  modules,
  standards_mappings,
  stakeholders,
  risks,
  risk_history,
  issues,
  kpi_snapshots,
  audit_log,
  etl_sync_log
TO service_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role;
