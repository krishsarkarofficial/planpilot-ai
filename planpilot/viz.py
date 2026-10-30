"""Plotly figure builders. Colours follow a validated categorical order."""

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from planpilot.engine.decision import Comparison
from planpilot.engine.montecarlo import SimResult

BLUE = "#2a78d6"  # categorical slot 1
ORANGE = "#eb6834"  # categorical slot 2
AQUA = "#1baf7a"  # categorical slot 3
MUTED = "#898781"
# Status colours (reserved for RAG; always shown with a text label, never colour alone).
STATUS = {"green": "#0ca30c", "amber": "#fab219", "red": "#d03b3b"}
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


BLUE_RAMP = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # sequential, light -> dark


def risk_heatmap(cells: dict[tuple[int, int], list[str]], labels: list[str]) -> go.Figure:
    """5x5 probability x impact matrix; colour = score (P x I), text = risk ids in the cell."""
    levels = range(1, 6)
    z = [[p * i for i in levels] for p in levels]
    text = [[", ".join(cells.get((p, i), [])) for i in levels] for p in levels]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=labels,
            y=labels,
            text=text,
            colorscale=[[k / 4, c] for k, c in enumerate(BLUE_RAMP)],
            zmin=1,
            zmax=25,
            xgap=2,
            ygap=2,
            colorbar={"title": "Score"},
            hovertemplate="Probability %{y} · impact %{x}<br>Score %{z}<br>%{text}<extra></extra>",
        )
    )
    for p in levels:
        for i in levels:
            ids = cells.get((p, i), [])
            if ids:
                lines = [" ".join(ids[k : k + 2]) for k in range(0, len(ids), 2)]  # 2 per line
                fig.add_annotation(
                    x=labels[i - 1],
                    y=labels[p - 1],
                    text="<br>".join(lines),
                    showarrow=False,
                    font={"color": "#ffffff" if p * i >= 8 else "#0b0b0b", "size": 13},
                )
    fig.update_layout(
        height=430,
        margin=MARGIN,
        xaxis={"title": "Impact (delay if it happens)", "side": "bottom"},
        yaxis={"title": "Probability"},
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


def index_gauge(value: float, title: str, green: float, amber: float) -> go.Figure:
    """SPI or CPI gauge with red / amber / green bands at the RAG thresholds."""
    lo, hi = min(0.5, value - 0.05), max(1.3, value + 0.05)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"valueformat": ".2f"},  # theme ink, readable in light and dark
            title={"text": title},
            gauge={
                "axis": {"range": [lo, hi], "tickformat": ".2f"},
                "bar": {"color": MUTED, "thickness": 0.25},
                "steps": [
                    {"range": [lo, amber], "color": STATUS["red"]},
                    {"range": [amber, green], "color": STATUS["amber"]},
                    {"range": [green, hi], "color": STATUS["green"]},
                ],
                "threshold": {"line": {"color": MUTED, "width": 2}, "value": 1.0},
            },
        )
    )
    fig.update_layout(height=230, margin={"l": 30, "r": 30, "t": 50, "b": 10})
    return fig


def evm_curves(planned: pd.DataFrame, series: pd.DataFrame, bac: float) -> go.Figure:
    """PV over the whole plan; EV and AC up to the status date (INR lakh, one axis)."""
    fig = go.Figure()
    lines = (
        ("Planned value (PV)", planned, "pv", BLUE),
        ("Earned value (EV)", series, "ev", ORANGE),
        ("Actual cost (AC)", series, "ac", AQUA),
    )
    for name, df, col, color in lines:
        y = df[col] / 1e5
        fig.add_trace(
            go.Scatter(
                x=df["week"],
                y=y,
                name=name,
                mode="lines+markers",
                line={"color": color, "width": 2},
                marker={"size": 8},
                hovertemplate=f"{name}<br>Week %{{x}}: ₹%{{y:.2f}} lakh<extra></extra>",
            )
        )
        fig.add_annotation(  # direct label at the line end
            x=df["week"].iloc[-1],
            y=y.iloc[-1],
            text=col.upper(),
            showarrow=False,
            xanchor="left",
            xshift=8,
            font={"color": MUTED},
        )
    fig.add_hline(
        y=bac / 1e5,
        line={"color": MUTED, "width": 1, "dash": "dash"},
        annotation_text=f"BAC ₹{bac / 1e5:.2f} lakh",
        annotation_position="top left",
        annotation_font_color=MUTED,
    )
    as_of = int(series["week"].iloc[-1])
    _vline(fig, as_of, f"Status date (week {as_of})", MUTED, 1.0, "dot")
    fig.update_layout(
        height=430,
        margin={**MARGIN, "t": 60},
        legend={"orientation": "h", "y": -0.18, "x": 0},
        xaxis={"title": "Week", "dtick": 1},
        yaxis={"title": "₹ lakh (cumulative)", "rangemode": "tozero"},
    )
    return fig


def _alternative_colours(names: list[str]) -> dict[str, str]:
    """Baseline grey, the options in categorical order."""
    palette = [BLUE, ORANGE, AQUA]
    return {n: MUTED if i == 0 else palette[(i - 1) % len(palette)] for i, n in enumerate(names)}


def option_scurves(comparison: Comparison) -> go.Figure:
    """S-curve of every alternative (same random draws); a dot marks each one's own deadline."""
    names = list(comparison.metrics.index)
    colours = _alternative_colours(names)
    qs = np.linspace(0, 100, 201)
    fig = go.Figure()
    for r in comparison.results:
        fig.add_trace(
            go.Scatter(
                x=np.percentile(r.sim.durations, qs),
                y=qs / 100,
                name=r.name,
                mode="lines",
                line={"color": colours[r.name], "width": 3 if r.name == names[0] else 2},
                hovertemplate=r.name + "<br>Within %{x:.1f} working days: %{y:.0%}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[r.sim.deadline_days],
                y=[r.sim.prob_on_time],
                name=f"{r.name}: deadline",
                showlegend=False,
                mode="markers+text",
                text=[f"{r.sim.prob_on_time:.0%}"],
                textposition="middle left",
                textfont={"color": colours[r.name]},
                marker={"color": colours[r.name], "size": 10},
                hovertemplate=r.name + "<br>P(on time) %{y:.0%}<extra></extra>",
            )
        )
    fig.update_layout(
        height=430,
        margin={**MARGIN, "t": 20},
        legend={"orientation": "h", "y": -0.2, "x": 0},
        xaxis_title="Project duration (working days)",
        yaxis={"title": "Probability of finishing", "tickformat": ".0%", "range": [0, 1.02]},
    )
    return fig


def scenario_scores(comparison: Comparison) -> go.Figure:
    """Weighted score (0-1, higher is better) of each alternative under each weight scenario."""
    names = list(comparison.metrics.index)
    colours = _alternative_colours(names)
    fig = go.Figure()
    for name in names:
        fig.add_trace(
            go.Bar(
                name=name,
                x=list(comparison.scores),
                y=[float(comparison.scores[s][name]) for s in comparison.scores],
                marker={"color": colours[name]},
                text=[f"{comparison.scores[s][name]:.2f}" for s in comparison.scores],
                textposition="outside",
                hovertemplate=name + "<br>%{x}: %{y:.2f}<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="group",
        height=430,
        margin={**MARGIN, "t": 20},
        legend={"orientation": "h", "y": -0.2, "x": 0},
        xaxis_title="Weight scenario",
        yaxis={"title": "Weighted score (1 = best)", "range": [0, 1.1]},
    )
    return fig


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
