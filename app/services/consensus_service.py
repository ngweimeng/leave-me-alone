"""Consensus Planning Protocol (CPP) for household PTO coordination.

The single-person optimizer answers "which PTO days maximize *my* continuous
time off?". This module answers the household question: "which PTO days let a
couple / family maximize the time they are off *together*, while each person
still respects their own budget, holidays and prebooked days?".

Why CPP
-------
Each person is a CPP *agent* with **private information** — their leave budget,
their country's public holidays, their prebooked (e.g. medical) days, their
vacation style. The coordinator never sees any of that. The only thing shared
is the **public variable**: which calendar days the household is off *together*.
"Days off" is a common currency across people for free, which is exactly the
precondition CPP needs to exchange value between agents.

The model
---------
Let ``b_d^m ∈ {0,1}`` be "person *m* is on a break on day *d*" (their existing
solver's ``break`` variable) and ``z_d ∈ [0,1]`` be "the household is off
together on day *d*". Together-time only counts when *everyone* is off:

    maximize   Σ_m u_m(b^m)          (each person's own continuous-time-off value)
             + β · Σ_d z_d           (household togetherness bonus)
    subject to z_d ≤ b_d^m           for every person m, every day d
               b^m ∈ Feasible_m      (private budget / holidays / prebooked / stretch)
               z_d ∈ [0, 1]

Only the *coupling* constraints ``z_d ≤ b_d^m`` are dualized (with multipliers
``λ_d^m ≥ 0``); each person's private feasibility set is left intact. That
decomposes the problem, per CPP's dual interface, into:

* **Agent step** (run in each person's own solver, privately):
      maximize u_m(b^m) + Σ_d λ_d^m · b_d^m
  i.e. the base objective plus a per-day *price* — precisely the ``day_prices``
  hook on :class:`~app.services.solvers.base.LeaveProblem`.

* **Coordinator z-step** (closed form): z_d = 1 iff Σ_m λ_d^m < β, else 0.

* **Price update** (dual subgradient / ADMM ascent):
      λ_d^m ← [ λ_d^m + ρ · (z_d − b_d^m) ]_+
  If the household wants day *d* (z_d = 1) but person *m* is working
  (b_d^m = 0), their price for that day rises — nudging them to take it next
  round. If they are already off when nobody else is, the price relaxes.

Because private feasibility is never relaxed, **every iterate is a genuine,
budget-legal schedule for every person**. The agents are integer programs
(non-convex), so we do not rely on the dual iteration converging to the exact
optimum — a caveat the CPP paper itself flags for non-convex agents. Instead we
evaluate the true togetherness of each round's real schedules and keep the best
one seen. That best is ``≥`` the uncoordinated baseline by construction, so
coordination can only help.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.services.solvers import LeaveProblem, SolverConfig, get_solver
from app.services.solvers.base import LeaveSolution


@dataclass(frozen=True)
class Member:
    """One person in the household: a label plus their private problem.

    ``problem`` carries everything private to this person — their PTO budget,
    their country's holidays, their prebooked days, their vacation style. The
    coordinator only ever reads it to hand to that person's own solver; it never
    inspects the contents to make household decisions.
    """

    name: str
    problem: LeaveProblem
    solver_name: str = "SCIP"


@dataclass
class MemberSchedule:
    """A member's resolved schedule in the consensus plan."""

    name: str
    solution: LeaveSolution

    @property
    def break_days(self) -> set[date]:
        return set(self.solution.break_days)

    @property
    def leave_days(self) -> list[date]:
        return self.solution.leave_days


@dataclass
class ConsensusResult:
    """Outcome of a consensus run.

    Attributes:
        members: Each person's final schedule in the consensus plan.
        shared_off_days: Days on which *every* member is on a break (the
            household togetherness the coordinator maximized).
        baseline_shared_off_days: Shared off-days if everyone optimized
            independently (no coordination). The gain is the whole point.
        iterations: Number of coordinator rounds actually run.
        converged: True if prices/plan stopped changing before the cap.
        history: Per-round count of shared off-days, for inspection/plots.
    """

    members: list[MemberSchedule]
    shared_off_days: list[date]
    baseline_shared_off_days: list[date]
    iterations: int
    converged: bool
    history: list[int] = field(default_factory=list)

    @property
    def togetherness(self) -> int:
        """Number of days the whole household is off together."""
        return len(self.shared_off_days)

    @property
    def baseline_togetherness(self) -> int:
        return len(self.baseline_shared_off_days)

    @property
    def gain(self) -> int:
        """Extra together-days coordination bought over the baseline."""
        return self.togetherness - self.baseline_togetherness


