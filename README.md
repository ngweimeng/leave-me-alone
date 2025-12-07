# Leave Optimizer

> Scientifically maximize your vacation time using linear programming, public holidays, and strategic PTO allocation.

A Streamlit application that uses FICO Xpress optimization to help you get the most continuous time off by strategically placing your paid time off (PTO) days adjacent to weekends and public holidays.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.0+-red.svg)](https://streamlit.io)

## Features

- **Smart Optimization**: Uses linear programming (MILP) to maximize consecutive break days
- **Vacation Style Presets**: Choose from balanced mix, long weekends, mini breaks, week-long vacations, or extended vacations
- **Public Holiday Integration**: Automatically fetches public holidays for 100+ countries via the `holidays` library
- **Pre-booked Days**: Constrain the optimizer around days you've already committed to taking off
- **Additional Time Off**: Add company-wide holidays, personal days, or other non-PTO time off

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

## Development

### Running Tests

```bash
make test
# or
pytest -q
```

### Code Formatting

```bash
make fmt
# or
black app tests
```

### Architecture Overview

The application follows a clean architecture pattern:

- **UI Layer** (`main.py`): Orchestrates the step-by-step user flow
- **Components** (`components/`): Reusable UI widgets and visualizations
- **Services** (`services/`): Business logic and external integrations
- **Models** (`models/`): Type-safe data structures using Pydantic
- **State** (`state/`): Centralized session state management

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

**Note**: This tool is for planning purposes only. Always confirm your vacation plans with your employer and respect company policies.
