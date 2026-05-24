# GSD Programme Dashboard
**IOM Lebanon / GSD Curriculum Development Consultancy**

A Streamlit application providing five live views — Timeline, Stakeholder Views, Risk Heat Map, Deliverables Tracker, and KPI Dashboard — for the IOM Lebanon / General Directorate of General Security curriculum development programme.

---

## Quick start (demo mode — no external services needed)

```bash
cd gsd_dashboard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` and sign in with one of the demo credentials:

| Username | Password | Role |
|---|---|---|
| `saleh.mansour` | `consultant123` | Implementation |
| `iom.pm` | `pm123` | Implementation (IBG PM) |
| `iom.hoo` | `hoo123` | Executive |
| `iom.oversight` | `oversight123` | Oversight |

All data is read from `data/programme_config.json` and persisted locally to `data/live_data.json`. No Supabase or Google account required in demo mode.

---

## Project structure

```
gsd_dashboard/
├── app.py                     # Entry point — auth + home splash
├── pages/
│   ├── 1_Timeline.py          # Plotly Gantt — phases, milestones, deliverables
│   ├── 2_Stakeholder_Views.py # Stakeholder map, issue log, engagement radar
│   ├── 3_Risk_Heat_Map.py     # 5×5 L×I heat map, risk updates
│   ├── 4_Deliverables.py      # Deliverables grid, module progress, standards table
│   └── 5_KPI_Dashboard.py     # TOR §7 KPIs, sparklines, timeliness detail
├── models/programme.py        # Pydantic v2 models for all data objects
├── data/
│   ├── programme_config.json  # Static programme data (TOR + action plan)
│   ├── live_data.json         # Mutable state (auto-created on first run)
│   ├── demo_store.py          # Demo-mode read/write layer
│   └── queries.py             # Unified data access — demo or Supabase
├── auth/
│   ├── setup.py               # Authentication, role management, login form
│   └── audit.py               # Audit logging (every sensitive view + form submit)
├── components/
│   ├── branding.py            # Luxury CSS injection, badge helpers, sidebar
│   ├── charts.py              # All Plotly chart builders
│   └── freshness.py           # Data freshness badges in sidebar
├── etl/
│   ├── sheets_sync.py         # Google Sheets → Supabase (production)
│   ├── kpi_calculator.py      # Daily KPI snapshot writer (production)
│   └── scheduler.py           # APScheduler cron worker entry point
├── db/migrations.sql          # Supabase schema + RLS policies
├── scripts/generate_hashes.py # Bcrypt password hash generator
├── .streamlit/config.toml     # Luxury theme (IOM blue + warm off-white)
├── .streamlit/secrets.toml.example  # Copy to secrets.toml and fill in
├── Dockerfile
└── fly.toml
```

---

## Production setup (Supabase + Google Sheets)

### 1. Create secrets.toml

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Set `DEMO_MODE = false` and fill in all values.

### 2. Supabase schema

Run `db/migrations.sql` in the Supabase SQL editor.

### 3. Hash passwords

```bash
python scripts/generate_hashes.py
```

Paste the output into `secrets.toml` under `[auth_credentials]`.

### 4. Google Sheets

Create a spreadsheet with tabs: **Issue Log**, **Stakeholder Map**, **Standards Reference**, **Task Tracker**.  
Share it with the service account email from GCP project.

### 5. Deploy to Fly.io

```bash
fly launch --config fly.toml
fly secrets set DEMO_MODE=false \
    SUPABASE_URL="..." \
    SUPABASE_ANON_KEY="..." \
    SUPABASE_SERVICE_ROLE_KEY="..." \
    GOOGLE_SPREADSHEET_ID="..." \
    GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
fly deploy
```

---

## Role access summary

| Feature | Executive | Implementation | Oversight |
|---|---|---|---|
| Timeline | Full | Full | Phases + deliverable milestones |
| Milestone checkboxes | — | Full (editable) | — |
| Stakeholder map | Category summary | Full + PII | Category only |
| Issue log | Count only | Full (editable) | High-risk only |
| Risk heat map | Positions only | Full + update form | Full detail |
| Risk history | — | Full | Full |
| Deliverables grid | Full | Full + update form | Full |
| Module progress | Aggregate % | Full + update form | Full |
| Standards table | — | Full | Full |
| KPI dashboard | Full | Full + audit log | Full |

---

## Data sources (demo mode)

All data traces to the TOR (Annex 2) and action plan documents:

- **Phases**: TOR §3 (three phases, Weeks 1–4, 5–8, 9–10)
- **Deliverables**: TOR §6 (D1–D4b, payment percentages, due dates)
- **Curriculum modules**: TOR §3 Phase 2 (ten modules)
- **Stakeholders**: Action Plan Day 3 (16 actor entries across 7 categories)
- **Risks**: Action Plan Day 1 Risk Flags (three named risks)
- **Standards**: Action Plan Day 2 Standards Reference Table (12 entries)
- **Issues**: Action Plan Day 1 Action 05 (issue log structure)
- **KPIs**: TOR §7 Performance Indicators (three TOR KPIs + two operational)

---

## Reset demo data

To reset `live_data.json` to the original programme_config.json state:

```python
from data.demo_store import reset_to_defaults
reset_to_defaults()
```

Or simply delete `data/live_data.json` and restart the app.
