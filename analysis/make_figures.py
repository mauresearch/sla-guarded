"""Generate all figures from the results in results/.

Figures 2 and 3 (time series, routing and capacity) re-run seed 0 of the
corresponding policies; all other figures only read the JSON results.

Usage: python analysis/make_figures.py [f1 f2 ... f7]   (default: all)
Output: figures/*.png, results/peak_stats.json, results/routing_stats.json
"""

import json
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import NullFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sla_guarded import simulator as sg  # noqa: E402

RES = ROOT / "results"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.titlesize": 8,
        "axes.labelsize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
    }
)
C = {
    "sla": "#2a78d6",
    "sla0": "#1c5cab",
    "cost": "#eb6834",
    "rr": "#1baf7a",
    "lat": "#eda100",
    "carb": "#e87ba4",
    "grey": "#8a8984",
    "lgrey": "#b5b4ac",
}


def style(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color("#b5b4ac")
    ax.grid(True, color="#e8e7e2", lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#4a4944")


def frontier(ev):
    f = ev[ev.tag == "frontier"]
    return (
        f.groupby(["policy", "alpha", "hyst", "margin"])[["isvr", "rsvr", "cost", "carbon"]]
        .mean()
        .reset_index()
    )


HY = {
    "rel0.5": dict(mode="relative", low_ratio=0.5, high_ratio=1.0),
    "rel0.75": dict(mode="relative", low_ratio=0.75, high_ratio=1.5),
    "abs2048": dict(mode="absolute", ref_capacity=2048),
    "abs4096": dict(mode="absolute", ref_capacity=4096),
    "none": None,
}
SEL = pd.read_csv(RES / "selected_settings.csv")


def run(pol, alpha=0.5, seed=0):
    sc = sg.SimulationConfig()
    sc.alpha_tradeoff = alpha
    r = SEL[(SEL.policy == pol) & (SEL.alpha == alpha)]
    h, m = (r.iloc[0].hyst, float(r.iloc[0].margin)) if len(r) else ("rel0.75", 2.0)
    if pol in ("LatencyFirst", "CostFirst", "CarbonFirst", "SOLA_style"):
        h, m = "none", 1.5
    return sg.run_policy(
        pol, seed=seed, sim_config=sc, hysteresis=HY[h], guardrail_margin=m, return_history=True
    )[1]


which = sys.argv[1:] or ["f1", "f2", "f3", "f4", "f5", "f6", "f7"]
hours = np.arange(2880) * 30 / 3600
# ---------- F1 frontier cost vs carbon (feasible settings)
if "f1" in which:
    ev = pd.DataFrame(json.load(open(RES / "main_eval.json")))
    fr = frontier(ev)
    f5 = fr[fr.isvr <= 0.05]
    al = ev[ev.tag == "alpha"].groupby("alpha")[["isvr", "cost", "carbon"]].mean().reset_index()
    fig, ax = plt.subplots(figsize=(3.45, 2.5), dpi=300)
    style(ax)
    for p, lab, c, m in [
        ("CostFirst+H", "CostFirst+H", C["cost"], "s"),
        ("RoundRobin+H", "RoundRobin+H", C["rr"], "^"),
        ("LatencyFirst+H", "LatencyFirst+H", C["lat"], "D"),
        ("SLA_Guarded_InvWeight", "Inverse-weight variant", C["carb"], "v"),
    ]:
        g = f5[f5.policy == p]
        ax.scatter(g.cost, g.carbon, color=c, marker=m, s=16, edgecolor="white", lw=0.5, label=lab, zorder=3)
    v = pd.concat(
        [
            f5[f5.policy == "SLA_Guarded"][["cost", "carbon", "alpha"]],
            al[al.isvr <= 0.05][["cost", "carbon", "alpha"]],
        ]
    )
    ax.scatter(
        v.cost,
        v.carbon,
        color=C["sla"],
        s=20,
        edgecolor="white",
        lw=0.5,
        label="SLA-Guarded (any $\\alpha$)",
        zorder=4,
    )
    for a, dx, dy in [(0.0, 5, -8), (0.25, 5, 2), (0.5, 5, -8), (1.0, 5, 2)]:
        r = v[v.alpha == a].sort_values("cost").iloc[0]
        ax.annotate(
            f"$\\alpha$={a:g}",
            (r.cost, r.carbon),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=6.5,
            color="#1c5cab",
        )
    ax.set_xscale("log")
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks([200, 500, 1000, 2000, 5000])
    ax.set_xticklabels(["200", "500", "1,000", "2,000", "5,000"])
    ax.set_xlabel("Total cost over 24 h (USD, log scale)")
    ax.set_ylabel("Total carbon (t CO$_2$e)")
    ax.legend(
        frameon=True,
        facecolor="white",
        edgecolor="#e8e7e2",
        loc="upper left",
        handletextpad=0.3,
        borderpad=0.3,
        labelspacing=0.3,
    )
    plt.tight_layout(pad=0.3)
    plt.savefig(FIG / "fig_frontier_cost_carbon.png")
    plt.close()
# ---------- F2 violation vs cost frontier
if "f2" in which:
    fr = frontier(pd.DataFrame(json.load(open(RES / "main_eval.json"))))
    fr = fr[fr.alpha == 0.5]
    fig, ax = plt.subplots(figsize=(3.45, 2.4), dpi=300)
    style(ax)
    for p, lab, c, m in [
        ("SLA_Guarded", "SLA-Guarded ($\\alpha$=0.5)", C["sla"], "o"),
        ("SLA_Guarded_InvWeight", "Inverse-weight variant", C["carb"], "v"),
        ("RoundRobin+H", "RoundRobin+H", C["rr"], "^"),
        ("CostFirst+H", "CostFirst+H", C["cost"], "s"),
        ("LatencyFirst+H", "LatencyFirst+H", C["lat"], "D"),
    ]:
        g = fr[fr.policy == p].sort_values("cost")
        # lower envelope
        env = []
        best = 9
        for _, r in g.iterrows():
            if r.isvr < best:
                env.append(r)
                best = r.isvr
        e = pd.DataFrame(env)
        ax.scatter(g.cost, 100 * g.isvr, color=c, marker=m, s=9, alpha=0.35, lw=0)
        ax.plot(e.cost, 100 * e.isvr, color=c, marker=m, ms=3.5, lw=1.3, label=lab)
    ax.axhline(5, color="#9c9b94", lw=0.8, ls=(0, (4, 3)))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks([200, 500, 1000, 2000, 5000])
    ax.set_xticklabels(["200", "500", "1,000", "2,000", "5,000"])
    ax.set_yticks([0.5, 1, 2, 5, 10, 20, 40])
    ax.set_yticklabels(["0.5", "1", "2", "5", "10", "20", "40"])
    ax.set_xlabel("Total cost over 24 h (USD, log scale)")
    ax.set_ylabel("Interval SLO violation (%)")
    ax.legend(
        frameon=True,
        facecolor="white",
        edgecolor="#e8e7e2",
        loc="lower left",
        handletextpad=0.3,
        borderpad=0.3,
        labelspacing=0.25,
    )
    plt.tight_layout(pad=0.3)
    plt.savefig(FIG / "fig_frontier_reliability.png")
    plt.close()
# ---------- F3 time series (hourly violation rates)
if "f3" in which:
    H = {
        "SLA-Guarded ($\\alpha$=0.5)": (run("SLA_Guarded"), C["sla"], 1.4),
        "CostFirst+H": (run("CostFirst+H"), C["cost"], 1.0),
        "CarbonFirst+H": (run("CarbonFirst+H"), C["carb"], 1.0),
        "CostFirst (own capacity rule)": (run("CostFirst"), C["grey"], 1.0),
    }
    fig, axs = plt.subplots(2, 1, figsize=(3.45, 3.1), dpi=300, sharex=True)
    hh = np.arange(24) + 0.5
    for n, (h, c, lw) in H.items():
        v = np.array(h["slo_violation"]).reshape(24, 120).mean(1) * 100
        vr = np.array(h["violating_requests_per_step"]).reshape(24, 120).sum(1)
        rq = np.array(h["total_requests_per_step"]).reshape(24, 120).sum(1)
        axs[0].plot(hh, v, color=c, lw=lw, marker="o", ms=2, label=n)
        axs[1].plot(hh, 100 * vr / np.maximum(rq, 1), color=c, lw=lw, marker="o", ms=2)
    for ax, l in zip(axs, ["Interval SLO\nviolation (%)", "Request SLO\nviolation (%)"]):
        style(ax)
        ax.set_ylabel(l)
    axs[1].set_xlabel("Time of day (h)")
    axs[1].set_xlim(0, 24)
    axs[1].set_xticks(range(0, 25, 4))
    axs[0].legend(
        frameon=True,
        facecolor="white",
        edgecolor="#e8e7e2",
        loc="upper left",
        handletextpad=0.3,
        borderpad=0.3,
        labelspacing=0.2,
        fontsize=6.3,
    )
    for ax, t in zip(axs, ["(a)", "(b)"]):
        ax.text(-0.2, 1.0, t, transform=ax.transAxes, fontsize=8, fontweight="bold", va="top")
    plt.tight_layout(pad=0.3)
    plt.savefig(FIG / "fig_timeseries.png")
    plt.close()
    out = {}
    for n, (h, _, _) in H.items():
        v = np.array(h["slo_violation"])
        pk = (hours >= 18) & (hours < 20)
        out[n] = dict(peak=float(v[pk].mean()), all=float(v.mean()))
    json.dump(out, open(RES / "peak_stats.json", "w"), indent=1)
    print(out)
# ---------- F4 routed load + capacity
if "f4" in which:
    h = run("SLA_Guarded")
    hn = run("no_hysteresis")
    regs = ["edge_1", "edge_2", "cloud_1", "cloud_2"]
    cols = ["#2a78d6", "#1baf7a", "#eb6834", "#e87ba4"]
    fig, axs = plt.subplots(3, 1, figsize=(3.45, 4.2), dpi=300, sharex=True)
    L = np.array([[d[r] for r in regs] for d in h["lambda_per_region"]])
    Lh = L.reshape(96, 30, 4).mean(1)
    hq = (np.arange(96) + 0.5) / 4
    style(axs[0])
    axs[0].stackplot(hq, Lh.T, colors=cols, labels=regs, alpha=0.9, lw=0)
    axs[0].set_ylabel("Routed load\n(req/s)")
    axs[0].legend(
        ncol=4,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        handlelength=1,
        columnspacing=0.8,
    )
    for ax, hh_, t in [(axs[1], h, "SLA-Guarded"), (axs[2], hn, "w/o hysteresis")]:
        style(ax)
        K = np.array([[d[r] for r in regs] for d in hh_["k_per_region"]])
        for i, r in enumerate(regs):
            ax.plot(hours, K[:, i], color=cols[i], lw=0.5)
        ax.set_ylabel(f"Capacity $k_r$\n({t})")
    axs[2].set_xlabel("Time of day (h)")
    axs[2].set_xlim(0, 24)
    axs[2].set_xticks(range(0, 25, 4))
    for ax, t in zip(axs, ["(a)", "(b)", "(c)"]):
        ax.text(-0.22, 1.0, t, transform=ax.transAxes, fontsize=8, fontweight="bold", va="top")
    plt.tight_layout(pad=0.3)
    plt.savefig(FIG / "fig_routing_capacity.png")
    plt.close()
    sh = L.sum(0) / L.sum()
    json.dump(
        dict(
            load_share=dict(zip(regs, sh.round(3).tolist())),
            scal=int(np.sum(h["scaling_changes"])),
            scal_noh=int(np.sum(hn["scaling_changes"])),
        ),
        open(RES / "routing_stats.json", "w"),
        indent=1,
    )
    print(open(RES / "routing_stats.json").read())
# ---------- F5 cold start
if "f5" in which:
    d = pd.DataFrame(json.load(open(RES / "coldstart.json")))
    d = d[d.kind == "sweep"].copy()
    d["name"] = d.policy + d.apply(lambda r: f" a={r.alpha:g}" if r.policy == "SLA_Guarded" else "", axis=1)
    g = d.groupby(["name", "warm"]).isvr.mean().reset_index()
    fig, ax = plt.subplots(figsize=(3.45, 2.5), dpi=300)
    style(ax)
    S = [
        ("SLA_Guarded a=0.5", "SLA-Guarded ($\\alpha$=0.5)", C["sla"], "o", 1.6),
        ("SLA_Guarded a=0", "SLA-Guarded ($\\alpha$=0)", C["sla0"], "o", 1.0),
        ("CostFirst+H", "CostFirst+H", C["cost"], "s", 1.0),
        ("RoundRobin+H", "RoundRobin+H", C["rr"], "^", 1.0),
        ("CarbonFirst+H", "CarbonFirst+H", C["carb"], "v", 1.0),
        ("SOLA_style", "SOLA-style", C["grey"], "D", 0.8),
        ("LatencyFirst", "LatencyFirst", C["lgrey"], "x", 0.8),
    ]
    for n, l, c, m, lw in S:
        x = g[g.name == n]
        ax.plot(x.warm * 30, 100 * x.isvr, color=c, marker=m, lw=lw, ms=3, label=l)
    ax.axhline(5, color="#9c9b94", lw=0.8, ls=(0, (4, 3)))
    ax.set_yscale("symlog", linthresh=10)
    ax.set_ylim(0, 95)
    ax.set_yticks([0, 2, 5, 10, 20, 50])
    ax.set_yticklabels(["0", "2", "5", "10", "20", "50"])
    ax.set_xticks([0, 30, 60, 120, 240])
    ax.set_xlabel("Capacity cold-start delay (s)")
    ax.set_ylabel("Interval SLO violation (%)")
    ax.legend(
        frameon=True,
        facecolor="white",
        edgecolor="#e8e7e2",
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        handletextpad=0.3,
        borderpad=0.3,
        labelspacing=0.3,
    )
    fig.set_size_inches(5.0, 2.3)
    plt.tight_layout(pad=0.3)
    plt.savefig(FIG / "fig_coldstart.png")
    plt.close()
# ---------- F6 DES validation
if "f6" in which:
    g = pd.DataFrame(json.load(open(RES / "des.json"))["grid"])
    fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.1), dpi=300)
    for ax, k in zip(axs, [10, 50, 200]):
        style(ax)
        x = g[(g.k == k) & (g.service == "exp") & (g.arrivals == "poisson")]
        ax.plot(x.rho, x.analytic_p99_wait, color="#1f1e1c", lw=1.4, label="M/M/k analytic")
        for (sv, ar), c, m, l in [
            (("exp", "poisson"), C["sla"], "o", "DES: exp. service"),
            (("lognormal_tokens", "poisson"), C["rr"], "^", "DES: token-based service"),
            (("lognormal_tokens", "bursty5s"), C["cost"], "s", "DES: token-based + bursts"),
        ]:
            y = g[(g.k == k) & (g.service == sv) & (g.arrivals == ar)]
            ax.plot(y.rho, y.des_p99_wait, color=c, marker=m, ms=3, lw=0.9, ls="--", label=l)
        ax.set_yscale("symlog", linthresh=1)
        ax.set_yticks([0, 1, 2, 5, 10, 20, 50])
        ax.set_yticklabels(["0", "1", "2", "5", "10", "20", "50"])
        ax.set_title(f"k = {k}")
        ax.set_xlabel("Utilisation $\\rho$")
    axs[0].set_ylabel("p99 waiting time (s)")
    axs[0].legend(
        frameon=True,
        facecolor="white",
        edgecolor="#e8e7e2",
        loc="upper left",
        fontsize=6,
        handletextpad=0.3,
        borderpad=0.3,
        labelspacing=0.2,
    )
    plt.tight_layout(pad=0.3)
    plt.savefig(FIG / "fig_des_validation.png")
    plt.close()
