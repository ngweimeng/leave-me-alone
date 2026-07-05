"""Headless demo of household PTO coordination via CPP.

Run from the repo root:

    python -m app.demos.consensus_demo

Two people share a spring quarter. Alex is in the US with 8 PTO days; Bo is in
the UK with 6. Left alone, each clusters leave against *their own* long
weekends, which rarely line up across two countries. The consensus coordinator
prices days so their time off overlaps — without either revealing their budget
or holiday calendar to the other.
"""

from datetime import date, timedelta

from app.services.consensus_service import Member, coordinate
from app.services.holiday_service import get_public_holiday_map
from app.services.solvers import LeaveProblem


def _quarter(year: int) -> list[date]:
    start, end = date(year, 4, 1), date(year, 6, 30)
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _holidays(country: str, year: int, horizon: list[date]) -> set[date]:
    span = set(horizon)
    return {d for d, _ in get_public_holiday_map(country, year) if d in span}


def main() -> None:
    year = 2025
    horizon = _quarter(year)

    alex = Member(
        name="Alex (US, 8d)",
        problem=LeaveProblem.of(
            horizon,
            _holidays("US", year, horizon),
            leave_available=8,
            adjacency_weight=1.0,
            max_stretch=6,
        ),
    )
    bo = Member(
        name="Bo (UK, 6d)",
        problem=LeaveProblem.of(
            horizon,
            _holidays("GB", year, horizon),
            leave_available=6,
            adjacency_weight=1.0,
            max_stretch=6,
        ),
    )

    result = coordinate([alex, bo], togetherness_bonus=2.0, rho=1.0, max_iters=40)

    print("=" * 64)
    print("Household PTO coordination (Consensus Planning Protocol)")
    print("=" * 64)
    print(
        f"Coordinator rounds : {result.iterations} "
        f"({'converged' if result.converged else 'hit cap'})"
    )
    print(f"Shared off-days history: {result.history}")
    print()
    print(f"Days off TOGETHER, independent : {result.baseline_togetherness}")
    print(f"Days off TOGETHER, coordinated : {result.togetherness}")
    print(f"Gain from coordination         : +{result.gain}")
    print()
    for m in result.members:
        print(
            f"  {m.name}: {len(m.leave_days)} PTO days -> "
            f"{len(m.break_days)} total break days"
        )
    print()
    print("Shared off-days:")
    for d in result.shared_off_days:
        print(f"  {d:%a %Y-%m-%d}")


if __name__ == "__main__":
    main()
