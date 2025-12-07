# Leave-Me-Alone: PTO Optimizer

> Scientifically maximize your vacation time using linear programming, public holidays, and strategic PTO allocation.

A Streamlit application that uses FICO Xpress optimization to help you get the most continuous time off by strategically placing your paid time off (PTO) days adjacent to weekends and public holidays.

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
./check.sh
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

### Step-by-Step Guide

1. **Enter PTO Days**: Input how many paid time-off days you have available

2. **Select Timeframe**: Choose your planning period (calendar year or custom 12-month period)

3. **Configure Public Holidays**: 
   - Select your country from 100+ supported countries
   - Review and edit the holiday list in an interactive table
   - Select/deselect specific holidays

4. **Choose Vacation Style**: Pick a preset that matches your preference:
   - **Recommended (Balanced Mix)** - Smart blend of short and long breaks
   - **Long Weekends** - More 3-4 day weekends
   - **Mini Breaks** - Several 5-6 day breaks
   - **Week-long Breaks** - Focused 7-9 day vacations
   - **Extended Vacations** - Longer 10-15 day getaways

5. **Add Pre-booked Days** (optional): Specify days you've already committed to

6. **Add Other Time Off** (optional): Include company holidays, personal days, etc.

7. **Optimize**: Click the "Optimize Break" button to generate your optimal schedule

8. **View Results**: See your optimized break calendar with:
   - Total break days achieved
   - PTO days used
   - Calendar heatmap visualization
   - Detailed breakdown of leave days

## Project Structure

```
leave-me-alone/
├── app/
│   ├── main.py                    # Main Streamlit orchestrator
│   ├── components/
│   │   ├── inputs.py              # Input components and request builder
│   │   ├── results_display.py    # Results visualization
│   │   └── calendar_heatmap.py   # Calendar heatmap rendering
│   ├── models/
│   │   └── leave_request.py      # Pydantic data models
│   ├── services/
│   │   ├── optimization_service.py # Optimizer wrapper
│   │   ├── leave_model.py         # MILP model implementation
│   │   └── holiday_service.py     # Holiday data fetching
│   ├── state/
│   │   └── session_manager.py     # Session state management
│   └── tests.py/
│       ├── test_holiday_service.py
│       ├── test_leave_model.py
│       └── test_optimization_service.py
├── requirements.txt               # Python dependencies
├── makefile                       # Common commands
├── LICENSE                        # Apache 2.0 license
└── README.md                      # This file
```

## Technical Appendix: Leave Optimization Model (Linear Programming Formulation)

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

#### Variable Domains

- **Leave variables** `l_d ∈ {0,1}` for all `d ∈ D`
- **Break variables** `b_d ∈ {0,1}` for all `d ∈ D`  
- **Adjacency variables** `a_d ∈ {0,1}` for all `d ∈ D` with successor

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

**Note**: This tool is for planning purposes only. Always confirm your vacation plans with your employer and respect company policies.
