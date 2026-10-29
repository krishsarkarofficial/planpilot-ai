"""Plotly figure builders. Colours follow a validated categorical order."""

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BLUE = "#2a78d6"  # categorical slot 1
ORANGE = "#eb6834"  # categorical slot 2
MUTED = "#898781"


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
        x = pd.Timestamp(deadline)
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
