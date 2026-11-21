# SLA-Guarded: Tail-Latency-Aware Edge–Cloud Scheduling for LLM Serving

This repository contains the simulator, the SLA-Guarded controller, all baselines
and the scripts that reproduce every table and figure of the paper
*SLA-Guarded Edge–Cloud Scheduling for Tail-Latency-Aware LLM Serving*.

SLA-Guarded is a regional controller for LLM inference served across edge and
cloud regions. Every 30 s it decides where the traffic of each user cluster is
served and how much capacity each region provisions:

- **Routing.** Each user cluster is sent to the admissible region (within an RTT
  budget of its nearest region) with the lowest normalized cost–carbon score
  `(1 − α)·price + α·carbon`. Assignment is capacity-aware, and a switch to a new
  region waits until that region has warm capacity (cold-start-aware switching).
- **Tail-latency guardrail.** For the load actually routed to a region, an
  M/M/k (Erlang-C) model gives the minimum capacity that keeps the p99
  time-to-first-token (TTFT) and the p99 end-to-end latency within the SLO. This
  bound is inflated by a safety margin and enforced before cost and carbon are optimized.
- **Capacity planning.** A receding-horizon search over a short load forecast
  chooses the capacity of each region, with a penalty on capacity churn.
- **Hysteresis.** A relative deadband filters small capacity changes, so that
  the controller does not pay repeated cold starts.

## Repository layout

```
sla_guarded/simulator.py     simulator, SLA-Guarded, baselines and ablations
experiments/                 scripts that run the experiments (write to results/)
analysis/make_tables.py      builds all tables from results/ (CSV + Markdown)
analysis/make_figures.py     builds all figures from results/
data/azure_llm_traces/       30 s aggregates of the Azure LLM inference traces
results/                     results of the full runs (JSON), as used in the paper
figures/                     generated figures
run_all.sh                   runs everything end to end
```

## Installation

Python 3.10 or newer.

```bash
git clone <repository-url>
cd sla-guarded
pip install -r requirements.txt
```

## Quick start

Rebuild all tables and figures from the provided results (about one minute):

```bash
python analysis/make_tables.py      # -> results/tables/*.csv and results/tables/tables.md
python analysis/make_figures.py     # -> figures/*.png
```

Run a single policy:

```python
from sla_guarded import SimulationConfig, run_policy

cfg = SimulationConfig()          # 24 h, 30 s intervals, p99 TTFT 3 s, p99 latency 30 s
cfg.alpha_tradeoff = 0.5          # cost-carbon weight
summary = run_policy(
    "SLA_Guarded", seed=0, sim_config=cfg,
    hysteresis=dict(mode="relative", low_ratio=0.75, high_ratio=1.5),
    guardrail_margin=2.0,
)
print(summary["SLO_Violation_Rate"], summary["Request_Violation_Rate"],
      summary["Total_Cost_USD"], summary["Total_Carbon_g"] / 1e6)
```

## Reproducing the experiments

```bash
./run_all.sh                 # full run, writes results/, tables and figures
QUICK=1 ./run_all.sh         # smoke test (fewer seeds, 2 simulated hours), writes results_quick/
WORKERS=8 ./run_all.sh       # limit the number of parallel processes
```

The full run executes several thousand 24-hour simulations and can take many
hours, depending on the number of cores. The scripts can also be run one by one:

| Script | What it does | Output | Used for |
|---|---|---|---|
| `01_tune.py` | Tunes the hysteresis band and safety margin of every hysteresis-equipped policy on validation seeds 100–102 (12 settings each; cheapest setting with ≤ 5% interval violation) | `tuning.json`, `selected_settings.csv` | settings of all policies |
| `02_evaluate.py` | Test seeds 0–9: all policies at all settings, α sweep, ablations, rule-based baselines | `main_eval.json` | overall comparison, Pareto frontiers, ablation, α, efficiency |
| `03_coldstart.py` | Cold-start delay 0–240 s; alternative cold-start models | `coldstart.json` | cold-start figure and table |
| `04_sensitivity.py` | 300 Latin-hypercube samples over eight parameters | `lhs.json` | joint sensitivity (PRCC) |
| `05_latency_validation.py` | Analytic M/M/k vs discrete-event simulation | `des.json`, `des_margin.json` | latency-model validation |
| `06_window.py` | Interval metric for 30/60/120 s windows; request-level accounting | `window.json` | aggregation-window table |
| `07_scalability.py` | 4–128 regions: control-loop time per stage and SLO violation | `scalability.json` | scalability figure and table |
| `08_trace_prepare.py` | Aggregates a raw Azure trace into 30 s bins (already done, see below) | `data/azure_llm_traces/*.csv` | trace evaluation |
| `09_trace_eval.py week\|short\|alpha0` | Trace-driven evaluation on the 2024 one-week and 2023 one-hour Azure traces | `trace_*.json` | trace-driven evaluation |

