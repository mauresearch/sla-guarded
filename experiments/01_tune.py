"""Tune the hysteresis band and safety margin of every hysteresis-equipped
policy on the validation seeds, with the same protocol for all policies.

Selection rule: among the settings whose mean interval SLO violation is at
most 5%, pick the cheapest; if none meets the target, pick the most reliable.

Outputs: results/tuning.json, results/selected_settings.csv
"""

import json

import pandas as pd

from common import (
    HYSTERESIS,
    RESULTS,
    SLO_TARGET,
    TUNED_HYSTERESIS,
    TUNED_MARGINS,
    TUNED_POLICIES,
    VALIDATION_SEEDS,
    parallel_map,
    sg,
    sim_config,
)


def job(a):
    policy, alpha, hyst, margin, seed = a
    s = sg.run_policy(
        policy, seed=seed, sim_config=sim_config(alpha), hysteresis=HYSTERESIS[hyst], guardrail_margin=margin
    )
    return dict(
        policy=policy,
        alpha=alpha,
        hyst=hyst,
        margin=margin,
        seed=seed,
        isvr=s["SLO_Violation_Rate"],
        rsvr=s["Request_Violation_Rate"],
        cost=s["Total_Cost_USD"],
        carbon=s["Total_Carbon_g"] / 1e6,
    )


def select(results):
    d = pd.DataFrame(results)
    g = (
        d.groupby(["policy", "alpha", "hyst", "margin"])[["isvr", "rsvr", "cost", "carbon"]]
        .mean()
        .reset_index()
    )
    rows = []
    for _, x in g.groupby(["policy", "alpha"]):
        ok = x[x.isvr <= SLO_TARGET]
        rows.append(ok.sort_values("cost").iloc[0] if len(ok) else x.sort_values("isvr").iloc[0])
    return pd.DataFrame(rows)


if __name__ == "__main__":
    jobs = [
        (p, a, h, m, s)
        for (p, a) in TUNED_POLICIES
        for h in TUNED_HYSTERESIS
        for m in TUNED_MARGINS
        for s in VALIDATION_SEEDS
    ]
    results = parallel_map(job, jobs, "tuning.json")
    sel = select(json.load(open(RESULTS / "tuning.json")))
    sel.to_csv(RESULTS / "selected_settings.csv", index=False)
    print(sel.to_string(index=False))
