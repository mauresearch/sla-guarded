"""Shared settings and helpers for the experiment scripts."""

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sla_guarded import simulator as sg  # noqa: E402

# QUICK=1 runs a reduced smoke test (fewer seeds, 2 simulated hours) and
# writes to results_quick/ so that the full results are never overwritten.
QUICK = os.environ.get("QUICK", "0") == "1"
RESULTS = ROOT / ("results_quick" if QUICK else "results")
RESULTS.mkdir(exist_ok=True)
DATA = ROOT / "data" / "azure_llm_traces"
WORKERS = int(os.environ.get("WORKERS", os.cpu_count() or 1))

TEST_SEEDS = list(range(2)) if QUICK else list(range(10))
VALIDATION_SEEDS = [100] if QUICK else [100, 101, 102]
QUICK_STEPS = 240

HYSTERESIS = {
    "none": None,
    "rel0.5": dict(mode="relative", low_ratio=0.5, high_ratio=1.0),
    "rel0.75": dict(mode="relative", low_ratio=0.75, high_ratio=1.5),
    "abs2048": dict(mode="absolute", ref_capacity=2048),
    "abs4096": dict(mode="absolute", ref_capacity=4096),
}
TUNED_HYSTERESIS = ["rel0.5", "rel0.75", "abs2048", "abs4096"]
TUNED_MARGINS = [1.5, 2.0, 2.5]

# (policy, alpha) pairs whose hysteresis band and safety margin are tuned
# on the validation seeds with the same protocol.
TUNED_POLICIES = [
    ("SLA_Guarded", 0.0),
    ("SLA_Guarded", 0.5),
    ("SLA_Guarded", 1.0),
    ("SLA_Guarded_InvWeight", 0.5),
    ("CostFirst+H", 0.5),
    ("RoundRobin+H", 0.5),
    ("CarbonFirst+H", 0.5),
    ("LatencyFirst+H", 0.5),
]
RULE_POLICIES = [
    "LatencyFirst",
    "CostFirst",
    "CarbonFirst",
    "RoundRobin",
    "QLM_style",
    "SOLA_style",
    "ThresholdBased",
    "HPA_Stab",
    "CarbonAdvisor_Style",
]
ABLATIONS = ["no_guardrail", "no_prediction", "no_hysteresis", "no_margin", "no_prewarm", "with_spreading"]
SLO_TARGET = 0.05


def sim_config(alpha=0.5, steps=None):
    sc = sg.SimulationConfig()
    sc.alpha_tradeoff = alpha
    if steps is not None:
        sc.total_steps = steps
    elif QUICK:
        sc.total_steps = QUICK_STEPS
    return sc


def selected_settings():
    path = RESULTS / "selected_settings.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run experiments/01_tune.py first")
    return pd.read_csv(path)


def setting(policy, alpha, table=None):
    """Tuned (hysteresis, margin) of a policy; rule-based baselines use none/1.5."""
    table = selected_settings() if table is None else table
    row = table[(table.policy == policy) & (table.alpha == alpha)]
    if len(row):
        return row.iloc[0].hyst, float(row.iloc[0].margin)
    if policy.startswith("SLA_Guarded"):
        return "rel0.75", 2.0
    return "none", 1.5


def summary_row(s):
    return dict(
        isvr=s["SLO_Violation_Rate"],
        rsvr=s["Request_Violation_Rate"],
        cost=s["Total_Cost_USD"],
        carbon=s["Total_Carbon_g"] / 1e6,
        scal=s["Scaling_Changes"],
        rout=s["Routing_Changes"],
        k=s["Mean_Provisioned_k"],
        p99=s["Avg_p99_Latency_ms"],
        ttft=s["Avg_p99_TTFT_ms"],
        cost_per_ok=s["Cost_per_Success_USD"],
        carbon_per_ok=s["Carbon_per_Success_g"],
    )


def parallel_map(fn, jobs, out_name, chunksize=4, every=100):
    """Run jobs in parallel and save the list of results as JSON in RESULTS."""
    out_path = RESULTS / out_name
    out = []
    print(f"{out_name}: {len(jobs)} runs on {WORKERS} workers", flush=True)
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        for i, r in enumerate(ex.map(fn, jobs, chunksize=chunksize)):
            out.append(r)
            if i % every == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
                json.dump(out, open(out_path, "w"))
    json.dump(out, open(out_path, "w"))
    print(f"  saved {out_path}", flush=True)
    return out