All runs are deterministic for a given seed.

### Figures

| File | Content |
|---|---|
| `fig_frontier_reliability.png` | Interval SLO violation vs cost for all settings of each policy (α = 0.5) |
| `fig_frontier_cost_carbon.png` | Cost vs carbon of all settings that meet the 5% target |
| `fig_timeseries.png` | Hourly interval and request SLO violation over the day |
| `fig_routing_capacity.png` | Routed load per region and capacity with and without hysteresis |
| `fig_coldstart.png` | Interval SLO violation vs cold-start delay |
| `fig_des_validation.png` | Analytic vs discrete-event p99 waiting time |
| `fig_scalability.png` | Control-loop time and SLO violation vs number of regions |

## Policies

| Name | Description |
|---|---|
| `SLA_Guarded` | Proposed controller |
| `SLA_Guarded_InvWeight` | SLA-Guarded with inverse-weight spreading over admissible regions instead of argmin routing |
| `LatencyFirst+H`, `CostFirst+H`, `CarbonFirst+H`, `RoundRobin+H` | Routing baselines with the same guardrail, safety margin and hysteresis filter as SLA-Guarded |
| `LatencyFirst`, `CostFirst`, `CarbonFirst`, `RoundRobin` | Routing baselines with their own reactive capacity rule |
| `QLM_style`, `SOLA_style` | SLO-aware baselines in the style of QLM and SOLA |
| `ThresholdBased`, `HPA_Stab` | Utilization-threshold autoscaler (Kubernetes HPA-like), without and with a 300 s stabilization window |
| `CarbonAdvisor_Style` | Carbon-aware spatial shifting with reactive scaling |
| `no_guardrail`, `no_prediction`, `no_hysteresis`, `no_margin`, `no_prewarm`, `with_spreading` | Ablations of SLA-Guarded |

## Simulation model

- Four regions (two edge, two cloud) and four user clusters; region prices,
  carbon intensities, PUE and RTTs are set in `create_default_topology()`.
- Diurnal, bursty arrivals per user cluster; synthetic diurnal price and carbon
  traces per region.
- Service rate per unit `1 / (0.8 s + response tokens / token rate)`, with 50
  tokens/s at the edge and 70 tokens/s in the cloud.
- SLO: p99 TTFT ≤ 3 s and p99 end-to-end latency ≤ 30 s. An interval violates
  the SLO if any region misses either target; the request-level violation rate is
  the expected share of requests, under the same M/M/k model, whose TTFT or
  latency exceeds its target.
- New capacity needs a 60 s cold start and is billed from launch; scale-downs
  take effect immediately (both configurable).

## Trace data

The trace-driven evaluation uses the public
[Azure LLM inference traces](https://github.com/Azure/AzurePublicDataset)
(2023 one-hour traces and 2024 one-week traces, conversation and code
services; CC-BY 4.0). The raw traces are several gigabytes, so this repository
contains only their 30 s aggregates in `data/azure_llm_traces/`. See
`data/azure_llm_traces/README.md` for how to rebuild them.

## Citation

If you use this code, please cite:

```bibtex
@article{khaledian_sla_guarded,
  title   = {SLA-Guarded Edge--Cloud Scheduling for Tail-Latency-Aware LLM Serving},
  author  = {Khaledian, Navid and Ramezanpour, Mohammadreza and Khorsand, Reihaneh},
  year    = {2026},
  note    = {Under review}
}
```

## License

See `LICENSE`.
