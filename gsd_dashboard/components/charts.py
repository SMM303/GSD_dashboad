"""
Shared Plotly chart builders — called from the five page modules.
All charts use the luxury palette defined in branding.py.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.figure_factory as ff

# ── Palette ────────────────────────────────────────────────────────────────
BLUE_DARK  = "#1B3A6B"
BLUE_MID   = "#2D5A9E"
BLUE_LIGHT = "#93B4D9"
GOLD       = "#C9A84C"
GREEN      = "#10b981"
AMBER      = "#f59e0b"
RED        = "#ef4444"
PURPLE     = "#8b5cf6"
GREY       = "#9ca3af"
BG         = "#F8F6F1"
GRID       = "#E5E2DB"

PHASE_COLOURS = {
    "not_started": GREY,
    "in_progress": BLUE_DARK,
    "complete":    GREEN,
}

STATUS_COLOURS = {
    "not_started": GREY,
    "in_progress": BLUE_MID,
    "submitted":   AMBER,
    "under_review": PURPLE,
    "approved":    GREEN,
    "rejected":    RED,
}

RISK_CAT_COLOURS = {
    "access":       RED,
    "coordination": AMBER,
    "scope":        PURPLE,
    "delivery":     BLUE_MID,
}

RISK_STATUS_SYMBOLS = {
    "active":    "circle",
    "mitigated": "square",
    "escalated": "x",
    "closed":    "diamond",
}


# ── Base layout ─────────────────────────────────────────────────────────────

def _base_layout(**overrides) -> dict:
    defaults = dict(
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(family="Inter, sans-serif", color="#1A1A1A", size=12),
        title_font=dict(family="Playfair Display, serif", size=20, color=BLUE_DARK),
        margin=dict(l=16, r=16, t=52, b=16),
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
    )
    defaults.update(overrides)
    return defaults


def _add_today_marker(fig: go.Figure, annotation_position: str = "top right") -> None:
    """Add today's vertical marker without Plotly's Timestamp annotation helper."""
    today = date.today().isoformat()
    fig.add_shape(
        type="line",
        x0=today,
        x1=today,
        y0=0,
        y1=1,
        xref="x",
        yref="paper",
        line=dict(dash="dash", color=GOLD, width=1.5),
    )
    xanchor = "left" if annotation_position.endswith("right") else "right"
    fig.add_annotation(
        x=today,
        y=1,
        xref="x",
        yref="paper",
        text="Today",
        showarrow=False,
        font=dict(color=GOLD),
        xanchor=xanchor,
        yanchor="bottom",
    )


# ── Programme Timeline Gantt ─────────────────────────────────────────────────

def build_timeline_figure(
    phases_df:     pd.DataFrame,
    deliverables_df: pd.DataFrame,
    milestones_df: pd.DataFrame,
    programme_start: date,
) -> go.Figure:
    fig = go.Figure()

    # Phase bands
    for _, p in phases_df.iterrows():
        colour = PHASE_COLOURS.get(p["status"], GREY)
        fig.add_trace(go.Bar(
            name=p["name"],
            x=[(pd.Timestamp(p["abs_end"]) - pd.Timestamp(p["abs_start"])).days],
            y=[p["name"]],
            base=[pd.Timestamp(p["abs_start"]).timestamp() * 1000],
            orientation="h",
            marker=dict(color=colour, opacity=0.85, line=dict(width=0)),
            text=p["name"],
            textposition="inside",
            insidetextanchor="middle",
            hovertemplate=f"<b>{p['name']}</b><br>Status: {p['status']}<br>Weeks {p['start_week']} to {p['end_week']}<extra></extra>",
            showlegend=False,
        ))

    # Deliverable markers
    for _, d in deliverables_df.iterrows():
        colour = STATUS_COLOURS.get(d["status"], GREY)
        y_pos  = _phase_name(d["phase_id"], phases_df)
        fig.add_trace(go.Scatter(
            x=[pd.Timestamp(d["due_date"])],
            y=[y_pos],
            mode="markers+text",
            marker=dict(symbol="diamond", size=14, color=colour,
                        line=dict(color="white", width=1.5)),
            text=d["id"],
            textposition="top center",
            name=d["name"],
            hovertemplate=(
                f"<b>{d['name']}</b><br>"
                f"Due: {d['due_date']}<br>"
                f"Status: {d['status']}<br>"
                f"Payment: {d['payment_pct']:.0f}%<extra></extra>"
            ),
            showlegend=False,
        ))

    # Milestone circles
    completed_ms   = milestones_df[milestones_df["completed"]]
    outstanding_ms = milestones_df[~milestones_df["completed"]]

    def _add_milestones(ms_df: pd.DataFrame, colour: str, symbol: str, label: str):
        if ms_df.empty:
            return
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(ms_df["target_date"]),
            y=["Milestones"] * len(ms_df),
            mode="markers",
            marker=dict(symbol=symbol, size=10, color=colour,
                        line=dict(color="white", width=1)),
            text=ms_df["description"],
            hovertemplate="<b>%{text}</b><br>Target: %{x|%d %b %Y}<extra></extra>",
            name=label,
        ))

    _add_milestones(completed_ms,   GREEN, "circle", "Milestone complete")
    _add_milestones(outstanding_ms, GREY,  "circle-open", "Milestone pending")

    # Today line
    _add_today_marker(fig, annotation_position="top right")

    # Axes
    prog_end = programme_start + timedelta(days=120)
    fig.update_xaxes(
        range=[pd.Timestamp(programme_start - timedelta(days=3)),
               pd.Timestamp(prog_end + timedelta(days=3))],
        gridcolor=GRID, tickformat="%d %b", tickangle=-30,
    )
    fig.update_yaxes(gridcolor=GRID, autorange="reversed")
    fig.update_layout(
        **_base_layout(title="Programme Timeline", height=380, barmode="overlay"),
    )
    return fig


def _phase_name(phase_id: str, phases_df: pd.DataFrame) -> str:
    row = phases_df[phases_df["id"] == phase_id]
    return row["name"].iloc[0] if not row.empty else phase_id


# ── Risk Heat Map ────────────────────────────────────────────────────────────

def build_risk_heatmap(risks_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    # Background zone shading
    zones = [
        (0.5, 0.5, 2.5, 2.5, "rgba(16,185,129,0.07)"),   # low
        (0.5, 2.5, 5.5, 4.5, "rgba(245,158,11,0.07)"),    # medium
        (2.5, 0.5, 5.5, 2.5, "rgba(245,158,11,0.07)"),    # medium
        (3.5, 3.5, 5.5, 5.5, "rgba(239,68,68,0.10)"),     # high
    ]
    for x0, y0, x1, y1, fill in zones:
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                      fillcolor=fill, line_width=0, layer="below")

    # Risk history trajectories (grey lines)
    for _, row in risks_df.iterrows():
        history = row.get("history", [])
        if isinstance(history, list) and len(history) > 1:
            hist_x = [h["impact"]     for h in history]
            hist_y = [h["likelihood"] for h in history]
            fig.add_trace(go.Scatter(
                x=hist_x, y=hist_y,
                mode="lines",
                line=dict(color=GREY, width=1, dash="dot"),
                showlegend=False,
                hoverinfo="skip",
            ))

    # Current risk positions
    for _, row in risks_df.iterrows():
        colour = RISK_CAT_COLOURS.get(row["category"], GREY)
        symbol = RISK_STATUS_SYMBOLS.get(row["status"], "circle")
        fig.add_trace(go.Scatter(
            x=[row["impact"]],
            y=[row["likelihood"]],
            mode="markers+text",
            marker=dict(size=22, color=colour, symbol=symbol, opacity=0.88,
                        line=dict(width=1.5, color="white")),
            text=row["id"],
            textposition="top center",
            textfont=dict(size=11, color="#1A1A1A"),
            name=row["id"],
            hovertemplate=(
                f"<b>{row['id']}</b><br>"
                f"{row['description']}<br><br>"
                f"Likelihood: {row['likelihood']}  Impact: {row['impact']}<br>"
                f"Score: {row['risk_score']}<br>"
                f"Status: {row['status']}<br>"
                f"Owner: {row['owner']}<br><br>"
                f"<i>Mitigation: {str(row['mitigation'])[:100]}...</i>"
                "<extra></extra>"
            ),
            showlegend=False,
        ))

    tick_labels = ["", "Rare", "Unlikely", "Possible", "Likely", "Almost Certain"]
    fig.update_xaxes(
        title="Impact", range=[0.5, 5.5], tickvals=list(range(6)),
        ticktext=["", "Negligible", "Minor", "Moderate", "Significant", "Critical"],
        gridcolor=GRID,
    )
    fig.update_yaxes(
        title="Likelihood", range=[0.5, 5.5], tickvals=list(range(6)),
        ticktext=tick_labels, gridcolor=GRID,
    )

    # Legend entries for categories
    for cat, col in RISK_CAT_COLOURS.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=col, symbol="circle"),
            name=cat.title(), showlegend=True,
        ))

    fig.update_layout(
        **_base_layout(
            title="Risk Register - Likelihood and Impact",
            height=500,
            xaxis_title="Impact",
            yaxis_title="Likelihood",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1, bgcolor="rgba(0,0,0,0)",
            ),
        )
    )
    return fig


# ── KPI Sparkline ────────────────────────────────────────────────────────────

def build_sparkline(trend: list, unit: str, target: float) -> go.Figure:
    if not trend:
        fig = go.Figure()
        fig.update_layout(height=80, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor=BG, plot_bgcolor=BG)
        return fig

    try:
        dates  = [t["date"] if isinstance(t, dict) else t.date  for t in trend]
        values = [t["value"] if isinstance(t, dict) else t.value for t in trend]
    except Exception:
        dates, values = [], []

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values,
        mode="lines+markers",
        line=dict(color=BLUE_MID, width=2),
        marker=dict(size=4, color=BLUE_MID),
        hovertemplate="%{x|%d %b}: %{y:.1f}<extra></extra>",
        showlegend=False,
    ))
    # Target line
    fig.add_hline(y=target, line_dash="dash", line_color=GREEN, line_width=1)

    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, range=[
        max(0, min(values) * 0.9 - 1),
        max(values) * 1.1 + 1,
    ])
    fig.update_layout(
        height=80,
        margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor=BG,
        plot_bgcolor=BG,
    )
    return fig


# ── Deliverables Gantt ───────────────────────────────────────────────────────

def build_deliverables_gantt(deliverables_df: pd.DataFrame, programme_start: date) -> go.Figure:
    fig = go.Figure()
    for _, d in deliverables_df.iterrows():
        start_ts = pd.Timestamp(programme_start)
        end_ts   = pd.Timestamp(d["due_date"])
        colour   = STATUS_COLOURS.get(d["status"], GREY)
        width    = max((end_ts - start_ts).days, 1)
        fig.add_trace(go.Bar(
            name=d["name"],
            x=[width],
            y=[d["name"]],
            base=[start_ts.timestamp() * 1000],
            orientation="h",
            marker=dict(color=colour, opacity=0.8, line=dict(width=0)),
            text=f"{d['id']} - {d['status'].replace('_',' ').title()}",
            textposition="inside",
            hovertemplate=(
                f"<b>{d['name']}</b><br>"
                f"Due: {d['due_date']}<br>"
                f"Status: {d['status']}<br>"
                f"Days remaining: {d['days_to_deadline']}<extra></extra>"
            ),
            showlegend=False,
        ))

    # Today line
    _add_today_marker(fig)
    prog_end = programme_start + timedelta(days=120)
    fig.update_xaxes(
        range=[pd.Timestamp(programme_start - timedelta(days=2)),
               pd.Timestamp(prog_end + timedelta(days=2))],
        gridcolor=GRID, tickformat="%d %b", tickangle=-30,
    )
    fig.update_yaxes(gridcolor=GRID, autorange="reversed")
    fig.update_layout(**_base_layout(title="Deliverable Schedule", height=260, barmode="overlay"))
    return fig


# ── Standards coverage horizontal bar ───────────────────────────────────────

def build_standards_coverage(modules_df: pd.DataFrame) -> go.Figure:
    status_order = ["not_started", "outline_complete", "draft_complete", "standards_aligned", "finalized"]
    status_col   = {
        "not_started":       GREY,
        "outline_complete":  BLUE_LIGHT,
        "draft_complete":    BLUE_MID,
        "standards_aligned": AMBER,
        "finalized":         GREEN,
    }

    fig = go.Figure()
    for status in status_order:
        subset = modules_df[modules_df["status"] == status]
        if subset.empty:
            continue
        fig.add_trace(go.Bar(
            y=subset["title"].str[:45],
            x=[1] * len(subset),
            name=status.replace("_", " ").title(),
            orientation="h",
            marker=dict(color=status_col.get(status, GREY), opacity=0.85),
            hovertemplate="%{y}<br>Status: " + status.replace("_", " ").title() + "<extra></extra>",
        ))

    fig.update_xaxes(visible=False)
    fig.update_yaxes(gridcolor=GRID, tickfont=dict(size=11))
    fig.update_layout(
        **_base_layout(
            title="Module Status",
            height=380,
            barmode="stack",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        ),
    )
    return fig


# ── Stakeholder engagement radar ─────────────────────────────────────────────

def build_engagement_radar(stakeholders_df: pd.DataFrame) -> go.Figure:
    cat_labels = {
        "GSD_leadership":        "GSD Leadership",
        "GSD_academy":           "GSD Academy",
        "GSD_operational":       "GSD Operations",
        "GSD_legal_it":          "GSD Legal and IT",
        "IOM":                   "IOM",
        "national_partner":      "National Partners",
        "international_partner": "Intl Partners",
    }
    categories = list(cat_labels.keys())
    labels     = [cat_labels[c] for c in categories]

    scores = []
    for cat in categories:
        subset = stakeholders_df[stakeholders_df["actor_category"] == cat]
        if "engagement_score" in subset.columns and not subset["engagement_score"].isna().all():
            scores.append(float(subset["engagement_score"].mean()))
        else:
            # Proxy: confirmed=7, pending=3, to_be_requested=0
            if "access_status" in subset.columns:
                status_map = {"confirmed": 7, "pending": 3, "to_be_requested": 0}
                vals = subset["access_status"].map(status_map).fillna(0)
                scores.append(float(vals.mean()) if not vals.empty else 0.0)
            else:
                scores.append(0.0)

    fig = go.Figure(go.Scatterpolar(
        r=scores + [scores[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor=f"rgba(27,58,107,0.15)",
        line=dict(color=BLUE_DARK, width=2),
        marker=dict(size=6, color=BLUE_DARK),
        hovertemplate="%{theta}: %{r:.1f}<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10], tickfont=dict(size=9), gridcolor=GRID),
            angularaxis=dict(tickfont=dict(size=10)),
            bgcolor=BG,
        ),
        **_base_layout(title="Stakeholder Engagement", height=340),
        showlegend=False,
    )
    return fig
