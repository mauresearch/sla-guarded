"""Trace-driven evaluation on the Azure LLM inference traces.

Arrivals are the per-30 s request counts of the trace, split over the user
clusters with a multinomial draw in proportion to their base rates. The mean
response length of the trace sets the service rate. Prices and carbon
intensity follow the same synthetic model as the main evaluation, indexed by
the time of day of the trace.

Modes:
  week    2024 one-week traces, 7 daily windows (each preceded by a 1 h warm-up
          that is excluded), at the recorded rate and at 2x the rate
  short   2023 one-hour traces, 10 seeds, transient start and a 10 min
          preconditioning period (excluded)
  alpha0  SLA-Guarded (alpha = 0) on the 2024 conversation trace with
          alternative hysteresis bands and margins

Usage: python experiments/09_trace_eval.py week|short|alpha0
Outputs: results/trace_week.json, results/trace_short.json, results/trace_alpha0.json
"""

import sys

import numpy as np
import pandas as pd

from common import DATA, HYSTERESIS, QUICK, parallel_map, selected_settings, setting, sg

POLICIES = [
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
DAY = 2880
WARMUP = 120
_BINS = {}
_TABLE = None


def bins(name):
    """Request counts per 30 s bin from the first non-empty bin, mean response
    length, and the index of the first bin (time-of-day offset)."""
    if name not in _BINS:
        b = pd.read_csv(DATA / f"{name}.csv")
        b0 = int(b.bin.min())
        counts = np.zeros(int(b.bin.max()) - b0 + 1)
        counts[b.bin.values.astype(int) - b0] = b.requests.values
        _BINS[name] = (counts, float(b.gen_tokens.sum() / b.requests.sum()), b0)
    return _BINS[name]


class BinWorkload:
    def __init__(self, counts, clusters, base, seed, scale):
        w = np.array([base[c.name] for c in clusters], float)
        w /= w.sum()
        rng = np.random.default_rng(seed)
        self.names = [c.name for c in clusters]
        self.split = np.array([rng.multinomial(int(round(n * scale)), w) for n in counts])

    def sample_arrival_rates(self, step=None):
        return {n: float(self.split[step, i]) / 30.0 for i, n in enumerate(self.names)}


class TimeOfDayPrices:
    """Synthetic price and carbon model of the main evaluation, indexed by hour of day."""

    def __init__(self, regions, n, offset_s, seed):
        rng = np.random.RandomState(seed)
        h = ((offset_s + np.arange(n) * 30) / 3600.0) % 24
        shared = rng.randn(n) * 0.02
        shared -= shared.mean()
        self.p, self.c = {}, {}
        for r in regions:
            noise_p = shared * 0.8 + rng.randn(n) * 0.03
            self.p[r.name] = r.price_trace * np.clip(
                1 + 0.35 * np.exp(-0.5 * (h - 18.5) ** 2 / 4) + noise_p, 0.5, 2.5
            )
            gas = 0.12 * np.exp(-0.5 * (h - 19) ** 2 / 2) * (noise_p > 0)
            noise_c = shared * 0.5 + rng.randn(n) * 0.04
            self.c[r.name] = r.carbon_trace * np.clip(
                1 - 0.45 * np.exp(-0.5 * (h - 12.5) ** 2 / 3.5) + noise_c + gas, 0.3, 2.0
            )

    def get(self, t):
        return {k: v[t] for k, v in self.p.items()}, {k: v[t] for k, v in self.c.items()}


def run(a):
    global _TABLE
    policy, alpha = a["policy"], a["alpha"]
    if "hyst" in a:
        hyst, margin = a["hyst"], a["margin"]
    else:
        if _TABLE is None:
            _TABLE = selected_settings()
        hyst, margin = setting(policy, alpha, _TABLE)
    counts, resp_tokens, b0 = bins(a["trace"])
    seg = counts[a["start"] : a["start"] + a["n"]]
    pre = a.get("precond", 0)
    if pre:
        seg = np.concatenate([counts[a["start"] : a["start"] + pre], seg])
    n = len(seg)
    sc = sg.SimulationConfig()
    sc.alpha_tradeoff = alpha
    sc.total_steps = n
    regions, clusters = sg.create_default_topology(avg_response_tokens=resp_tokens)
    base = sg._base_lambda_per_cluster()
    guards = sg.build_guardrail_calculators(regions, sc, safety_margin=margin)
    sim = sg.SLASimulator(
        sim_config=sc,
        sla_controller=sg.make_controller(policy, sc, HYSTERESIS[hyst]),
        regions=regions,
        clusters=clusters,
        energy_model=sg.EnergyCostCarbonModel(interval_seconds=30, busy_power=180.0, idle_power=120.0),
        base_lambda_per_cluster=base,
        guardrail_calculator=guards,
        rtt_budget_ms=sc.rtt_budget_ms,
        policy_name=policy,
        trace_seed=a["seed"],
        warmup_steps=2,
    )
    sim.trace_generator = TimeOfDayPrices(regions, n, (b0 + a["start"] - pre) * 30, a["seed"])
    sim.workload_gen = BinWorkload(seg, clusters, base, a["seed"], a.get("scale", 1.0))
    np.random.seed(a["seed"])
    sim.current_step = 0
    for _ in range(n):
        sim._run_single_step()
    h = sim.history
    w = a.get("exclude", 0)
    v = np.array(h["slo_violation"])[w:]
    req = np.array(h["total_requests_per_step"])[w:]
    vr = np.array(h["violating_requests_per_step"])[w:]
    out = dict(a)
    out.update(
        hyst=hyst,
        margin=margin,
        isvr=float(v.mean()),
        rsvr=float(vr.sum() / max(req.sum(), 1e-9)),
        cost=float(np.sum(h["total_cost_usd"][w:])),
        carbon=float(np.sum(h["total_carbon_g"][w:]) / 1e6),
        scal=int(np.sum(h["scaling_changes"][w:])),
        req=float(req.sum()),
        resp_tokens=resp_tokens,
        mean_rate=float(req.sum() / (len(req) * 30)),
    )
    return out


def day_window(d):
    """Day d of the week, preceded by a one-hour warm-up (none for the first day)."""
    start = max(0, d * DAY - WARMUP)
    return dict(start=start, n=DAY + WARMUP if d > 0 else DAY, exclude=WARMUP, day=d, seed=d)


if __name__ == "__main__":
    mode = sys.argv[1]
    days = range(1) if QUICK else range(7)
    seeds = range(2) if QUICK else range(10)
    jobs = []
    if mode == "week":
        for tr in ["conv_1week", "code_1week"]:
            for scale in [1.0, 2.0]:
                for d in days:
                    for p, al in POLICIES:
                        jobs.append(dict(trace=tr, scale=scale, policy=p, alpha=al, **day_window(d)))
    elif mode == "short":
        for tr in ["conv", "code"]:
            nb = len(bins(tr)[0])
            for s in seeds:
                for p, al in POLICIES:
                    jobs.append(
                        dict(
                            trace=tr,
                            protocol="transient",
                            start=0,
                            n=nb,
                            exclude=0,
                            seed=s,
                            policy=p,
                            alpha=al,
                        )
                    )
                    jobs.append(
                        dict(
                            trace=tr,
                            protocol="preconditioned",
                            start=0,
                            n=nb,
                            precond=20,
                            exclude=20,
                            seed=s,
                            policy=p,
                            alpha=al,
                        )
                    )
    elif mode == "alpha0":
        for hyst, margin in [("rel0.75", 1.5), ("rel0.5", 1.5), ("rel0.5", 2.0), ("rel0.75", 2.0)]:
            for d in days:
                jobs.append(
                    dict(
                        trace="conv_1week",
                        scale=1.0,
                        policy="SLA_Guarded",
                        alpha=0.0,
                        hyst=hyst,
                        margin=margin,
                        **day_window(d),
                    )
                )
    else:
        sys.exit("mode must be week, short or alpha0")
    parallel_map(run, jobs, f"trace_{mode}.json", chunksize=2, every=25)
