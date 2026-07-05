# Paper: *Leave Me Alone — A Binary Integer Program for Maximizing Continuous Time Off*

A short (5-page, two-column) workshop-style paper on the PTO-optimization model
that powers this repo: the binary-IP formulation, its structural properties, and
a reproducible four-solver benchmark.

## Layout

```
paper/
├── main.tex                 # the paper (two-column article)
├── references.bib           # bibliography
├── build.sh                 # results → tables/figures → PDF
├── results/
│   └── results.json         # measured numbers (committed; regenerate with --rerun)
├── tables/                  # \input-able LaTeX fragments, auto-generated
│   ├── tab_comparison.tex
│   ├── tab_scaling.tex
│   ├── tab_alpha.tex
│   ├── tab_max_stretch.tex
│   └── tab_leverage.tex
├── figures/                 # vector PDFs, auto-generated
│   ├── fig_scaling.pdf
│   ├── fig_alpha.pdf
│   ├── fig_max_stretch.pdf
│   └── fig_leverage.pdf
└── experiments/
    ├── run_experiments.py   # runs the 4 experiments via the app's solver layer
    ├── make_tables.py       # results.json → tables/*.tex
    └── make_figures.py      # results.json → figures/*.pdf
```

**Nothing in the tables or figures is hand-typed.** `run_experiments.py` calls
the same `app.services.solvers` backends the Streamlit app uses, writes
`results/results.json`, and `make_tables.py` / `make_figures.py` render from it.
Re-running regenerates every number, so the paper can never drift from the code.

## Build

The committed `results.json`, `tables/`, and `figures/` let you compile the PDF
without any solver installed:

```bash
cd paper
tectonic main.tex          # or: latexmk -pdf -bibtex main.tex
```

To regenerate the measurements first (needs the solver backends + matplotlib):

```bash
./paper/build.sh --rerun   # run experiments, rebuild tables/figures, compile
./paper/build.sh           # skip experiments, just rebuild tables/figures + PDF
```

## Overleaf

Upload the whole `paper/` folder to a new Overleaf project (drag-and-drop the
folder, or `git`-import the repo and set the project root to `paper/`). Set the
compiler to **pdfLaTeX** and the main document to `main.tex`. The `tables/` and
`figures/` files are committed, so it compiles immediately — no need to run the
Python on Overleaf.

## Reproducibility note

Timings in `results.json` were measured on Apple silicon (arm64), macOS, with
Xpress 9.8.1, Gurobi 12.0.3, SCIP (pyscipopt) 6.2.1, and OR-Tools 9.15. Each
solver runs in its default configuration. Absolute times will differ on other
hardware; the qualitative findings (objective ties, schedule divergence,
license-cap behavior, the α threshold, and the max-stretch cap as the true
length dial) are hardware-independent.
