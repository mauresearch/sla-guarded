"""Scalability of SLA-Guarded on generated topologies with 4-128 regions and
an equal number of user clusters (3 topology seeds, 24 h each): control-loop
time per interval (total and per stage) and service quality.

Output: results/scalability.json
"""

import json

import numpy as np

from common import QUICK, RESULTS, sg, sim_config

SIZES = [4, 8, 16] if QUICK else [4, 8, 16, 32, 64, 128]
SEEDS = [0] if QUICK else [0, 1, 2]
HYST = dict(mode="relative", low_ratio=0.75, high_ratio=1.5)
WARM_INTERVALS = 120  # first simulated hour, reported separately

if __name__ == "__main__":
    out = []
    for n in SIZES:
        for seed in SEEDS:
            regions, clusters = sg.create_scaled_topology(n, n, seed=seed, max_k=4096)
            rng = np.random.RandomState(seed)
            base = {c.name: float(rng.uniform(8, 15)) for c in clusters}
            sc = sim_config(0.5)
            s, h = sg.run_policy(
                "SLA_Guarded",
                seed=seed,
                sim_config=sc,
                hysteresis=HYST,
                guardrail_margin=2.0,
                topology=(regions, clusters, base),
                profile=True,
                return_history=True,
            )
            v = np.array(h["slo_violation"])
            r = dict(
                n_regions=n,
                seed=seed,
                steps=sc.total_steps,
                isvr=float(v.mean()),
                isvr_after_1h=float(v[WARM_INTERVALS:].mean()) if len(v) > WARM_INTERVALS else float("nan"),
                rsvr=s["Request_Violation_Rate"],
                cost=s["Total_Cost_USD"],
                mean_step_ms=s["Mean_Step_ms"],
                p99_step_ms=s["P99_Step_ms"],
                regions_used=float(
                    np.mean([sum(1 for x in d.values() if x > 0.01) for d in h["lambda_per_region"]])
                ),
                **{k: v_ for k, v_ in s.items() if k.startswith("Stage_")}
            )
            out.append(r)
            print(r, flush=True)
            json.dump(out, open(RESULTS / "scalability.json", "w"))
