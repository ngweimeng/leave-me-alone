# `app/services/` — solver backends & household coordination

Deep-dive notes for the two subsystems under this directory. Loaded only when
working in `app/services/`. The layered overview and the `services/`/`models/`
no-`streamlit` rule live in the root `CLAUDE.md`.

## Solver backends (`app/services/solvers/`)

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

## Household coordination (`consensus_service.py`)

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
