"""Pluggable solver backends for the leave-optimization MILP."""

from .base import (
    LeaveProblem,
    LeaveSolution,
    LeaveSolver,
    SolveResult,
    SolveStats,
    SolverConfig,
)
from .benchmark import BenchmarkRow, run_benchmark, schedules_diverge
from .registry import (
    available_solver_classes,
    available_solver_names,
    get_solver,
)

__all__ = [
    "LeaveProblem",
    "LeaveSolution",
    "LeaveSolver",
    "SolveResult",
    "SolveStats",
    "SolverConfig",
    "BenchmarkRow",
    "run_benchmark",
    "schedules_diverge",
    "available_solver_classes",
    "available_solver_names",
    "get_solver",
]
