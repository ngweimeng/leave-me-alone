import streamlit as st
import datetime as _dt
import calendar
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import colors


def render_calendar_heatmap(break_days, leave_days, year):
    """Render a simple 12-month calendar grid for `year`.

    Highlights:
    - Weekends: light gray background
    - Public holidays (inferred as break_days that are not weekends or leave): yellow
    - Leave days: red

    The function expects `break_days` and `leave_days` to be iterables of
    `datetime.date` objects (or convertible to them).
    """

    # Normalize inputs to sets of date objects
    bd_set = set([_as_date(d) for d in break_days]) if break_days else set()
    ld_set = set([_as_date(d) for d in leave_days]) if leave_days else set()

    # If there are no break days and no leave days, nothing to show
    if not bd_set and not ld_set:
        st.info("No breaks or leave days found to display.")
        return

    st.subheader("📅 Year Calendar")

    # Compute public holidays as break_days that are not weekends and not leave
    # (This infers PH from break_days; if you have an explicit PH list pass it instead.)
    year_dates = set(_dt.date(year, 1, 1) + _dt.timedelta(days=i) for i in range(( _dt.date(year,12,31) - _dt.date(year,1,1) ).days + 1))
    weekends = set(d for d in year_dates if d.weekday() >= 5)
    ph_set = bd_set - weekends - ld_set

    # Prepare figure: 4 rows x 3 columns of months
    fig = plt.figure(figsize=(14, 10))
    plt.suptitle(f"{year} — Weekends, Public Holidays, and Leave", fontsize=16)

    month_names = [calendar.month_name[i] for i in range(1, 13)]

    for month in range(1, 13):
        ax = fig.add_subplot(4, 3, month)
        ax.set_title(month_names[month - 1], fontsize=10)
        ax.set_xlim(0, 7)

        month_cal = calendar.monthcalendar(year, month)
        nrows = len(month_cal)
        # allow a small top margin for weekday headers
        ax.set_ylim(-nrows, 1)
        ax.axis('off')
        ax.set_aspect('equal')

        # Draw weekday headers above the grid
        for i, wd in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
            ax.text(i + 0.5, 0.6, wd, fontsize=7, ha='center', va='center')

        # Draw cells (week rows top-to-bottom)
        for week_idx, week in enumerate(month_cal):
            for dow, day in enumerate(week):
                if day == 0:
                    continue
                d = _dt.date(year, month, day)

                # Determine background color
                if d in ld_set:
                    face = '#ff6b6b'  # red for leave
                    text_color = 'white'
                elif d in ph_set:
                    face = '#ffd54f'  # yellow for public holiday
                    text_color = 'black'
                elif d.weekday() >= 5:
                    face = '#efefef'  # light gray for weekend
                    text_color = 'black'
                else:
                    face = 'white'
                    text_color = 'black'

                # Rectangle bottom-left at (dow, -week_idx-1), height=1
                rect = mpatches.Rectangle((dow, -week_idx - 1), 1, 1, edgecolor='lightgray', facecolor=face)
                ax.add_patch(rect)

                # Day number centered in cell
                ax.text(dow + 0.5, -week_idx - 0.5, str(day), fontsize=8, ha='center', va='center', color=text_color)

    # Legend
    legend_patches = [
        mpatches.Patch(color='#ff6b6b', label='Leave Days'),
        mpatches.Patch(color='#ffd54f', label='Public Holidays'),
        mpatches.Patch(color='#efefef', label='Weekends'),
    ]
    fig.legend(handles=legend_patches, loc='lower center', ncol=3)

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    st.pyplot(fig)


def _as_date(d):
    """Convert input to a datetime.date if possible."""
    if isinstance(d, _dt.date) and not isinstance(d, _dt.datetime):
        return d
    if isinstance(d, _dt.datetime):
        return d.date()
    # assume pandas Timestamp or string
    try:
        import pandas as pd
        return pd.to_datetime(d).date()
    except Exception:
        return d
