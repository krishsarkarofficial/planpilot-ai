"""Plotly figure builders. Colours follow a validated categorical order."""

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from planpilot.engine.montecarlo import SimResult

BLUE = "#2a78d6"  # categorical slot 1
ORANGE = "#eb6834"  # categorical slot 2
MUTED = "#898781"
MARGIN = {"l": 10, "r": 10, "t": 40, "b": 10}


def _vline(fig: go.Figure, x: float, label: str, color: str, y: float, dash: str) -> None:
    fig.add_shape(
        type="line",
        x0=x,
        x1=x,
        y0=0,
        y1=max(1, y),  # a label above the plot gets a leader line up to it
        yref="paper",
        line={"color": color, "width": 2, "dash": dash},
    )
    fig.add_annotation(
        x=x,
        y=y,
        yref="paper",
        text=label,
        showarrow=False,
        xanchor="left",
        yanchor="bottom" if y >= 1 else "middle",
        xshift=4,
        font={"color": color},
    )


def duration_histogram(res: SimResult) -> go.Figure:
    """Distribution of project duration with P50/P80/P90 and the deadline."""
    fig = go.Figure(
        go.Histogram(
            x=res.durations,
            xbins={"size": 1},
            marker={"color": BLUE, "line": {"width": 1, "color": "rgba(0,0,0,0)"}},
            hovertemplate="%{x} working days<br>%{y} runs<extra></extra>",
        )
    )
    # Labels sit above the plot, stacked, so close percentiles never collide.
    for q, y in ((50, 1.0), (80, 1.08), (90, 1.16)):
        v = res.percentile(q)
        _vline(fig, v, f"P{q} {v:.1f}", MUTED, y, "dash")
    _vline(fig, res.deadline_days, f"Deadline {res.deadline_days}", ORANGE, 1.24, "solid")
    fig.update_layout(
        bargap=0.08,
        height=430,
        margin={**MARGIN, "t": 110},
        showlegend=False,
        xaxis_title="Project duration (working days)",
        yaxis_title="Runs",
    )
    return fig


def s_curve(res: SimResult) -> go.Figure:
    """Empirical CDF: probability of finishing within x working days."""
    qs = np.linspace(0, 100, 201)
    x = np.percentile(res.durations, qs)
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=qs / 100,
            mode="lines",
            line={"color": BLUE, "width": 2},
            hovertemplate="Within %{x:.1f} working days: %{y:.0%}<extra></extra>",
        )
    )
    _vline(fig, res.deadline_days, f"Deadline: {res.prob_on_time:.0%}", ORANGE, 0.08, "solid")
    fig.add_trace(
        go.Scatter(
            x=[res.deadline_days],
            y=[res.prob_on_time],
            mode="markers",
            marker={"color": ORANGE, "size": 10},
            hovertemplate="P(on time) %{y:.0%}<extra></extra>",
        )
    )
    fig.update_layout(
        height=430,
        margin={**MARGIN, "t": 110},  # matches the histogram beside it
        showlegend=False,
        xaxis_title="Project duration (working days)",
        yaxis={"title": "Probability of finishing", "tickformat": ".0%", "range": [0, 1.02]},
    )
    return fig


def _hbar(labels: list[str], values: list[float], fmt: str, x_title: str) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": BLUE},
            hovertemplate="%{y}<br>%{x:" + fmt + "}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(300, 26 * len(labels) + 80),
        margin=MARGIN,
        showlegend=False,
        bargap=0.25,
        xaxis={"title": x_title, "tickformat": fmt},
        yaxis={"autorange": "reversed"},
    )
    return fig


def tornado(res: SimResult, names: dict[str, str], top: int = 10) -> go.Figure:
    """Tasks whose duration moves the project duration most (Pearson r)."""
    items = list(res.tornado.items())[:top]  # already sorted by |r|
    return _hbar(
        [f"{tid}  {names[tid]}" for tid, _ in items],
        [r for _, r in items],
        ".2f",
        "Correlation with project duration",
    )


def criticality(res: SimResult, names: dict[str, str]) -> go.Figure:
    """Share of runs in which each task is on the critical path."""
    items = sorted(res.criticality.items(), key=lambda kv: -kv[1])
    return _hbar(
        [f"{tid}  {names[tid]}" for tid, _ in items],
        [c for _, c in items],
        ".0%",
        "Share of runs on the critical path",
    )


def gantt(df: pd.DataFrame, deadline: date | None = None) -> go.Figure:
    """Gantt from `schedule.schedule_frame`, critical tasks highlighted."""
    d = df.sort_values(["es", "id"]).reset_index(drop=True)
    d["label"] = d["id"] + "  " + d["name"]
    d["end"] = d["finish"] + pd.Timedelta(days=1)  # bar covers the whole finish day
    d["path"] = d["critical"].map({True: "Critical", False: "Has slack"})
    fig = px.timeline(
        d,
        x_start="start",
        x_end="end",
        y="label",
        color="path",
        color_discrete_map={"Critical": ORANGE, "Has slack": BLUE},
        category_orders={"label": list(d["label"]), "path": ["Critical", "Has slack"]},
        custom_data=["phase", "role", "m", "slack", "start", "finish"],
    )
    fig.update_traces(
        marker_line_width=0,
        hovertemplate=(
            "<b>%{y}</b><br>%{customdata[0]} · %{customdata[1]}<br>"
            "Most likely %{customdata[2]} d · slack %{customdata[3]} d<br>"
            "%{customdata[4]|%d %b} → %{customdata[5]|%d %b %Y}<extra></extra>"
        ),
    )
    fig.update_yaxes(title=None)
    fig.update_xaxes(title=None)
    if deadline is not None:
        x = pd.Timestamp(deadline) + pd.Timedelta(days=1)  # end of the deadline day
        fig.add_shape(
            type="line",
            x0=x,
            x1=x,
            y0=0,
            y1=1,
            yref="paper",
            line={"color": MUTED, "width": 2, "dash": "dash"},
        )
        fig.add_annotation(
            x=x,
            y=1,
            yref="paper",
            text="Deadline",
            showarrow=False,
            yanchor="bottom",
            font={"color": MUTED},
        )
    fig.update_layout(
        height=max(320, 28 * len(d) + 80),
        bargap=0.25,
        legend={"title": None, "orientation": "h", "y": 1.06, "x": 0},
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    return fig
