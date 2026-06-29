"""Run a problem through multiple backends and compare the results.

For a model this small every backend reaches the same optimal objective, so
the interesting signals are (a) solve time / binding overhead and (b) whether
backends return *different but equally optimal* schedules — a sign the optimum
is not unique.
"""

from dataclasses import dataclass
from typing import Optional

from .base import LeaveProblem, SolverConfig, SolveResult
from .registry import available_solver_classes, get_solver


@dataclass
class BenchmarkRow:
    """One backend's outcome in a benchmark run."""

    result: SolveResult
    leave_signature: tuple  # sorted ISO dates of leave; identifies the schedule


def run_benchmark(
    problem: LeaveProblem,
    config: Optional[SolverConfig] = None,
    solver_names: Optional[list[str]] = None,
) -> list[BenchmarkRow]:
    """Solve ``problem`` with each requested (or all available) backend.

    A backend that errors mid-solve is skipped rather than aborting the run,
    so one missing license never sinks the comparison.
    """
    if solver_names is None:
        solvers = [cls(config) for cls in available_solver_classes()]
    else:
        solvers = [get_solver(name, config) for name in solver_names]

    rows: list[BenchmarkRow] = []
    for solver in solvers:
        try:
            result = solver.solve(problem)
        except Exception as exc:  # a missing license / size cap shouldn't abort
            print(f"⚠️ {solver.name} failed: {exc}")
            continue
        signature = tuple(sorted(d.isoformat() for d in result.solution.leave_days))
        rows.append(BenchmarkRow(result=result, leave_signature=signature))
    return rows


def schedules_diverge(rows: list[BenchmarkRow]) -> bool:
    """True if backends found different leave schedules (non-unique optimum)."""
    signatures = {row.leave_signature for row in rows if row.result.solution.found}
    return len(signatures) > 1
