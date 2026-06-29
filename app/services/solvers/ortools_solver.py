"""OR-Tools CP-SAT backend for the leave-optimization model.

CP-SAT is Google's open-source (Apache) constraint-programming / SAT-based
solver — a fundamentally different algorithm from the LP branch-and-cut engines
(Xpress, Gurobi). It excels at pure-binary models like this one, which
makes it the most interesting point of comparison in the benchmark.

CP-SAT works in integers; it scales the float ``adjacency_weight`` internally,
and ``ObjectiveValue()`` reports the true (unscaled) objective.
"""

import time

from .base import LeaveProblem, LeaveSolution, LeaveSolver, SolveResult, SolveStats

try:
    from ortools.sat.python import cp_model

    _IMPORT_OK = True
except Exception:  # pragma: no cover - environment without ortools
    _IMPORT_OK = False


class OrToolsSolver(LeaveSolver):
    """OR-Tools CP-SAT. Open source; constraint-programming paradigm."""

    name = "OR-Tools (CP-SAT)"

    @classmethod
    def is_available(cls) -> bool:
        return _IMPORT_OK

    def solve(self, problem: LeaveProblem) -> SolveResult:
        cfg = self.config
        dr = problem.date_range

        model = cp_model.CpModel()
        leave = {d: model.NewBoolVar(f"leave_{d.isoformat()}") for d in dr}
        brk = {d: model.NewBoolVar(f"break_{d.isoformat()}") for d in dr}
        adj = {
            dr[i]: model.NewBoolVar(f"adj_{dr[i].isoformat()}")
            for i in range(len(dr) - 1)
        }

        for d in problem.prebooked_days:
            if d in leave:
                model.Add(leave[d] == 1)

        model.Add(sum(leave[d] for d in dr) <= problem.leave_available)

        for d in dr:
            if problem.is_fixed_break(d):
                model.Add(brk[d] == 1)
            else:
                model.Add(brk[d] <= leave[d])

        for i in range(len(dr) - 1):
            d1, d2 = dr[i], dr[i + 1]
            model.Add(adj[d1] <= brk[d1])
            model.Add(adj[d1] <= brk[d2])
            model.Add(adj[d1] >= brk[d1] + brk[d2] - 1)

        objective = sum(brk[d] for d in dr)
        objective += problem.adjacency_weight * sum(adj[d] for d in adj)
        model.Maximize(objective)

        solver = cp_model.CpSolver()
        solver.parameters.log_search_progress = bool(cfg.verbose)
        if cfg.time_limit_s is not None:
            solver.parameters.max_time_in_seconds = float(cfg.time_limit_s)
        if cfg.mip_gap is not None:
            solver.parameters.relative_gap_limit = float(cfg.mip_gap)
        if cfg.threads is not None:
            solver.parameters.num_search_workers = int(cfg.threads)

        t0 = time.perf_counter()
        status = solver.Solve(model)
        elapsed = time.perf_counter() - t0

        status_name = solver.StatusName(status)
        # CP-SAT has no direct "num constraints" attribute; count what we added.
        num_constraints = len(model.Proto().constraints)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            stats = SolveStats(
                solver=self.name,
                status=status_name,
                objective=None,
                solve_time_s=elapsed,
                num_variables=problem.num_variables,
                num_constraints=num_constraints,
                num_break_days=0,
                num_leave_days=0,
            )
            return SolveResult(LeaveSolution(), stats)

        break_days = [d for d in dr if solver.Value(brk[d]) > 0.5]
        leave_days = [d for d in dr if solver.Value(leave[d]) > 0.5]
        stats = SolveStats(
            solver=self.name,
            status=status_name,
            objective=float(solver.ObjectiveValue()),
            solve_time_s=elapsed,
            num_variables=problem.num_variables,
            num_constraints=num_constraints,
            num_break_days=len(break_days),
            num_leave_days=len(leave_days),
        )
        return SolveResult(LeaveSolution(break_days, leave_days), stats)