# ---------- F7 scalability
if "f7" in which:
    s = pd.DataFrame(json.load(open(RES / "scalability.json")))
    m = s.groupby("n_regions").agg(["mean", "std"])
    n = m.index.values
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.1), dpi=300)
    ax = axs[0]
    style(ax)
    ax.errorbar(
        n,
        m[("mean_step_ms", "mean")],
        yerr=m[("mean_step_ms", "std")],
        color=C["sla"],
        marker="o",
        ms=3,
        lw=1.2,
        capsize=2,
        label="mean",
    )
    ax.errorbar(
        n,
        m[("p99_step_ms", "mean")],
        yerr=m[("p99_step_ms", "std")],
        color=C["cost"],
        marker="s",
        ms=3,
        lw=1.2,
        capsize=2,
        label="p99",
    )
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(n)
    ax.set_xticklabels(n)
    ax.set_xlabel("Number of regions (= clusters)")
    ax.set_ylabel("Time per interval (ms)")
    ax.legend(frameon=False)
    ax = axs[1]
    style(ax)
    ax.errorbar(
        n,
        100 * m[("rsvr", "mean")],
        yerr=100 * m[("rsvr", "std")],
        color=C["sla"],
        marker="o",
        ms=3,
        lw=1.2,
        capsize=2,
        label="request-level",
    )
    ax.errorbar(
        n,
        100 * m[("isvr", "mean")],
        yerr=100 * m[("isvr", "std")],
        color=C["grey"],
        marker="s",
        ms=3,
        lw=1.2,
        capsize=2,
        label="interval-level (any region)",
    )
    ax.set_xscale("log", base=2)
    ax.set_xticks(n)
    ax.set_xticklabels(n)
    ax.set_xlabel("Number of regions (= clusters)")
    ax.set_ylabel("SLO violation (%)")
    ax.legend(frameon=False)
    for a, t in zip(axs, ["(a)", "(b)"]):
        a.text(0.0, 1.03, t, transform=a.transAxes, fontsize=8, fontweight="bold", va="bottom")
    plt.tight_layout(pad=0.3)
    plt.savefig(FIG / "fig_scalability.png")
    plt.close()
