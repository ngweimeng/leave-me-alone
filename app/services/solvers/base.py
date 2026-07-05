"""
Solver abstraction for the leave-optimization MILP.

This is the seam that lets the same problem be solved by different backends
(Xpress, Gurobi, OR-Tools, ...) and compared. The math lives in
``LeaveProblem``; each backend translates it into its own modeling API.

Class roles
-----------
- ``LeaveProblem``  : immutable description of the inputs (the "what").
- ``SolverConfig``  : backend-agnostic tuning knobs (time limit, gap, ...).
- ``LeaveSolution`` : the chosen break/leave days.
- ``SolveStats``    : measured outcome (objective, time, status, counts).
- ``SolveResult``   : solution + stats together.
- ``LeaveSolver``   : abstract base; one concrete subclass per backend.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class LeaveProblem:
    """Immutable description of a leave-optimization problem.

    Attributes:
        date_range: Ordered list of every date in the planning horizon.
        holidays: Dates that are public holidays (weekends are detected
            automatically and need not be included here).
        leave_available: Total PTO budget the solver may allocate.
        adjacency_weight: Bonus per pair of consecutive break days. Higher
            values bias the solution toward longer continuous breaks. Note that
            this is a *threshold* control, not a length dial: any positive value
            clusters maximally. To bound block *length*, use ``max_stretch``.
        prebooked_days: Dates that must be taken as leave (forced to 1).
        max_stretch: Cap on the length of any continuous break created or
            extended by leave (e.g. 4 → at most 4 consecutive break days).
            ``None`` means no cap. Runs forced entirely by weekends/holidays are
            left alone (see :meth:`stretch_windows`).
        day_prices: Optional per-day *price* added to the objective as
            ``Σ_d price_d · break_d``. This is the hook the consensus coordinator
            (see :mod:`app.services.consensus_service`) uses to nudge one person
            toward days off that others in the household also take — a positive
            price rewards being a break on day ``d``, a negative one discourages
            it. Days absent from the mapping have price 0. When empty (the
            default), the objective is unchanged, so ordinary single-person
            solves behave exactly as before.
    """

    date_range: tuple[date, ...]
    holidays: frozenset[date]
    leave_available: int
    adjacency_weight: float = 1.0
    prebooked_days: frozenset[date] = frozenset()
    max_stretch: Optional[int] = None
    day_prices: dict[date, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.date_range:
            raise ValueError("date_range cannot be empty")
        if self.leave_available < 0:
            raise ValueError("leave_available cannot be negative")
        if self.max_stretch is not None and self.max_stretch < 1:
            raise ValueError("max_stretch must be >= 1 when set")

    @classmethod
    def of(
        cls,
        date_range,
        holidays,
        leave_available: int,
        adjacency_weight: float = 1.0,
        prebooked_days=None,
        max_stretch: Optional[int] = None,
        day_prices=None,
    ) -> "LeaveProblem":
        """Build from loose iterables, coercing to the frozen types."""
        return cls(
            date_range=tuple(date_range),
            holidays=frozenset(holidays or ()),
            leave_available=leave_available,
            adjacency_weight=adjacency_weight,
            prebooked_days=frozenset(prebooked_days or ()),
            max_stretch=max_stretch,
            day_prices=dict(day_prices or {}),
        )

    def with_prices(self, day_prices: dict[date, float]) -> "LeaveProblem":
        """Return a copy carrying new consensus day-prices (all else unchanged)."""
        return replace(self, day_prices=dict(day_prices))

    def is_fixed_break(self, d: date) -> bool:
        """True if a date is always a break day (weekend or public holiday)."""
        return d.weekday() >= 5 or d in self.holidays

    def price_of(self, d: date) -> float:
        """Consensus price added to the objective for ``break_d`` (0 if unset)."""
        return self.day_prices.get(d, 0.0)

    @property
    def has_prices(self) -> bool:
        """True if any consensus day-price is set (else the objective is the base)."""
        return bool(self.day_prices)

    def stretch_windows(self) -> list[tuple[int, ...]]:
        """Index windows that must not be entirely break days.

        For a cap of ``K = max_stretch``, every window of ``K + 1`` consecutive
        days is constrained to at most ``K`` break days, which forbids any run
        longer than ``K``. We emit only windows that contain at least one
        non-fixed-break day (a weekday that is not a holiday): a window made
        entirely of weekends/holidays is already all breaks and cannot be
        capped, so constraining it would make the model infeasible. Skipping
        those windows leaves pre-existing forced holiday runs untouched while
        still preventing leave from creating or extending a longer run.
        """
        if not self.max_stretch:
            return []
        k = self.max_stretch
        dr = self.date_range
        n = len(dr)
        windows: list[tuple[int, ...]] = []
        for i in range(0, n - k):
            idxs = tuple(range(i, i + k + 1))
            if any(not self.is_fixed_break(dr[j]) for j in idxs):
                windows.append(idxs)
        return windows

    @property
    def num_variables(self) -> int:
        """Variable count for this horizon (leave + break + adjacency)."""
        n = len(self.date_range)
        return n + n + max(n - 1, 0)


@dataclass(frozen=True)
class SolverConfig:
    """Backend-agnostic tuning knobs, mapped onto each engine's parameters.

    Attributes:
        time_limit_s: Wall-clock cap in seconds (None = no limit).
        mip_gap: Relative MIP optimality gap to stop at (e.g. 0.0 = optimal).
        threads: Solver threads (None = backend default).
        verbose: Whether the backend prints its log.
    """

    time_limit_s: Optional[float] = None
    mip_gap: float = 0.0
    threads: Optional[int] = None
    verbose: bool = False


@dataclass
class LeaveSolution:
    """The chosen days. ``break_days`` ⊇ weekends/holidays + taken leave."""

    break_days: list[date] = field(default_factory=list)
    leave_days: list[date] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.break_days)


@dataclass
class SolveStats:
    """Measured outcome of a solve, for benchmarking and comparison."""

    solver: str
    status: str
    objective: Optional[float]
    solve_time_s: float
    num_variables: int
    num_constraints: int
    num_break_days: int
    num_leave_days: int


@dataclass
class SolveResult:
    """A solution paired with its measured stats."""

    solution: LeaveSolution
    stats: SolveStats


class LeaveSolver(ABC):
    """Abstract leave-optimization backend.

    Subclasses build the MILP in their native API and return a
    :class:`SolveResult`. Use :attr:`name` for display and
    :meth:`is_available` to gate backends whose package/license is missing.
    """

    #: Short, human-facing label (e.g. "Xpress", "Gurobi", "OR-Tools (CP-SAT)").
    name: str = "abstract"

    def __init__(self, config: Optional[SolverConfig] = None) -> None:
        self.config = config or SolverConfig()

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """True if this backend can run (package importable and licensed)."""
        raise NotImplementedError

    @abstractmethod
    def solve(self, problem: LeaveProblem) -> SolveResult:
        """Solve ``problem`` and return the solution plus measured stats."""
        raise NotImplementedError
