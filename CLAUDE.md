# Leave-Me-Alone — PTO Optimizer

Streamlit app that uses a binary MILP (FICO Xpress solver) to choose which PTO
days to take so total continuous time off is maximized — by clustering leave
against weekends and public holidays.

## Run

```bash
source .venv/bin/activate
pip install -e ".[dev]"     # one-time; registers the `app` package
streamlit run app/main.py   # or ./run_app.sh
```

## Test & format

```bash
python -m pytest -q          # tests live in app/tests/
black app                    # format
./run_check.sh               # does both
```

## Architecture (layered — keep the boundaries)

- `app/main.py` — Streamlit orchestrator, a 7-step input wizard.
- `app/models/leave_request.py` — `LeaveOptimizationRequest` dataclass.
- `app/services/`
  - `holiday_service.py` — wraps `holidays` + `pycountry`; no Streamlit imports.
  - `optimization_service.py` — adapter: builds the problem, calls a solver
    (`run_optimizer`) or benchmarks several (`benchmark_optimizer`).
  - `solvers/` — pluggable solver backends (see below).
  - `leave_model.py` — thin back-compat shim; `solve_leave_lp()` delegates to the
    Xpress backend so existing callers/tests keep working.
- `app/components/` — `results_display.py` (incl. `show_benchmark`), `calendar_heatmap.py`.
- `app/state/session_manager.py` — wraps Streamlit `session_state`.

### Solver backends (`app/services/solvers/`)

Strategy pattern so the same problem can run on different engines and be compared:

- `base.py` — `LeaveProblem` (frozen inputs), `SolverConfig` (uniform knobs:
  time limit, MIP gap, threads, verbose), `LeaveSolution`, `SolveStats`,
  `SolveResult`, and the `LeaveSolver` ABC.
- `xpress_solver.py` / `gurobi_solver.py` / `scip_solver.py` / `ortools_solver.py`
  — one class each, building the model in that engine's native API.
- `registry.py` — `available_solver_classes()` auto-detects which backends are
  importable + licensed; the UI only offers available ones.
- `benchmark.py` — `run_benchmark()` solves with all backends; `schedules_diverge()`
  flags when they return different-but-equally-optimal schedules.

Backend notes:
- **Xpress** — Community license, ~5000 row/col cap.
- **Gurobi** — `pip install gurobipy` ships a free license capped at **2000 vars /
  2000 constraints**. A calendar year (~1,094 vars) fits; long custom horizons may
  not, in which case `GurobiSolver.is_available()`/`solve()` degrade gracefully.
- **SCIP** (`pyscipopt`) — fully open source, no license, no cap; the strongest
  free MILP solver. NOTE: SCIP frees the original problem after solving, so the
  constraint count is captured *before* `optimize()`.
- **OR-Tools (CP-SAT)** — fully open source, no license, no cap. A constraint-
  programming / SAT engine — a *different paradigm* from the LP solvers, which is
  what makes it an interesting benchmark comparison. Works in integers; it scales
  the float `adjacency_weight` internally.

Known conflict: **do not add the standalone `highspy` (HiGHS) package** alongside
OR-Tools. OR-Tools bundles its own native HiGHS, and importing both into one
process segfaults on macOS (symbol clash). The "benchmark all" feature loads
every backend in one process, so they cannot coexist.

For a model this size **all backends reach the same optimal objective** — the
benchmark's value is comparing solve time and exposing non-unique optima, not
finding a "better" answer.

**Rule:** `services/` and `models/` must not import `streamlit`. Keep solver
math out of the UI layer.

## The model

Maximize `Σ b_d + α·Σ a_d` where `b_d` = day is a break, `a_d` = days d and d+1
are both breaks (adjacency bonus). Constraints: prebooked leave forced to 1;
`Σ l_d ≤ budget`; weekends/holidays always breaks; weekdays break only if leave
taken. Full formulation is in the README's LP appendix.

- **Vacation "style" is controlled only by `adjacency_weight`** (the `PRESETS` in
  `main.py`). Higher α → longer continuous blocks.
- A full year is ~1,100 vars / ~1,500 constraints — well under Xpress Community
  Edition's 5,000 cap. There is headroom to add features like min/max-stretch
  constraints if desired (they were removed as unused dead params).

## Conventions

- Format with `black` before committing.
- Add tests under `app/tests/` mirroring the module name.
