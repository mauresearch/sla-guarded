"""Build all result tables from the JSON files in results/.

Writes one CSV per table to results/tables/ and a readable summary to
results/tables/tables.md.

Usage: python analysis/make_tables.py [results_dir]
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RES = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
OUT = RES / "tables"
OUT.mkdir(exist_ok=True)
MD = []

LABEL = {
    "SLA_Guarded_InvWeight": "Spreading variant (inverse-weight routing)",
    "no_guardrail": "w/o guardrail",
    "no_prediction": "w/o prediction",
    "no_hysteresis": "w/o hysteresis",
    "no_margin": "w/o safety margin (m=1)",
    "no_prewarm": "w/o cold-start-aware switching",
    "with_spreading": "with spreading (inverse-weight routing)",
}
REFERENCE = ("SLA_Guarded", 0.5)


def load(name):
    return pd.DataFrame(json.load(open(RES / name)))


def label(policy, alpha=None):
    if policy == "SLA_Guarded":
        return f"SLA-Guarded (alpha={alpha:g})"
    return LABEL.get(policy, policy)


def ci95(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float(x.mean()), float("nan")
    return float(x.mean()), float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))


def save(df, name, title):
    df.to_csv(OUT / f"{name}.csv", index=False)
    MD.append(f"## {title}\n\n{df.to_markdown(index=False)}\n")
    print(f"\n== {title}\n{df.to_string(index=False)}")


def summarize(g, ref=None):
    r = {}
    for m, scale in [("isvr", 100), ("rsvr", 100), ("cost", 1), ("carbon", 1)]:
        mean, ci = ci95(g[m] * scale)
        r[m], r[m + "_ci95"] = mean, ci
    r["p99_ttft_ms"] = g.ttft.mean()
    r["scaling_changes"] = g.scal.mean()
    if ref is not None:
        a, b = ref.set_index("seed"), g.set_index("seed")
        for m in ["isvr", "carbon"]:
            try:
                r["p_" + m] = stats.wilcoxon(a[m], b[m].loc[a.index]).pvalue
            except ValueError:
                r["p_" + m] = 1.0
    return r


# ---------------------------------------------------------------- main results
sel = pd.read_csv(RES / "selected_settings.csv")
ev = load("main_eval.json")
fr = ev[ev.tag == "frontier"]


def selected_runs(policy, alpha):
    s = sel[(sel.policy == policy) & (sel.alpha == alpha)].iloc[0]
    return fr[(fr.policy == policy) & (fr.alpha == alpha) & (fr.hyst == s.hyst) & (fr.margin == s.margin)]


ref = selected_runs(*REFERENCE)
rows = []
order = [
    ("SLA_Guarded", 0.5),
    ("SLA_Guarded", 0.0),
    ("SLA_Guarded", 1.0),
    ("SLA_Guarded_InvWeight", 0.5),
    ("LatencyFirst+H", 0.5),
    ("CostFirst+H", 0.5),
    ("CarbonFirst+H", 0.5),
    ("RoundRobin+H", 0.5),
]
for p, a in order:
    s = sel[(sel.policy == p) & (sel.alpha == a)].iloc[0]
    g = selected_runs(p, a)
    rows.append(
        dict(
            group="hysteresis-equipped",
            policy=label(p, a),
            setting=f"{s.hyst}, m={s.margin:g}",
            **summarize(g, None if (p, a) == REFERENCE else ref),
        )
    )
rb = ev[ev.tag == "rule_baseline"]
for p in rb.policy.unique():
    rows.append(dict(group="own capacity rule", policy=p, setting="-", **summarize(rb[rb.policy == p], ref)))
overall = pd.DataFrame(rows)
save(overall.round(3), "overall", "Overall comparison (test seeds, mean and 95% CI; violations in %)")

# ---------------------------------------------------------------- Pareto dominance over the 12 settings
grid = (
    fr.groupby(["policy", "alpha", "hyst", "margin"])[["isvr", "rsvr", "cost", "carbon"]].mean().reset_index()
)
grid.to_csv(OUT / "frontier_settings.csv", index=False)
DOMINANCE_ALPHAS = [0.0, 0.5]
sla_all = grid[grid.policy == "SLA_Guarded"]


def dominated_by(x, pts):
    return bool(np.any(np.all(pts <= x, axis=1) & np.any(pts < x, axis=1)))


dom = []
for alphas in [DOMINANCE_ALPHAS, [0.0, 0.5, 1.0]]:
    sla = sla_all[sla_all.alpha.isin(alphas)][["isvr", "cost", "carbon"]].values
    for p in ["SLA_Guarded_InvWeight", "CostFirst+H", "RoundRobin+H", "CarbonFirst+H", "LatencyFirst+H"]:
        other = grid[grid.policy == p][["isvr", "cost", "carbon"]].values
        dom.append(
            dict(
                sla_guarded_alphas=",".join(f"{a:g}" for a in alphas),
                policy=label(p),
                settings=len(other),
                dominated_by_SLA_Guarded=sum(dominated_by(x, sla) for x in other),
                SLA_Guarded_settings_dominated=sum(dominated_by(x, other) for x in sla),
            )
        )
save(
    pd.DataFrame(dom),
    "pareto_dominance",
    "Pareto dominance in (interval violation, cost, carbon) over the 12 hysteresis/margin settings "
    "of each baseline vs the settings of SLA-Guarded at the listed alpha values",
)

# ---------------------------------------------------------------- ablation
rows = [dict(variant="SLA-Guarded (alpha=0.5)", **summarize(ref))]
ab = ev[ev.tag == "ablation"]
for p in ["no_guardrail", "no_prediction", "no_hysteresis", "no_margin", "no_prewarm", "with_spreading"]:
    rows.append(dict(variant=label(p), **summarize(ab[ab.policy == p], ref)))
save(pd.DataFrame(rows).round(3), "ablation", "Ablation study (alpha=0.5)")

# ---------------------------------------------------------------- alpha
rows = []
for a in [0.0, 0.25, 0.5, 0.75, 1.0]:
    if a in (0.25, 0.75):
        g = ev[(ev.tag == "alpha") & (ev.alpha == a)]
        setting = "rel0.75, m=2"
    else:
        g = selected_runs("SLA_Guarded", a)
        s = sel[(sel.policy == "SLA_Guarded") & (sel.alpha == a)].iloc[0]
        setting = f"{s.hyst}, m={s.margin:g}"
    m, c = ci95(100 * g.isvr)
    rows.append(
        dict(
            alpha=a,
            setting=setting,
            isvr=m,
            isvr_ci95=c,
            rsvr=100 * g.rsvr.mean(),
            cost=g.cost.mean(),
            carbon=g.carbon.mean(),
            scaling_changes=g.scal.mean(),
        )
    )
save(pd.DataFrame(rows).round(3), "alpha", "Effect of the cost-carbon weight alpha")

# ---------------------------------------------------------------- efficiency
rows = []
for p, a in [
    ("SLA_Guarded", 0.5),
    ("SLA_Guarded", 0.0),
    ("SLA_Guarded_InvWeight", 0.5),
    ("CostFirst+H", 0.5),
    ("RoundRobin+H", 0.5),
    ("CarbonFirst+H", 0.5),
    ("LatencyFirst+H", 0.5),
]:
    g = selected_runs(p, a)
    rows.append((label(p, a), g))
for p in ["HPA_Stab", "SOLA_style", "CarbonAdvisor_Style"]:
    rows.append((p, rb[rb.policy == p]))
eff = pd.DataFrame(
    [
        dict(
            policy=n,
            rsvr=100 * g.rsvr.mean(),
            usd_per_1k_compliant_req=1000 * g.cost_per_ok.mean(),
            g_co2e_per_compliant_req=g.carbon_per_ok.mean(),
        )
        for n, g in rows
    ]
)
save(eff.round(3), "efficiency", "Cost and carbon per SLO-compliant request")

# ---------------------------------------------------------------- cold start
cs = load("coldstart.json")
sw = cs[cs.kind == "sweep"].copy()
sw["name"] = [label(p, a) for p, a in zip(sw.policy, sw.alpha)]
sweep = (100 * sw.pivot_table(index="name", columns="warm", values="isvr", aggfunc="mean")).round(2)
sweep.columns = [f"{30 * int(w)} s" for w in sweep.columns]
save(
    sweep.reset_index().rename(columns={"name": "policy"}),
    "coldstart_sweep",
    "Interval SLO violation (%) vs cold-start delay",
)
va = cs[cs.kind == "variant"]
rows = []
for p in ["SLA_Guarded", "SLA_Guarded_InvWeight", "CostFirst+H", "RoundRobin+H"]:
    r = dict(policy=label(p, 0.5))
    base = sw[(sw.policy == p) & (sw.alpha == 0.5) & (sw.warm == 2)]
    for name, g in [("fixed 60 s", base)] + [
        (v, va[(va.policy == p) & (va.variant == v)]) for v in ["ln60", "ln120", "sd2", "bill_ready"]
    ]:
        r[name] = f"{100 * g.isvr.mean():.1f} / {g.cost.mean():,.0f}"
    rows.append(r)
save(
    pd.DataFrame(rows),
    "coldstart_variants",
    "Interval violation (%) / cost (USD) under alternative cold-start models "
    "(ln60/ln120: log-normal start-up, mean 60/120 s; sd2: delayed scale-down; bill_ready: billed when ready)",
)

# ---------------------------------------------------------------- joint sensitivity
d = load("lhs.json")
P = ["low", "margin", "rtt", "alpha", "eta", "warm", "H", "umax"]
NAMES = {
    "low": "hysteresis band h_lo [0.3, 1.0]",
    "margin": "safety margin m [1.2, 3.0]",
    "rtt": "RTT budget [5, 80] ms",
    "alpha": "alpha [0, 1]",
    "eta": "churn penalty eta [0, 0.1]",
    "warm": "cold-start delay [0, 240] s",
    "H": "horizon H [1, 32]",
    "umax": "U_max [0.80, 0.95]",
}


def prcc(X, y):
    R = np.column_stack([stats.rankdata(X[:, j]) for j in range(X.shape[1])])
    ry = stats.rankdata(y)
    out = []
    for j in range(X.shape[1]):
        Z = np.column_stack([np.ones(len(y)), np.delete(R, j, axis=1)])
        rx = R[:, j] - Z @ np.linalg.lstsq(Z, R[:, j], rcond=None)[0]
        rr = ry - Z @ np.linalg.lstsq(Z, ry, rcond=None)[0]
        out.append(stats.pearsonr(rx, rr))
    return out


X = d[P].values.astype(float)
T = pd.DataFrame({"parameter": [NAMES[p] for p in P]})
for m in ["isvr", "cost", "carbon"]:
    T[m] = [f"{c:+.2f}{'*' if p < 0.01 else ''}" for c, p in prcc(X, d[m].values)]
save(T, "prcc", "Partial rank correlation coefficients (* p < 0.01)")

d["margin_bin"] = pd.cut(d.margin, [1.2, 1.8, 2.4, 3.0], include_lowest=True).astype(str)
d["band_bin"] = pd.cut(d.low, [0.3, 0.53, 0.77, 1.0], include_lowest=True).astype(str)
piv = (100 * d.pivot_table(index="margin_bin", columns="band_bin", values="isvr", aggfunc="mean")).round(1)
save(
    piv.reset_index(),
    "lhs_margin_band",
    "Mean interval violation (%) by safety margin (rows) and hysteresis band h_lo (columns)",
)

y = d.isvr.values
Zs = (X - X.mean(0)) / X.std(0)
main_cols = [Zs[:, i] for i in range(len(P))]
inter = [Zs[:, i] * Zs[:, j] for i, j in itertools.combinations(range(len(P)), 2)] + [
    Zs[:, i] ** 2 for i in range(len(P))
]


def r2(cols):
    A = np.column_stack([np.ones(len(y))] + cols)
    pred = A @ np.linalg.lstsq(A, y, rcond=None)[0]
    return 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()


save(
    pd.DataFrame(
        [
            dict(
                samples=len(d),
                median_isvr=100 * np.median(y),
                share_meeting_5pct=100 * (y <= 0.05).mean(),
                r2_main_effects=r2(main_cols),
                r2_with_interactions=r2(main_cols + inter),
            )
        ]
    ).round(3),
    "lhs_summary",
    "Joint sensitivity summary",
)

# ---------------------------------------------------------------- latency model validation
des = json.load(open(RES / "des.json"))
g = pd.DataFrame(des["grid"])
g["des_over_analytic"] = g.des_p99_wait / g.analytic_p99_wait.replace(0, np.nan)
save(g.round(3), "des_grid", "Analytic M/M/k vs discrete-event p99 waiting time (s)")
save(
    pd.DataFrame(des["guardrail"]).round(3),
    "des_guardrail",
    "DES p99 TTFT (s) at the capacity chosen by the analytic guardrail",
)
save(
    pd.DataFrame(json.load(open(RES / "des_margin.json"))).round(3),
    "des_margin",
    "Capacity needed under within-interval bursts relative to the analytic guardrail",
)

# ---------------------------------------------------------------- traces
POL_ORDER = [
    "SLA-Guarded (alpha=0.5)",
    "SLA-Guarded (alpha=0)",
    LABEL["SLA_Guarded_InvWeight"],
    "LatencyFirst+H",
    "CostFirst+H",
    "RoundRobin+H",
    "CarbonFirst+H",
    "LatencyFirst",
    "CostFirst",
    "SOLA_style",
    "HPA_Stab",
]


def trace_table(df, keys):
    df = df.copy()
    df["policy_label"] = [label(p, a) for p, a in zip(df.policy, df.alpha)]
    g = (
        df.groupby(keys + ["policy_label"])[["isvr", "rsvr", "cost", "carbon", "mean_rate"]]
        .mean()
        .reset_index()
    )
    g[["isvr", "rsvr"]] *= 100
    g["order"] = g.policy_label.map({n: i for i, n in enumerate(POL_ORDER)})
    return g.sort_values(keys + ["order"]).drop(columns="order").round(3)


tw = load("trace_week.json")
save(
    trace_table(tw, ["trace", "scale"]),
    "trace_week",
    "2024 one-week traces (mean over 7 daily windows; violations in %; cost USD and carbon t per day)",
)
save(
    trace_table(load("trace_short.json"), ["trace", "protocol"]),
    "trace_short",
    "2023 one-hour traces (10 seeds; transient start and 10 min preconditioning)",
)
if (RES / "trace_alpha0.json").exists():
    ta = load("trace_alpha0.json")
    ta["setting"] = ta.hyst + ", m=" + ta.margin.astype(str)
    g = ta.groupby("setting")[["isvr", "rsvr", "cost", "carbon", "scal"]].mean().reset_index()
    g[["isvr", "rsvr"]] *= 100
    save(
        g.round(3),
        "trace_alpha0",
        "SLA-Guarded (alpha=0) on the 2024 conversation trace: hysteresis band and margin",
    )

# ---------------------------------------------------------------- scalability
sc = load("scalability.json")
stage = {
    "Stage_routing_ms_per_step": "routing_ms",
    "Stage_guardrail_ms_per_step": "guardrail_ms",
    "Stage_capacity_search_ms_per_step": "capacity_search_ms",
    "Stage_hysteresis_ms_per_step": "hysteresis_ms",
}
g = (
    sc.groupby("n_regions")
    .agg(
        mean_step_ms=("mean_step_ms", "mean"),
        p99_step_ms=("p99_step_ms", "mean"),
        **{v: (k, "mean") for k, v in stage.items() if k in sc},
        isvr=("isvr", "mean"),
        rsvr=("rsvr", "mean"),
        regions_used=("regions_used", "mean"),
    )
    .reset_index()
)
g[["isvr", "rsvr"]] *= 100
save(
    g.round(3),
    "scalability",
    "Control-loop time per interval (ms) and SLO violation (%) vs number of regions",
)

# ---------------------------------------------------------------- aggregation window
w = load("window.json")
w["name"] = [label(p, a) for p, a in zip(w.policy, w.alpha)]
g = w.groupby("name")[
    ["isvr_pooled_30s", "isvr_pooled_60s", "isvr_pooled_120s", "rsvr", "req_mean", "req_p5", "frac_lt100"]
].mean()
g[["isvr_pooled_30s", "isvr_pooled_60s", "isvr_pooled_120s", "rsvr", "frac_lt100"]] *= 100
g = g.sort_values("isvr_pooled_30s").reset_index().rename(columns={"name": "policy"})
save(g.round(2), "window", "Interval SLO violation (%) for aggregation windows of 30, 60 and 120 s")

(OUT / "tables.md").write_text("# Result tables\n\n" + "\n".join(MD))
print(f"\nTables written to {OUT}")
