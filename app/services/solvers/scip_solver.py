"""SCIP backend for the leave-optimization MILP.

SCIP is a powerful open-source (Apache, since SCIP 9) solver with a native
Python API (``pyscipopt``) — no license, no size cap. It is an LP
branch-and-cut engine like Xpress/Gurobi, and is the strongest freely
available MILP solver.
"""

import time

from .base import LeaveProblem, LeaveSolution, LeaveSolver, SolveResult, SolveStats

try:
    from pyscipopt import Model, quicksum

    _IMPORT_OK = True
except Exception:  # pragma: no cover - environment without pyscipopt
    _IMPORT_OK = False


class ScipSolver(LeaveSolver):
    """SCIP via the native ``pyscipopt`` API. Open source, no size cap."""

    name = "SCIP"

    @classmethod
    def is_available(cls) -> bool:
        return _IMPORT_OK

    def solve(self, problem: LeaveProblem) -> SolveResult:
        cfg = self.config
        dr = problem.date_range

        model = Model()
        if not cfg.verbose:
            model.hideOutput()
        if cfg.time_limit_s is not None:
            model.setParam("limits/time", float(cfg.time_limit_s))
        if cfg.mip_gap is not None:
            model.setParam("limits/gap", float(cfg.mip_gap))
        if cfg.threads is not None:
            model.setParam("parallel/maxnthreads", int(cfg.threads))

        leave = {d: model.addVar(vtype="B", name=f"leave_{d.isoformat()}") for d in dr}
        brk = {d: model.addVar(vtype="B", name=f"break_{d.isoformat()}") for d in dr}
        adj = {
            dr[i]: model.addVar(vtype="B", name=f"adj_{dr[i].isoformat()}")
            for i in range(len(dr) - 1)
        }

        for d in problem.prebooked_days:
            if d in leave:
                model.addCons(leave[d] == 1)

        model.addCons(quicksum(leave[d] for d in dr) <= problem.leave_available)

        for d in dr:
            if problem.is_fixed_break(d):
                model.addCons(brk[d] == 1)
            else:
                model.addCons(brk[d] <= leave[d])

        for i in range(len(dr) - 1):
            d1, d2 = dr[i], dr[i + 1]
            model.addCons(adj[d1] <= brk[d1])
            model.addCons(adj[d1] <= brk[d2])
            model.addCons(adj[d1] >= brk[d1] + brk[d2] - 1)

        objective = quicksum(brk[d] for d in dr)
        objective += problem.adjacency_weight * quicksum(adj[d] for d in adj)
        model.setObjective(objective, sense="maximize")

        # SCIP frees the original problem after solving, so capture the
        # constraint count before optimize().
        num_constraints = model.getNConss()

        t0 = time.perf_counter()
        model.optimize()
        elapsed = time.perf_counter() - t0

        status = model.getStatus()
        if model.getNSols() == 0:
            stats = SolveStats(
                solver=self.name,
                status=status,
                objective=None,
                solve_time_s=elapsed,
                num_variables=problem.num_variables,
                num_constraints=num_constraints,
                num_break_days=0,
                num_leave_days=0,
            )
            return SolveResult(LeaveSolution(), stats)

        break_days = [d for d in dr if model.getVal(brk[d]) > 0.5]
        leave_days = [d for d in dr if model.getVal(leave[d]) > 0.5]
        stats = SolveStats(
            solver=self.name,
            status=status,
            objective=float(model.getObjVal()),
            solve_time_s=elapsed,
            num_variables=problem.num_variables,
            num_constraints=num_constraints,
            num_break_days=len(break_days),
            num_leave_days=len(leave_days),
        )
        return SolveResult(LeaveSolution(break_days, leave_days), stats)
