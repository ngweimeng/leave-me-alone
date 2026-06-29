"""Xpress backend for the leave-optimization MILP."""

import time
import warnings

from .base import LeaveProblem, LeaveSolution, LeaveSolver, SolveResult, SolveStats

try:
    import xpress as xp

    warnings.filterwarnings("ignore", category=UserWarning, module="xpress")
    _IMPORT_OK = True
except Exception:  # pragma: no cover - environment without xpress
    _IMPORT_OK = False


class XpressSolver(LeaveSolver):
    """FICO Xpress. Community license caps the model at ~5000 rows/cols."""

    name = "Xpress"

    @classmethod
    def is_available(cls) -> bool:
        return _IMPORT_OK

    def solve(self, problem: LeaveProblem) -> SolveResult:
        cfg = self.config
        model = xp.problem()

        dr = problem.date_range
        leave = {d: xp.var(vartype=xp.binary) for d in dr}
        brk = {d: xp.var(vartype=xp.binary) for d in dr}
        adj = {dr[i]: xp.var(vartype=xp.binary) for i in range(len(dr) - 1)}
        model.addVariable(leave)
        model.addVariable(brk)
        model.addVariable(adj)

        for d in problem.prebooked_days:
            if d in leave:
                model.addConstraint(leave[d] == 1)

        model.addConstraint(xp.Sum(leave[d] for d in dr) <= problem.leave_available)

        for d in dr:
            if problem.is_fixed_break(d):
                model.addConstraint(brk[d] == 1)
            else:
                model.addConstraint(brk[d] <= leave[d])

        for i in range(len(dr) - 1):
            d1, d2 = dr[i], dr[i + 1]
            model.addConstraint(adj[d1] <= brk[d1])
            model.addConstraint(adj[d1] <= brk[d2])
            model.addConstraint(adj[d1] >= brk[d1] + brk[d2] - 1)

        objective = xp.Sum(brk[d] for d in dr)
        objective += problem.adjacency_weight * xp.Sum(adj[d] for d in adj)
        model.setObjective(objective, sense=xp.maximize)

        # Map uniform config onto Xpress controls.
        controls = {}
        if cfg.time_limit_s is not None:
            controls["maxtime"] = int(cfg.time_limit_s)
        if cfg.mip_gap is not None:
            controls["miprelstop"] = cfg.mip_gap
        if cfg.threads is not None:
            controls["threads"] = cfg.threads
        controls["outputlog"] = 1 if cfg.verbose else 0
        if controls:
            model.setControl(controls)

        t0 = time.perf_counter()
        model.solve()
        elapsed = time.perf_counter() - t0

        num_constraints = int(model.getAttrib("rows"))
        if model.getAttrib("mipsols") == 0:
            stats = SolveStats(
                solver=self.name,
                status=str(model.getProbStatusString()),
                objective=None,
                solve_time_s=elapsed,
                num_variables=problem.num_variables,
                num_constraints=num_constraints,
                num_break_days=0,
                num_leave_days=0,
            )
            return SolveResult(LeaveSolution(), stats)

        break_days = [d for d in dr if model.getSolution(brk[d]) > 0.5]
        leave_days = [d for d in dr if model.getSolution(leave[d]) > 0.5]
        stats = SolveStats(
            solver=self.name,
            status=str(model.getProbStatusString()),
            objective=float(model.getObjVal()),
            solve_time_s=elapsed,
            num_variables=problem.num_variables,
            num_constraints=num_constraints,
            num_break_days=len(break_days),
            num_leave_days=len(leave_days),
        )
        return SolveResult(LeaveSolution(break_days, leave_days), stats)