def _shared_off_days(schedules: list[MemberSchedule]) -> list[date]:
    """Days on which every member is on a break (intersection of break sets)."""
    if not schedules:
        return []
    common = set.intersection(*(s.break_days for s in schedules))
    return sorted(common)


def _solve_member(member: Member, prices: dict[date, float], config) -> LeaveSolution:
    """Run one member's private oracle with the given per-day consensus prices."""
    problem = member.problem.with_prices(prices) if prices else member.problem
    return get_solver(member.solver_name, config).solve(problem).solution


def coordinate(
    members: list[Member],
    togetherness_bonus: float = 2.0,
    rho: float = 1.0,
    max_iters: int = 40,
    config: Optional[SolverConfig] = None,
) -> ConsensusResult:
    """Coordinate a household's PTO with the Consensus Planning Protocol.

    Args:
        members: The people to coordinate (2+ for a meaningful result).
        togetherness_bonus: ``β`` — how much a shared off-day is worth relative
            to one person's own day off. Must exceed 1 for the household to be
            willing to "spend" budget lining days up; higher clusters harder.
        rho: ``ρ`` — dual step size for the price update. Larger reacts faster
            but can oscillate.
        max_iters: Coordinator round cap.
        config: Solver config passed to every agent solve.

    Returns:
        A :class:`ConsensusResult` whose schedules are the best (most
        together, fewest total leave-days as a tie-break) round observed —
        always at least as good as the uncoordinated baseline.
    """
    if len(members) < 2:
        raise ValueError("coordinate() needs at least two members")

    config = config or SolverConfig()

    # Union of every member's horizon: the days the coordinator can price.
    all_days = sorted({d for m in members for d in m.problem.date_range})

    # λ_d^m — each member's price vector, starts at zero (= independent solve).
    prices: dict[str, dict[date, float]] = {m.name: {} for m in members}

    # Round 0 with no prices *is* the uncoordinated baseline.
    schedules = [
        MemberSchedule(m.name, _solve_member(m, prices[m.name], config))
        for m in members
    ]
    baseline_shared = _shared_off_days(schedules)

    def _total_leave(scheds: list[MemberSchedule]) -> int:
        return sum(len(s.leave_days) for s in scheds)

    best = schedules
    best_shared = baseline_shared
    # Tie-break: among equally-together plans prefer the one spending less PTO.
    best_key = (len(baseline_shared), -_total_leave(schedules))
    history = [len(baseline_shared)]

    converged = False
    iterations = 0
    for it in range(1, max_iters + 1):
        iterations = it

        # Which days is each member on a break in the current plan?
        break_of = {s.name: s.break_days for s in schedules}

        # Coordinator z-step: the household wants day d off together when the
        # total price of aligning there is still cheaper than the bonus.
        z = {
            d: (sum(prices[m.name].get(d, 0.0) for m in members) < togetherness_bonus)
            for d in all_days
        }

        # Price update: raise a member's price on days the household wants but
        # they don't take; relax it where they're off alone. Clipped at 0 so
        # prices stay rewards (dual feasibility λ ≥ 0).
        changed = False
        for m in members:
            pm = prices[m.name]
            brk = break_of[m.name]
            for d in all_days:
                z_d = 1.0 if z[d] else 0.0
                b_d = 1.0 if d in brk else 0.0
                new = max(0.0, pm.get(d, 0.0) + rho * (z_d - b_d))
                if new != pm.get(d, 0.0):
                    changed = True
                if new > 0.0:
                    pm[d] = new
                elif d in pm:
                    del pm[d]

        if not changed:
            converged = True
            break

        # Agent step: everyone re-optimizes privately under the new prices.
        schedules = [
            MemberSchedule(m.name, _solve_member(m, prices[m.name], config))
            for m in members
        ]
        shared = _shared_off_days(schedules)
        history.append(len(shared))

        key = (len(shared), -_total_leave(schedules))
        if key > best_key:
            best_key = key
            best = schedules
            best_shared = shared

    return ConsensusResult(
        members=best,
        shared_off_days=best_shared,
        baseline_shared_off_days=baseline_shared,
        iterations=iterations,
        converged=converged,
        history=history,
    )
