"""Sensitivity to capacity cold start.

  sweep     fixed cold-start delay of 0, 30, 60, 120 and 240 s (0-8 intervals)
  variants  alternative cold-start models at the default 60 s:
              ln60        log-normal start-up time, mean 60 s (sigma 0.5)
              ln120       log-normal start-up time, mean 120 s
              sd2         scale-downs take effect after 60 s
              bill_ready  capacity is billed only once it is ready

Output: results/coldstart.json
"""

import numpy as np

from common import HYSTERESIS, TEST_SEEDS, parallel_map, selected_settings, setting, sg, sim_config

SWEEP_POLICIES = [
    ("SLA_Guarded", 0.5),
    ("SLA_Guarded", 0.0),
    ("SLA_Guarded_InvWeight", 0.5),
    ("CostFirst+H", 0.5),
    ("RoundRobin+H", 0.5),
    ("CarbonFirst+H", 0.5),
    ("LatencyFirst+H", 0.5),
    ("LatencyFirst", 0.5),
    ("CostFirst", 0.5),
    ("SOLA_style", 0.5),
    ("HPA_Stab", 0.5),
]
VARIANT_POLICIES = [
    ("SLA_Guarded", 0.5),
    ("SLA_Guarded_InvWeight", 0.5),
    ("CostFirst+H", 0.5),
    ("RoundRobin+H", 0.5),
]
WARMUP_STEPS = [0, 1, 2, 4, 8]


def lognormal_steps(mean_steps, sigma=0.5):
    mu = np.log(mean_steps) - sigma**2 / 2
    return lambda rng: int(round(rng.lognormal(mu, sigma)))


def job(a):
    kw = {}
    v = a.get("variant")
    if v == "ln60":
        kw["warmup_sampler"] = lognormal_steps(2)
    elif v == "ln120":
        kw["warmup_sampler"] = lognormal_steps(4)
    elif v == "sd2":
        kw["scaledown_delay_steps"] = 2
    elif v == "bill_ready":
        kw["bill_from_launch"] = False
    s = sg.run_policy(
        a["policy"],
        seed=a["seed"],
        sim_config=sim_config(a["alpha"]),
        hysteresis=HYSTERESIS[a["hyst"]],
        guardrail_margin=a["margin"],
        warmup_steps=a.get("warm", 2),
        sim_kwargs=kw,
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


if __name__ == "__main__":
    table = selected_settings()
    jobs = []
    for p, al in SWEEP_POLICIES:
        h, m = setting(p, al, table)
        for w in WARMUP_STEPS:
            jobs += [
                dict(kind="sweep", policy=p, alpha=al, hyst=h, margin=m, warm=w, seed=s) for s in TEST_SEEDS
            ]
    for p, al in VARIANT_POLICIES:
        h, m = setting(p, al, table)
        for v in ["ln60", "ln120", "sd2", "bill_ready"]:
            jobs += [
                dict(kind="variant", policy=p, alpha=al, hyst=h, margin=m, variant=v, seed=s)
                for s in TEST_SEEDS
            ]
    parallel_map(job, jobs, "coldstart.json")
