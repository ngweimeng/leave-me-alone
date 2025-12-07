"""
Leave optimization model using linear programming.

This module provides functionality to optimize leave scheduling by maximizing
break days (including weekends and holidays) while respecting constraints like
blocked days, leave budget, and prebooked days.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Set, Optional, Tuple, Dict, Any
import warnings

import xpress as xp


# Constants for better maintainability
class LeaveOptimizationConstants:
    """Constants used in leave optimization model."""

    WEEKEND_THRESHOLD = 5  # Saturday = 5, Sunday = 6
    SOLUTION_THRESHOLD = 0.5  # Threshold for binary variable interpretation
    DEFAULT_ADJACENCY_WEIGHT = 1.0


class LeaveOptimizationError(Exception):
    """Custom exception for leave optimization errors."""

    pass


class LeaveOptimizer:
    """
    Linear programming optimizer for leave scheduling.

    This class encapsulates the logic for optimizing leave days to maximize
    total break time while respecting various constraints.
    """

    def __init__(self, suppress_xpress_warnings: bool = True):
        """
        Initialize the leave optimizer.

        Args:
            suppress_xpress_warnings: Whether to suppress Xpress license warnings
        """
        self.logger = logging.getLogger(__name__)

        # Suppress Xpress license warnings if requested
        if suppress_xpress_warnings:
            warnings.filterwarnings("ignore", category=UserWarning, module="xpress")

    def solve(
        self,
        date_range: List[date],
        holidays: Set[date],
        blocked_days: Set[date],
        leave_available: int,
        adjacency_weight: float = LeaveOptimizationConstants.DEFAULT_ADJACENCY_WEIGHT,
        prebooked_days: Optional[Set[date]] = None,
    ) -> Tuple[List[date], List[date]]:
        """
        Solve the leave optimization problem using linear programming.

        This method finds the optimal assignment of leave days that maximizes
        total break days while respecting all constraints.

        Args:
            date_range: List of dates to consider for optimization
            holidays: Set of public holidays (automatically free)
            blocked_days: Set of days when leave cannot be taken
            leave_available: Maximum number of leave days that can be taken
            adjacency_weight: Weight for consecutive break days bonus (default: 1.0)
            prebooked_days: Set of days that are already booked as leave

        Returns:
            Tuple containing:
                - List of break days (including weekends, holidays, and leave days)
                - List of leave days (days where leave must be taken)

        Raises:
            LeaveOptimizationError: If optimization fails or inputs are invalid
            ValueError: If parameters are invalid
        """
        self._validate_inputs(
            date_range,
            holidays,
            blocked_days,
            leave_available,
            adjacency_weight,
            prebooked_days,
        )

        try:
            # Create optimization problem
            model = xp.problem()

            # Create decision variables using old API (to avoid deprecation for now)
            leave_vars = {
                d: xp.var(vartype=xp.binary) for d in date_range
            }  # leave days
            break_vars = {
                d: xp.var(vartype=xp.binary) for d in date_range
            }  # break days

            # Create adjacency variables for consecutive break-days pairs
            adjacency_vars = {}
            for i in range(len(date_range) - 1):
                adjacency_vars[date_range[i]] = xp.var(vartype=xp.binary)

            # Register variables with the problem
            model.addVariable(leave_vars)
            model.addVariable(break_vars)
            model.addVariable(adjacency_vars)

            # Add constraints
            self._add_constraints(
                model,
                leave_vars,
                break_vars,
                adjacency_vars,
                date_range,
                holidays,
                blocked_days,
                leave_available,
                prebooked_days,
            )

            # Set objective function
            self._set_objective_simple(
                model, break_vars, adjacency_vars, date_range, adjacency_weight
            )

            # Solve the model
            model.solve()

            # Extract and return results
            return self._extract_solution_simple(
                model, break_vars, leave_vars, date_range
            )

        except Exception as e:
            self.logger.error(f"Optimization failed: {str(e)}")
            raise LeaveOptimizationError(
                f"Failed to solve optimization problem: {str(e)}"
            )

    def _add_constraints(
        self,
        model: Any,
        leave_vars: Dict[date, Any],
        break_vars: Dict[date, Any],
        adjacency_vars: Dict[date, Any],
        date_range: List[date],
        holidays: Set[date],
        blocked_days: Set[date],
        leave_available: int,
        prebooked_days: Optional[Set[date]],
    ) -> None:
        """Add all constraints to the model."""

        # Cannot take leave on blocked days
        for day in blocked_days:
            if day in leave_vars:
                model.addConstraint(leave_vars[day] == 0)

        # Force prebooked days to be leave days (they count toward the leave budget)
        if prebooked_days:
            for day in prebooked_days:
                if day in leave_vars:
                    model.addConstraint(leave_vars[day] == 1)

        # Leave budget constraint
        model.addConstraint(
            xp.Sum(leave_vars[d] for d in date_range) <= leave_available
        )

        # Break day constraints
        for day in date_range:
            is_naturally_free = (
                day.weekday() >= LeaveOptimizationConstants.WEEKEND_THRESHOLD
                or day in holidays
            )
            if is_naturally_free:
                # Weekends and holidays are automatically break days
                model.addConstraint(break_vars[day] == 1)
            else:
                # Workdays are break days only if leave is taken
                model.addConstraint(break_vars[day] <= leave_vars[day])

        # Link adjacency variables: adj[d] == break[d] AND break[d+1]
        for i in range(len(date_range) - 1):
            current_day = date_range[i]
            next_day = date_range[i + 1]
            adj_var = adjacency_vars[current_day]

            # Standard linearization of AND constraint
            model.addConstraint(adj_var <= break_vars[current_day])
            model.addConstraint(adj_var <= break_vars[next_day])
            model.addConstraint(
                adj_var >= break_vars[current_day] + break_vars[next_day] - 1
            )

    def _set_objective_simple(
        self,
        model: Any,
        break_vars: Dict[date, Any],
        adjacency_vars: Dict[date, Any],
        date_range: List[date],
        adjacency_weight: float,
    ) -> None:
        """Set the objective function using the original pattern."""
        # Objective: maximize total break days plus a bonus for consecutive days
        model.setObjective(
            xp.Sum(break_vars[d] for d in date_range)
            + adjacency_weight * xp.Sum(adjacency_vars[d] for d in adjacency_vars),
            sense=xp.maximize,
        )

    def _extract_solution_simple(
        self,
        model: Any,
        break_vars: Dict[date, Any],
        leave_vars: Dict[date, Any],
        date_range: List[date],
    ) -> Tuple[List[date], List[date]]:
        """Extract the solution using the original pattern."""
        threshold = LeaveOptimizationConstants.SOLUTION_THRESHOLD

        # Extract break days and leave days from solution
        break_days = [
            d for d in date_range if model.getSolution(break_vars[d]) > threshold
        ]
        leave_days = [
            d for d in date_range if model.getSolution(leave_vars[d]) > threshold
        ]

        return break_days, leave_days

    def _validate_inputs(
        self,
        date_range: List[date],
        holidays: Set[date],
        blocked_days: Set[date],
        leave_available: int,
        adjacency_weight: float,
        prebooked_days: Optional[Set[date]],
    ) -> None:
        """Validate input parameters."""
        if not date_range:
            raise ValueError("Date range cannot be empty")

        if leave_available < 0:
            raise ValueError("Leave available cannot be negative")

        if adjacency_weight < 0:
            raise ValueError("Adjacency weight cannot be negative")

        if not isinstance(holidays, set):
            raise ValueError("Holidays must be a set")

        if not isinstance(blocked_days, set):
            raise ValueError("Blocked days must be a set")

        if prebooked_days is not None and not isinstance(prebooked_days, set):
            raise ValueError("Prebooked days must be a set or None")

        # Check for conflicts
        if prebooked_days and blocked_days:
            conflicts = prebooked_days.intersection(blocked_days)
            if conflicts:
                raise ValueError(f"Prebooked days cannot be blocked days: {conflicts}")


# Maintain backward compatibility with the original function interface
def solve_leave_lp(
    date_range: List[date],
    holidays: Set[date],
    blocked_days: Set[date],
    leave_available: int,
    adjacency_weight: float = LeaveOptimizationConstants.DEFAULT_ADJACENCY_WEIGHT,
    prebooked_days: Optional[Set[date]] = None,
) -> Tuple[List[date], List[date]]:
    """
    Solve the leave optimization problem (backward compatibility wrapper).

    This function maintains the original interface for existing code while
    using the improved implementation underneath.

    Args:
        date_range: List of dates to consider for optimization
        holidays: Set of public holidays (automatically free)
        blocked_days: Set of days when leave cannot be taken
        leave_available: Maximum number of leave days that can be taken
        adjacency_weight: Weight for consecutive break days bonus
        prebooked_days: Set of days that are already booked as leave

    Returns:
        Tuple of (break_days, leave_days) lists

    Raises:
        LeaveOptimizationError: If optimization fails
        ValueError: If parameters are invalid
    """
    optimizer = LeaveOptimizer(suppress_xpress_warnings=True)
    return optimizer.solve(
        date_range=date_range,
        holidays=holidays,
        blocked_days=blocked_days,
        leave_available=leave_available,
        adjacency_weight=adjacency_weight,
        prebooked_days=prebooked_days,
    )
