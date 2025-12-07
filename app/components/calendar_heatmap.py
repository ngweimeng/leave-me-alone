import streamlit as st
import datetime as _dt
import calendar
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def render_calendar_heatmap(break_days, leave_days, year, holiday_map=None):
    """Render an interactive 12-month calendar grid for year using Plotly.

    Highlights:
    - Weekends: light gray background
    - Public holidays: yellow with holiday name in tooltip
    - Leave days: red with PTO Day label in tooltip

    Args:
        break_days: Iterable of datetime.date objects (all break days)
        leave_days: Iterable of datetime.date objects (allocated leave)
        year: Year to display
        holiday_map: Optional dict {date: holiday_name} for tooltip labels
    """

    # Normalize inputs to sets of date objects
    bd_set = set([_as_date(d) for d in break_days]) if break_days else set()
    ld_set = set([_as_date(d) for d in leave_days]) if leave_days else set()

    # If there are no break days and no leave days, nothing to show
    if not bd_set and not ld_set:
        st.info("No breaks or leave days found to display.")
        return

    st.subheader("📅 Calendar View")

    # Compute public holidays as break_days that are not weekends and not leave
    year_dates = set(
        _dt.date(year, 1, 1) + _dt.timedelta(days=i)
        for i in range((_dt.date(year, 12, 31) - _dt.date(year, 1, 1)).days + 1)
    )
    weekends = set(d for d in year_dates if d.weekday() >= 5)
    ph_set = bd_set - weekends - ld_set

    # Build holiday name mapping if not provided
    if holiday_map is None:
        holiday_map = {}

    # Color mapping: 0=white, 1=weekend, 2=holiday, 3=PTO
    colorscale = [
        [0, "white"],
        [0.33, "#efefef"],  # weekend
        [0.66, "#ffd54f"],  # holiday
        [1, "#ff6b6b"],  # PTO
    ]

    # Create subplots: 4 rows x 3 columns
    fig = make_subplots(
        rows=4,
        cols=3,
        subplot_titles=[calendar.month_name[i] for i in range(1, 13)],
        horizontal_spacing=0.06,
        vertical_spacing=0.10,
        specs=[[{"type": "xy"}] * 3 for _ in range(4)],
    )

    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for month in range(1, 13):
        row = (month - 1) // 3 + 1
        col = (month - 1) % 3 + 1

        month_cal = calendar.monthcalendar(year, month)

        # Prepare matrices for heatmap
        z_vals = []  # Color values
        text_vals = []  # Day numbers
        hover_vals = []  # Hover text
        x_vals = []
        y_vals = []

        # Prepare data for each day
        for week_idx, week in enumerate(month_cal):
            for dow, day in enumerate(week):
                if day == 0:
                    continue

                d = _dt.date(year, month, day)

                # Determine color value and label
                if d in ld_set:
                    z_val = 3
                    label = "PTO Day"
                elif d in ph_set:
                    z_val = 2
                    label = holiday_map.get(d, "Public Holiday")
                elif d.weekday() >= 5:
                    z_val = 1
                    label = "Weekend"
                else:
                    z_val = 0
                    label = "Workday"

                x_vals.append(dow + 0.5)
                y_vals.append(-week_idx - 0.5)
                z_vals.append(z_val)
                text_vals.append(str(day))
                hover_vals.append(f"{d.strftime('%A, %b %d')}<br>{label}")

        # Add single heatmap trace for the entire month
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="markers+text",
                marker=dict(
                    size=50,  # Increased size for better cell coverage
                    color=z_vals,
                    colorscale=colorscale,
                    cmin=0,
                    cmax=3,
                    line=dict(color="lightgray", width=1),
                    symbol="square",
                ),
                text=text_vals,
                textfont=dict(size=11, color="black"),
                hovertext=hover_vals,
                hoverinfo="text",
                showlegend=False,
            ),
            row=row,
            col=col,
        )

        # Update axes for this subplot
        fig.update_xaxes(
            range=[-0.1, 7.1],  # Slightly expanded range for better spacing
            showticklabels=True,
            tickvals=[i + 0.5 for i in range(7)],
            ticktext=weekday_names,
            tickfont=dict(size=9),
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            row=row,
            col=col,
        )

        fig.update_yaxes(
            range=[-len(month_cal) - 0.1, 0.1],  # Adjusted for better fit
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            row=row,
            col=col,
        )

    # Add legend at the top
    legend_y = 1.05  # Increased from 1.02 for more spacing
    legend_items = [
        ("#ff6b6b", "PTO Days"),
        ("#ffd54f", "Public Holidays"),
        ("#efefef", "Weekends"),
    ]

    for i, (color, label_text) in enumerate(legend_items):
        x_pos = 0.25 + i * 0.25
        fig.add_shape(
            type="rect",
            xref="paper",
            yref="paper",
            x0=x_pos,
            y0=legend_y,
            x1=x_pos + 0.02,
            y1=legend_y + 0.015,
            fillcolor=color,
            line=dict(color="gray", width=1),
        )
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=x_pos + 0.03,
            y=legend_y + 0.0075,
            text=label_text,
            showarrow=False,
            font=dict(size=11),
            xanchor="left",
        )

    # Update layout
    fig.update_layout(
        height=1100,  # Increased height for better cell proportions
        showlegend=False,
        hovermode="closest",
        margin=dict(t=80, b=20, l=20, r=20),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _as_date(d):
    """Convert input to a datetime.date if possible."""
    if isinstance(d, _dt.date) and not isinstance(d, _dt.datetime):
        return d
    if isinstance(d, _dt.datetime):
        return d.date()
    try:
        import pandas as pd

        return pd.to_datetime(d).date()
    except Exception:
        return d
