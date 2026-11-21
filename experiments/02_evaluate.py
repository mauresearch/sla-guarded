"""Main evaluation on the test seeds.

Runs (tag in the output):
  frontier       every tuned policy at every hysteresis/margin setting
                 (used for the selected-setting results and the Pareto frontiers)
  alpha          SLA-Guarded at alpha = 0.25 and 0.75
  ablation       SLA-Guarded with one component removed
  rule_baseline  baselines with their own capacity rule

Output: results/main_eval.json
"""

from common import (
    ABLATIONS,
    HYSTERESIS,
    RULE_POLICIES,
    TEST_SEEDS,
    TUNED_HYSTERESIS,
    TUNED_MARGINS,
    TUNED_POLICIES,
    parallel_map,
    sg,
    sim_config,
    summary_row,
)


def job(a):
    policy, alpha, hyst, margin, seed, tag = a
    s = sg.run_policy(
        policy, seed=seed, sim_config=sim_config(alpha), hysteresis=HYSTERESIS[hyst], guardrail_margin=margin
    )
    return dict(tag=tag, policy=policy, alpha=alpha, hyst=hyst, margin=margin, seed=seed, **summary_row(s))


if __name__ == "__main__":
    jobs = []
    for p, a in TUNED_POLICIES:
        for h in TUNED_HYSTERESIS:
            for m in TUNED_MARGINS:
                jobs += [(p, a, h, m, s, "frontier") for s in TEST_SEEDS]
    for a in [0.25, 0.75]:
        jobs += [("SLA_Guarded", a, "rel0.75", 2.0, s, "alpha") for s in TEST_SEEDS]
    for p in ABLATIONS:
        margin = 1.0 if p == "no_margin" else 2.0
        jobs += [(p, 0.5, "rel0.75", margin, s, "ablation") for s in TEST_SEEDS]
    for p in RULE_POLICIES:
        jobs += [(p, 0.5, "none", 1.5, s, "rule_baseline") for s in TEST_SEEDS]
    parallel_map(job, jobs, "main_eval.json")
