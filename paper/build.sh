#!/usr/bin/env bash
# Regenerate results -> tables/figures -> compile the paper.
# Run from the repo root or anywhere; paths are resolved relative to this file.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

# 1. (Re)run experiments only if asked; the JSON is committed so the paper
#    builds without solvers installed. Pass --rerun to regenerate numbers.
if [[ "${1:-}" == "--rerun" ]]; then
  echo "==> running experiments (needs the solver backends installed)"
  python paper/experiments/run_experiments.py --repeats 7 --scaling-time-limit 15
fi

echo "==> generating LaTeX tables"
python paper/experiments/make_tables.py

echo "==> generating figures (needs matplotlib)"
python paper/experiments/make_figures.py

echo "==> compiling main.tex"
cd "$HERE"
if command -v tectonic >/dev/null 2>&1; then
  tectonic main.tex
elif command -v latexmk >/dev/null 2>&1; then
  latexmk -pdf -bibtex main.tex
else
  pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
fi
echo "==> done: $HERE/main.pdf"
