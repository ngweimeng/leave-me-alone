# Leave-Me-Alone: PTO Optimizer

> Scientifically maximize your vacation time using linear programming, public holidays, and strategic PTO allocation.

A Streamlit application that uses FICO Xpress optimization to help you get the most continuous time off by strategically placing your paid time off (PTO) days adjacent to weekends and public holidays.

It has two modes: **Just me** — optimize a single person's PTO — and
**Household (couple / family)** — coordinate several people so they maximize the
days they are off *together*, while each person keeps their own budget, country
holidays and pre-booked days private (see [Household coordination](#household-coordination-consensus-planning-protocol)).

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.0+-red.svg)](https://streamlit.io)

## Quick Start

### Prerequisites

- Python 3.8 or higher
- [FICO Xpress](https://www.fico.com/en/products/fico-xpress-optimization) solver (Community Edition available for free)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/ngweimeng/leave-me-alone.git
   cd leave-me-alone
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   ./run_app.sh
   # or
   streamlit run app/main.py
   ```

5. **Open in browser**
   
   The app will automatically open at `http://localhost:8501`

## Development

### Code Quality Check (Format + Test)
Run both code formatting and tests in one command:
```bash
./run_check.sh
```
This will:
- Format all code with `black` (auto-installs if needed)
- Run all tests with `pytest`
- Show a nice summary of results

### Running Tests Only
```bash
python -m pytest -q
```

### Formatting Code Only
```bash
black app
```

## Usage

At the top of the app, choose **Just me** or **Household (couple / family)**.

### Just me — Step-by-Step Guide

1. **Enter PTO Days**: Input how many paid time-off days you have available

2. **Select Timeframe**: Choose your planning period (calendar year or custom 12-month period)

3. **Configure Public Holidays**: 
   - Select your country from 100+ supported countries
   - Review and edit the holiday list in an interactive table
   - Select/deselect specific holidays

4. **Choose Vacation Style**: Pick a preset that caps how long any single
   continuous break may run (`max_stretch`):
   - **Long Weekends (3-4 days)** - breaks capped at 4 consecutive days
   - **Mini Breaks (5-6 days)** - breaks capped at 6 consecutive days
   - **Week-Long Breaks (7-9 days)** - breaks capped at 9 consecutive days
   - **Extended Vacations (>2 weeks)** - no cap; longest possible blocks

   > The style controls break **length** via a hard cap, not the
   > `adjacency_weight`. A positive adjacency weight only decides *whether* to
   > cluster at all — any positive value clusters maximally, so it cannot set a
   > target length on its own. See the LP appendix.

5. **Add Pre-booked Days** (optional): Specify days you've already committed to

6. **Add Other Time Off** (optional): Include company holidays, personal days, etc.

7. **Optimize**: Click the "Optimize Break" button to generate your optimal schedule

8. **View Results**: See your optimized break calendar with:
   - Total break days achieved
   - PTO days used
   - Calendar heatmap visualization
   - Detailed breakdown of leave days

### Household — Step-by-Step Guide

1. **Choose the shared timeframe**: everyone plans within the same date range.

2. **Add the household**: a table where each person gets a name, country
   (their own public-holiday calendar), PTO budget, and vacation style. Add or
   remove people freely; optional per-person pre-booked days live behind a
   per-row expander. Pick the solver backend used privately for each person.

3. **Tune coordination** (optional): a *togetherness priority* slider trades off
   how hard to push everyone's breaks into alignment.

4. **Coordinate**: click **Coordinate Household Breaks** to see:
   - **Days off together** vs. the *everyone-books-solo* baseline, and the
     **extra days** coordination bought
   - a calendar with the shared "off together" days highlighted green
   - a per-person breakdown of PTO used and shared days

## Project Structure

```
leave-me-alone/
├── app/
│   ├── main.py                    # Main Streamlit orchestrator (mode toggle)
│   ├── components/
│   │   ├── results_display.py    # Solo results visualization
│   │   ├── calendar_heatmap.py   # Calendar heatmap (optional "off together" overlay)
│   │   ├── household_input.py    # Household roster editor
│   │   └── consensus_display.py  # Household coordination result view
│   ├── models/
│   │   └── leave_request.py      # Request data model
│   ├── services/
│   │   ├── optimization_service.py # Optimizer + benchmark wrapper
│   │   ├── consensus_service.py   # Household coordination (CPP) coordinator
│   │   ├── leave_model.py         # Back-compat shim (solve_leave_lp)
│   │   ├── holiday_service.py     # Holiday data fetching
│   │   └── solvers/               # Pluggable solver backends
│   │       ├── base.py            # LeaveProblem / SolverConfig / LeaveSolver (ABC)
│   │       ├── xpress_solver.py   # FICO Xpress backend (LP branch-and-cut)
│   │       ├── gurobi_solver.py   # Gurobi backend (free limited license)
│   │       ├── scip_solver.py     # SCIP backend (open-source LP branch-and-cut)
│   │       ├── ortools_solver.py  # OR-Tools CP-SAT backend (constraint programming)
│   │       ├── registry.py        # Auto-detect available backends
│   │       └── benchmark.py       # Compare backends on the same problem
│   ├── demos/
│   │   └── consensus_demo.py      # Headless household-coordination demo
│   ├── state/
│   │   └── session_manager.py     # Session state management
│   └── tests/
│       ├── test_holiday_service.py
│       ├── test_leave_model.py
│       ├── test_optimization_service.py
│       ├── test_solvers.py
│       ├── test_consensus_service.py
│       └── test_household_input.py
├── pyproject.toml                 # Package metadata, deps, black & pytest config
├── requirements.txt               # Python dependencies
├── run_app.sh                     # Launch application
├── run_check.sh                   # Format code + run tests
├── LICENSE                        # Apache 2.0 license
└── README.md                      # This file
```

## Solver Backends

The optimization model can be solved by interchangeable backends, selectable in
the UI (Step 5). They share a common `LeaveSolver` interface, so adding another
engine is a single new class.

| Backend | Paradigm | License | Notes |
|---|---|---|---|
| **FICO Xpress** | LP branch-and-cut | Commercial; free Community Edition | ~5000 variable/constraint cap |
| **Gurobi** | LP branch-and-cut | Commercial; `pip install gurobipy` ships a free *limited* license | Capped at 2000 vars / 2000 constraints — a calendar year fits |
| **SCIP** | LP branch-and-cut | Fully open source (Apache) | The strongest freely available MILP solver; no license, no size cap |
| **OR-Tools (CP-SAT)** | Constraint programming / SAT | Fully open source (Apache) | No license, no size cap; a different algorithm from the LP solvers |

Enable the **Benchmark all available solvers** option to solve the same problem
with every installed engine and compare solve time, objective, and the chosen
schedule. For a problem this small, all engines reach the **same optimal
objective** — the benchmark's value is comparing speed and revealing when the
optimum is *not unique* (different engines pick different, equally-optimal days).

Only Xpress is required to run the app. The others are optional:
```bash
pip install gurobipy pyscipopt ortools   # adds Gurobi, SCIP, and OR-Tools CP-SAT
```

## Household coordination (Consensus Planning Protocol)

Household mode coordinates several people's PTO so they maximize the days they
are off **together**, using the **Consensus Planning Protocol (CPP)** — a
distributed-optimization method (consensus ADMM / dual decomposition). Instead
of pooling everyone's data into one model, CPP treats each person as an
independent **agent**:

- Each person's budget, country holidays, pre-booked days and vacation style
  stay **private** to their own solver — the coordinator never sees them.
- The only shared quantity is which calendar days the household is off together.
- A central coordinator vends per-day "prices" and each person re-optimizes
  privately; over a few rounds the prices pull everyone's breaks into alignment.
  "Days off" is a common currency across people, which is exactly what CPP needs
  to trade value between agents.

Under the hood each person is solved by the **same single-person model** above
(their existing backend), with one extra per-day price term in the objective —
so nothing about the core optimization changes. Because the per-person problems
are integer programs, the coordinator keeps the **best schedule it observes**,
which is always at least as good as everyone planning independently.

Try it headlessly (a US + UK couple with different budgets):

```bash
python -m app.demos.consensus_demo
```

> Coordination only helps when calendars actually differ — two identical people
> over a full year already share every weekend and holiday, so the gain is zero.
> Different countries, budgets, or pre-booked days are what create room to
> coordinate.

## Technical Appendix: LP Formulation

We optimize which days to take leave in order to maximize total break time
(weekends, public holidays, and allocated leave days), while respecting
a leave budget and encouraging longer continuous breaks.

#### Sets and Indexing

- $D$ : ordered set of dates in the planning horizon  
- $H \subseteq D$ : set of dates that are weekends or public holidays  
- $P \subseteq D$ : set of dates pre-booked as leave  
- For convenience, we denote by $d^+$ the next day after $d$ in $D$
  (i.e. the successor of $d$ in the ordered set).

#### Parameters

- $L \in \mathbb{Z}_{\ge 0}$ : total number of leave days available  
- $\alpha \in \mathbb{R}_{\ge 0}$ : adjacency weight (bonus for consecutive break days)  
- $K \in \mathbb{Z}_{\ge 1} \cup \{\infty\}$ : optional cap on the length of any
  continuous break ($K = \infty$ means uncapped). This is what the UI's
  vacation-style presets set.

#### Decision Variables

For each day $d \in D$:

- $l_d \in \{0,1\}$  
  - $l_d = 1$ if we take leave on day $d$  
- $b_d \in \{0,1\}$  
  - $b_d = 1$ if day $d$ is a break day
    (weekend/holiday or leave on a weekday)

For each day $d \in D$ except the last:

- $a_d \in \{0,1\}$  
  - $a_d = 1$ if both $d$ and its successor $d^+$ are break days
    (used to reward consecutive breaks)

#### Objective

Maximize the total number of break days plus an adjacency bonus for consecutive break sequences:

```
max: Σ(b_d for d in D) + α·Σ(a_d for d in D\{last day})
```

Where:
- `b_d` = 1 if day d is a break day, 0 otherwise
- `a_d` = 1 if both day d and d+1 are break days (adjacency bonus)
- `α` = adjacency weight parameter

#### Constraints

**1. Pre-booked leave must be honored**

For all days `d` in pre-booked set `P`:
```
l_d = 1
```

**2. Leave budget**

Total leave days cannot exceed available budget `L`:
```
Σ(l_d for d in D) ≤ L
```

**3. Break-day logic**

- Weekends and public holidays (set `H`) are always break days:
  ```
  b_d = 1  for all d in H
  ```

- Weekdays can only become break days if leave is taken:
  ```
  b_d ≤ l_d  for all d in D\H
  ```

**4. Adjacency (consecutive break days)**

For each day `d` with a successor `d+`:
```
a_d ≤ b_d
a_d ≤ b_(d+)
a_d ≥ b_d + b_(d+) - 1
```

These three constraints linearize the logical AND condition: `a_d = b_d AND b_(d+)`, ensuring `a_d = 1` if and only if both `b_d` and `b_(d+)` are 1.

**5. Max-stretch cap (controls break length)**

When `K < ∞`, no run of `K+1` consecutive break days is allowed. For every
window `W` of `K+1` consecutive dates that contains at least one weekday
(non-fixed-break) day:
```
Σ(b_d for d in W) ≤ K
```
Windows made up *entirely* of weekends/holidays are skipped: such a window is
already all breaks by constraint (3) and capping it would be infeasible.
Skipping them leaves a pre-existing forced holiday run (e.g. a long public-
holiday bridge) untouched, while still preventing *leave* from creating or
extending a run beyond `K`. This keeps the model feasible for any `K ≥ 1`.

> **Why a cap and not just `α`?** Because every leave day adds exactly one break
> day at no cost, the total number of break days is fixed by the budget. The
> objective's first term is therefore constant at the optimum, and maximizing
> the adjacency term reduces to *minimizing the number of break stretches* —
> i.e. clustering maximally. So any `α > 0` produces the same maximally-clustered
> schedule: `α` is a **threshold** (cluster vs. don't), not a length dial. To
> target a specific break length you must constrain it, which is what `K` does.

#### Variable Domains

- **Leave variables** `l_d ∈ {0,1}` for all `d ∈ D`
- **Break variables** `b_d ∈ {0,1}` for all `d ∈ D`  
- **Adjacency variables** `a_d ∈ {0,1}` for all `d ∈ D` with successor

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

**Note**: This tool is for planning purposes only. Always confirm your vacation plans with your employer and respect company policies.
