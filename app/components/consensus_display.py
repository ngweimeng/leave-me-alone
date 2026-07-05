"""Render the outcome of a household consensus (CPP) run."""

from datetime import date

import pandas as pd
import streamlit as st

from app.components.calendar_heatmap import render_calendar_heatmap
from app.services.consensus_service import ConsensusResult

_TOGETHER_COLOR = "#66bb6a"


def show_consensus(result: ConsensusResult) -> None:
    """Display togetherness gain, the shared-day calendar, and per-member detail."""
    st.subheader("👨‍👩‍👧 Household Coordination Result")

    # Headline metrics: the whole point is the gain over going solo.
    c1, c2, c3 = st.columns(3)
    c1.metric("Days off together", result.togetherness)
    c2.metric(
        "If everyone booked solo",
        result.baseline_togetherness,
        help="Shared days if each person optimized independently, ignoring the "
        "others.",
    )
    c3.metric(
        "Extra days from coordinating",
        f"+{result.gain}",
        delta=result.gain,
    )

    if result.gain > 0:
        st.success(
            f"Coordinating PTO buys the household **{result.gain} more day(s) "
            "off together** than everyone optimizing alone — no one revealed "
            "their budget or calendar to anyone else."
        )
    else:
        st.info(
            "Coordination couldn't improve on independent planning here — the "
            "household's fixed weekends/holidays already overlap as much as the "
            "budgets allow. Try more PTO or a longer horizon."
        )

    conv = "converged" if result.converged else f"stopped at cap ({result.iterations})"
    st.caption(
        f"Consensus Planning Protocol · {result.iterations} coordinator round(s) "
        f"· {conv} · best-observed plan kept."
    )

    # Shared-days calendar (green overlay on the year of the horizon).
    shared = result.shared_off_days
    if shared:
        year = shared[0].year
        # Union of everyone's breaks so the calendar shows full context, with
        # the "off together" intersection highlighted on top.
        all_breaks: set[date] = set()
        all_leave: set[date] = set()
        for m in result.members:
            all_breaks |= m.break_days
            all_leave |= set(m.leave_days)
        st.markdown("#### 📅 When you're all off together")
        render_calendar_heatmap(
            break_days=sorted(all_breaks),
            leave_days=sorted(all_leave),
            year=year,
            highlight=shared,
            highlight_color=_TOGETHER_COLOR,
            highlight_label="Off Together",
            show_subheader=False,
        )

    # Per-member breakdown.
    st.markdown("#### Per-person plan")
    shared_set = set(shared)
    rows = []
    for m in result.members:
        leave = m.leave_days
        rows.append(
            {
                "Name": m.name,
                "PTO used": len(leave),
                "Total break days": len(m.break_days),
                "Shared with household": len(m.break_days & shared_set),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    with st.expander("Shared off-days (full list)"):
        st.write(", ".join(f"{d:%a %b %d}" for d in shared) or "None")
