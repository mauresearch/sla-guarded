#!/usr/bin/env bash
# Reproduce all experiments, tables and figures.
#
#   ./run_all.sh            full run (results/, several hours on a multi-core machine)
#   QUICK=1 ./run_all.sh    smoke test with fewer seeds and shorter runs (results_quick/)
#   WORKERS=8 ./run_all.sh  limit the number of parallel processes
#
# The tables and figures can also be rebuilt from the provided results without
# re-running the experiments:
#   python analysis/make_tables.py && python analysis/make_figures.py
set -euo pipefail
cd "$(dirname "$0")"

python experiments/01_tune.py
python experiments/02_evaluate.py
python experiments/03_coldstart.py
python experiments/04_sensitivity.py
python experiments/05_latency_validation.py
python experiments/06_window.py
python experiments/07_scalability.py
python experiments/09_trace_eval.py week
python experiments/09_trace_eval.py short
python experiments/09_trace_eval.py alpha0

if [ "${QUICK:-0}" = "1" ]; then
  python analysis/make_tables.py results_quick
else
  python analysis/make_tables.py
  python analysis/make_figures.py
fi
