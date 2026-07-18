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
    `app/services/CLAUDE.md`.
  - `solvers/` — pluggable solver backends (see `app/services/CLAUDE.md`).
  - `leave_model.py` — thin back-compat shim; `solve_leave_lp()` delegates to the
    Xpress backend so existing callers/tests keep working.
- `app/components/` — `results_display.py` (incl. `show_benchmark`),
  `calendar_heatmap.py` (optional `highlight` overlay for "off together" days),
  `household_input.py` + `consensus_display.py` (the household/CPP flow).
- `app/state/session_manager.py` — wraps Streamlit `session_state`.

**Rule:** `services/` and `models/` must not import `streamlit`. Keep solver
math out of the UI layer.

Deep-dive notes for the solver backends (`app/services/solvers/`) and household
coordination (`consensus_service.py` / CPP) live in `app/services/CLAUDE.md`,
which loads when working under that directory.

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
