"""Interval-level vs request-level SLO accounting and sensitivity of the
interval metric to the aggregation window (30, 60 and 120 s).

For a window of w intervals, the window violates the SLO if the
load-weighted mixture of per-region M/M/k tails gives P(TTFT > 3 s) > 1% or
P(latency > 30 s) > 1% over all requests of the window.

Output: results/window.json
"""

import numpy as np

from common import HYSTERESIS, TEST_SEEDS, parallel_map, selected_settings, setting, sg, sim_config

POLICIES = [
    ("SLA_Guarded", 0.5),
    ("SLA_Guarded", 0.0),
    ("SLA_Guarded_InvWeight", 0.5),
    ("CostFirst+H", 0.5),
    ("RoundRobin+H", 0.5),
]


def job(a):
    policy, alpha, hyst, margin, seed = a
    ec = sg.ErlangC()
    s, h = sg.run_policy(
        policy,
        seed=seed,
        sim_config=sim_config(alpha),
        hysteresis=HYSTERESIS[hyst],
        guardrail_margin=margin,
        return_history=True,
    )
    regions, _ = sg.create_default_topology()
    mu = {r.name: r.mu for r in regions}
    rtt = {r.name: r.rtt / 1000 for r in regions}
    L, A = h["lambda_per_region"], h["available_k_per_region"]
    req = np.array(h["total_requests_per_step"])

    def tail(steps, x, offset):
        tot = sum(L[t][r] for t in steps for r in mu)
        if tot <= 0:
            return 0.0
        acc = 0.0
        for t in steps:
            for r in mu:
                lam = L[t][r]
                if lam > 0:
                    acc += lam * ec.prob_wait_exceeds(lam, mu[r], max(1, A[t][r]), x - offset(r) - rtt[r])
        return acc / tot

    def violated(steps):
        return int(tail(steps, 3.0, lambda r: 0.8) > 0.01 or tail(steps, 30.0, lambda r: 1 / mu[r]) > 0.01)

    out = dict(
        policy=policy,
        alpha=alpha,
        seed=seed,
        isvr_reported=s["SLO_Violation_Rate"],
        rsvr=s["Request_Violation_Rate"],
        req_mean=float(req.mean()),
        req_p5=float(np.percentile(req, 5)),
        req_min=float(req.min()),
        frac_lt100=float((req < 100).mean()),
    )
    n = len(L)
    for w in [1, 2, 4]:
        out[f"isvr_pooled_{30 * w}s"] = float(
            np.mean([violated(range(i, min(i + w, n))) for i in range(0, n, w)])
        )
    return out


if __name__ == "__main__":
    table = selected_settings()
    jobs = [(p, a, *setting(p, a, table), s) for p, a in POLICIES for s in TEST_SEEDS]
    parallel_map(job, jobs, "window.json", chunksize=1)
