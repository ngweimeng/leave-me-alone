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

    # Create subplots: 4 rows x 3 columns
    fig = make_subplots(
        rows=4,
        cols=3,
        subplot_titles=[calendar.month_name[i] for i in range(1, 13)],
        horizontal_spacing=0.05,
        vertical_spacing=0.08,
        specs=[[{"type": "xy"}] * 3 for _ in range(4)],
    )

    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for month in range(1, 13):
        row = (month - 1) // 3 + 1
        col = (month - 1) % 3 + 1

        month_cal = calendar.monthcalendar(year, month)

        # Prepare data for heatmap
        for week_idx, week in enumerate(month_cal):
            for dow, day in enumerate(week):
                if day == 0:
                    continue

                d = _dt.date(year, month, day)

                # Determine color and label
                if d in ld_set:
                    color = "#ff6b6b"
                    label = "PTO Day"
                    text_color = "white"
                elif d in ph_set:
                    color = "#ffd54f"
                    label = holiday_map.get(d, "Public Holiday")
                    text_color = "black"
                elif d.weekday() >= 5:
                    color = "#efefef"
                    label = "Weekend"
                    text_color = "gray"
                else:
                    color = "white"
                    label = "Workday"
                    text_color = "black"

                # Add rectangle
                fig.add_shape(
                    type="rect",
                    x0=dow,
                    y0=-week_idx - 1,
                    x1=dow + 1,
                    y1=-week_idx,
                    fillcolor=color,
                    line=dict(color="lightgray", width=1),
                    row=row,
                    col=col,
                )

                # Add invisible scatter point for hover
                hover_text = f"{d.strftime('%A, %B %d, %Y')}<br>{label}"
                fig.add_trace(
                    go.Scatter(
                        x=[dow + 0.5],
                        y=[-week_idx - 0.5],
                        mode="markers",
                        marker=dict(size=20, opacity=0),  # Invisible but hoverable
                        hovertext=hover_text,
                        hoverinfo="text",
                        showlegend=False,
                    ),
                    row=row,
                    col=col,
                )

                # Add day number as annotation (always visible)
                fig.add_annotation(
                    x=dow + 0.5,
                    y=-week_idx - 0.5,
                    text=str(day),
                    showarrow=False,
                    font=dict(size=10, color=text_color),
                    xref=f"x{(row - 1) * 3 + col}" if row > 1 or col > 1 else "x",
                    yref=f"y{(row - 1) * 3 + col}" if row > 1 or col > 1 else "y",
                )

        # Update axes for this subplot
        fig.update_xaxes(
            range=[0, 7],
            showticklabels=True,
            tickvals=[i + 0.5 for i in range(7)],
            ticktext=weekday_names,
            tickfont=dict(size=8),
            showgrid=False,
            zeroline=False,
            row=row,
            col=col,
        )

        fig.update_yaxes(
            range=[-len(month_cal), 1],
            showticklabels=False,
            showgrid=False,
            zeroline=False,
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
        height=1000,
        showlegend=False,
        hovermode="closest",
        margin=dict(t=80, b=20, l=20, r=20),  # Reduced top margin since no title
    )

    st.plotly_chart(fig, use_container_width=True)


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
