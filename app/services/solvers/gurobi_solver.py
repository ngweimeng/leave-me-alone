"""Gurobi backend for the leave-optimization MILP.

Gurobi is commercial, but ``pip install gurobipy`` ships a free limited
license capped at 2000 variables and 2000 constraints. A single calendar
year fits under that cap; longer custom horizons may exceed it, in which
case the solve raises and the backend reports the failure.
"""

import time

from .base import LeaveProblem, LeaveSolution, LeaveSolver, SolveResult, SolveStats

try:
    import gurobipy as gp
    from gurobipy import GRB

    _IMPORT_OK = True
except Exception:  # pragma: no cover - environment without gurobipy
    _IMPORT_OK = False


class GurobiSolver(LeaveSolver):
    """Gurobi. Free pip license is limited to 2000 vars / 2000 constraints."""

    name = "Gurobi"

    @classmethod
    def is_available(cls) -> bool:
        if not _IMPORT_OK:
            return False
        # Confirm a usable license by instantiating a trivial model.
        try:
            env = gp.Env(empty=True)
            env.setParam("OutputFlag", 0)
            env.start()
            gp.Model(env=env).dispose()
            env.dispose()
            return True
        except Exception:  # pragma: no cover - no/expired license
            return False

    def solve(self, problem: LeaveProblem) -> SolveResult:
        cfg = self.config
        dr = problem.date_range

        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 1 if cfg.verbose else 0)
        env.start()
        model = gp.Model(env=env)

        if cfg.time_limit_s is not None:
            model.setParam("TimeLimit", cfg.time_limit_s)
        if cfg.mip_gap is not None:
            model.setParam("MIPGap", cfg.mip_gap)
        if cfg.threads is not None:
            model.setParam("Threads", cfg.threads)

        leave = model.addVars(dr, vtype=GRB.BINARY, name="leave")
        brk = model.addVars(dr, vtype=GRB.BINARY, name="break")
        adj_idx = [dr[i] for i in range(len(dr) - 1)]
        adj = model.addVars(adj_idx, vtype=GRB.BINARY, name="adj")

        for d in problem.prebooked_days:
            if d in leave:
                model.addConstr(leave[d] == 1)

        model.addConstr(gp.quicksum(leave[d] for d in dr) <= problem.leave_available)

        for d in dr:
            if problem.is_fixed_break(d):
                model.addConstr(brk[d] == 1)
            else:
                model.addConstr(brk[d] <= leave[d])

        for i in range(len(dr) - 1):
            d1, d2 = dr[i], dr[i + 1]
            model.addConstr(adj[d1] <= brk[d1])
            model.addConstr(adj[d1] <= brk[d2])
            model.addConstr(adj[d1] >= brk[d1] + brk[d2] - 1)

        objective = gp.quicksum(brk[d] for d in dr)
        objective += problem.adjacency_weight * gp.quicksum(adj[d] for d in adj_idx)
        model.setObjective(objective, GRB.MAXIMIZE)

        t0 = time.perf_counter()
        model.optimize()
        elapsed = time.perf_counter() - t0

        status_name = {
            GRB.OPTIMAL: "OPTIMAL",
            GRB.TIME_LIMIT: "TIME_LIMIT",
            GRB.INFEASIBLE: "INFEASIBLE",
            GRB.SUBOPTIMAL: "SUBOPTIMAL",
        }.get(model.Status, str(model.Status))

        if model.SolCount == 0:
            stats = SolveStats(
                solver=self.name,
                status=status_name,
                objective=None,
                solve_time_s=elapsed,
                num_variables=problem.num_variables,
                num_constraints=model.NumConstrs,
                num_break_days=0,
                num_leave_days=0,
            )
            model.dispose()
            env.dispose()
            return SolveResult(LeaveSolution(), stats)

        break_days = [d for d in dr if brk[d].X > 0.5]
        leave_days = [d for d in dr if leave[d].X > 0.5]
        num_constraints = model.NumConstrs
        objective_val = float(model.ObjVal)
        model.dispose()
        env.dispose()

        stats = SolveStats(
            solver=self.name,
            status=status_name,
            objective=objective_val,
            solve_time_s=elapsed,
            num_variables=problem.num_variables,
            num_constraints=num_constraints,
            num_break_days=len(break_days),
            num_leave_days=len(leave_days),
        )
        return SolveResult(LeaveSolution(break_days, leave_days), stats)
