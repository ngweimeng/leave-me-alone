"""Registry of solver backends, with availability detection.

The UI should offer only backends whose package is importable and licensed,
so the registry separates "known" from "available".
"""

from typing import Optional, Type

from .base import LeaveSolver, SolverConfig
from .gurobi_solver import GurobiSolver
from .ortools_solver import OrToolsSolver
from .scip_solver import ScipSolver
from .xpress_solver import XpressSolver

# All backends the app knows about, in display order.
_ALL: tuple[Type[LeaveSolver], ...] = (
    XpressSolver,
    GurobiSolver,
    ScipSolver,
    OrToolsSolver,
)


def all_solver_classes() -> tuple[Type[LeaveSolver], ...]:
    """Every known backend, regardless of availability."""
    return _ALL


def available_solver_classes() -> list[Type[LeaveSolver]]:
    """Backends that can actually run in this environment."""
    return [cls for cls in _ALL if cls.is_available()]


def available_solver_names() -> list[str]:
    """Display names of runnable backends (for UI dropdowns)."""
    return [cls.name for cls in available_solver_classes()]


def get_solver(name: str, config: Optional[SolverConfig] = None) -> LeaveSolver:
    """Instantiate a backend by its display name.

    Raises:
        ValueError: if the name is unknown or that backend is unavailable.
    """
    for cls in _ALL:
        if cls.name == name:
            if not cls.is_available():
                raise ValueError(
                    f"Solver '{name}' is not available in this environment"
                )
            return cls(config)
    known = ", ".join(cls.name for cls in _ALL)
    raise ValueError(f"Unknown solver '{name}'. Known solvers: {known}")
