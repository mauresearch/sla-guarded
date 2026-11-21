"""Joint sensitivity of SLA-Guarded: 300 Latin-hypercube samples over eight
parameters (hysteresis band, safety margin, RTT budget, alpha, churn penalty,
cold-start delay, horizon, maximum utilisation).

Output: results/lhs.json
"""

import numpy as np

from common import QUICK, parallel_map, sg, sim_config

N_SAMPLES = 16 if QUICK else 300
PARAMS = ["low", "margin", "rtt", "alpha", "eta", "warm", "H", "umax"]


def job(a):
    sc = sim_config(a["alpha"])
    sc.rtt_budget_ms = a["rtt"]
    sc.horizon_steps = a["H"]
    s = sg.run_policy(
        "SLA_Guarded",
        seed=a["seed"],
        sim_config=sc,
        hysteresis=dict(mode="relative", low_ratio=a["low"], high_ratio=2 * a["low"]),
        guardrail_margin=a["margin"],
        warmup_steps=a["warm"],
        mpc_overrides=dict(eta=a["eta"], max_utilization=a["umax"]),
    )
    out = dict(a)
    out.update(
        isvr=s["SLO_Violation_Rate"],
        rsvr=s["Request_Violation_Rate"],
        cost=s["Total_Cost_USD"],
        carbon=s["Total_Carbon_g"] / 1e6,
        scal=s["Scaling_Changes"],
        k=s["Mean_Provisioned_k"],
    )
    return out


def latin_hypercube(n, rng):
    return {p: (rng.permutation(n) + rng.random(n)) / n for p in PARAMS}


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    n = 300
    U = latin_hypercube(n, rng)
    jobs = [
        dict(
            i=i,
            seed=i % 10,
            low=0.3 + 0.7 * U["low"][i],
            margin=1.2 + 1.8 * U["margin"][i],
            rtt=5 + 75 * U["rtt"][i],
            alpha=U["alpha"][i],
            eta=0.1 * U["eta"][i],
            warm=int(min(8, np.floor(9 * U["warm"][i]))),
            H=int(1 + np.floor(32 * U["H"][i])),
            umax=0.80 + 0.15 * U["umax"][i],
        )
        for i in range(n)
    ][:N_SAMPLES]
    parallel_map(job, jobs, "lhs.json")
