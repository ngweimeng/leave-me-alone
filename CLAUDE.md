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
  - `consensus_service.py` — household PTO coordination via the Consensus
    Planning Protocol (CPP). `coordinate([Member, ...])` runs a dual-decomposition
    (ADMM-style) loop: each person is a private CPP *agent* solved by their own
    solver with per-day `day_prices`; the coordinator prices calendar days to
    maximize days off *together* without seeing anyone's budget/holidays. See
    below.
  - `solvers/` — pluggable solver backends (see below).
  - `leave_model.py` — thin back-compat shim; `solve_leave_lp()` delegates to the
    Xpress backend so existing callers/tests keep working.
- `app/components/` — `results_display.py` (incl. `show_benchmark`),
  `calendar_heatmap.py` (optional `highlight` overlay for "off together" days),
  `household_input.py` + `consensus_display.py` (the household/CPP flow).
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

### Household coordination (`consensus_service.py`)

Coordinates PTO across a couple/family so they maximize days off **together**,
via the Consensus Planning Protocol (CPP — Amazon SCOT / Boyd, a consensus-ADMM
/ dual-decomposition method). Each person is a CPP **agent** whose private
information (budget, per-country holidays, prebooked days, style) never leaves
their own solver; the only shared quantity is which calendar days the household
is off together.

- The joint model adds `+ β·Σ_d z_d` (togetherness bonus) with coupling
  `z_d ≤ break_d^m` for every member. Only the coupling is dualized, so each
  person's feasibility set stays intact and **every iterate is a budget-legal
  schedule**.
- Because break vars are binary, CPP's proximal/dual term collapses to a single
  **linear per-day price** — implemented as `LeaveProblem.day_prices` and added
  to every backend's objective as `Σ_d price_d·break_d`. With no prices the
  objective is byte-identical to before, so single-person solves are unchanged.
- `coordinate()` loop per round: agent step (each solver re-optimizes under its
  prices) → coordinator z-step (`z_d=1` iff `Σ_m λ_d^m < β`) → dual price update
  `λ_d^m ← [λ_d^m + ρ(z_d − break_d^m)]_+`.
- **Agents are integer (non-convex)**, so the dual iteration oscillates rather
  than converging cleanly (a caveat the CPP paper flags for non-convex agents).
  We therefore keep the **best-observed** round; result is `≥` the uncoordinated
  baseline by construction. `ConsensusResult.gain` reports the extra together-days.
- Demo: `python -m app.demos.consensus_demo` (US+UK couple, different budgets).
- UI: `main.py` opens with a "Just me / Household" mode toggle. Household mode
  (`components/household_input.py` → `coordinate()` → `components/consensus_display.py`)
  collects a roster, coordinates, and shows the togetherness gain plus a calendar
  with "off together" days highlighted green. The solo wizard is unchanged.

## The model

Maximize `Σ b_d + α·Σ a_d` where `b_d` = day is a break, `a_d` = days d and d+1
are both breaks (adjacency bonus). Constraints: prebooked leave forced to 1;
`Σ l_d ≤ budget`; weekends/holidays always breaks; weekdays break only if leave
taken; and an optional **max-stretch cap** `K` (no window of `K+1` consecutive
days may be all breaks; all-holiday windows are skipped to stay feasible). Full
formulation is in the README's LP appendix.

- **Vacation "style" is controlled by `max_stretch`** (the `PRESETS` in
  `main.py` map to caps 4/6/9/None). `adjacency_weight` is held fixed-positive:
  it is a *threshold*, not a dial — any α > 0 clusters maximally because the
  break count is fixed by the budget, so α alone cannot set a target block
  length. The cap is the real length control. (See the paper's Finding 3/4.)
- `LeaveProblem.stretch_windows()` builds the feasible windows once; each
  backend adds the cap as a single constraint loop.
- A full year is ~1,100 vars / ~1,500 constraints — well under Xpress Community
  Edition's 5,000 cap.
- The paper lives in `paper/` (LaTeX + reproducible experiment harness).

## Conventions

- Format with `black` before committing.
- Add tests under `app/tests/` mirroring the module name.
