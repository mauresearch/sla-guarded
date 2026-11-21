"""Validation of the analytic M/M/k tail-latency model against a request-level
discrete-event simulation (DES) of an FCFS multi-server queue.

  grid       analytic vs DES p99 waiting time for k in {10, 50, 200} and
             utilisation 0.5-0.95, with exponential service, token-based
             service (log-normal response length), a heavier-tailed variant,
             and token-based service with within-interval bursts
  guardrail  DES p99 TTFT at the capacity chosen by the analytic guardrail
  margin     capacity actually needed under bursts, relative to the analytic one

Outputs: results/des.json, results/des_margin.json
"""

import heapq
import json

import numpy as np

from common import QUICK, RESULTS, sg

TOKEN_RATE_CLOUD = 70.0
MU = sg.calculate_effective_mu(TOKEN_RATE_CLOUD)
N_REQ = 20000 if QUICK else 200000
ec = sg.ErlangC()


def service_times(kind, rng, n):
    if kind == "exp":
        return rng.exponential(1 / MU, n)
    sigma = 1.0 if kind == "lognormal_tokens_heavy" else 0.70
    tokens = np.maximum(150, rng.lognormal(5.40, sigma, n))
    return 0.8 + tokens / TOKEN_RATE_CLOUD


def arrival_times(kind, lam, rng, n):
    if kind == "poisson":
        return np.cumsum(rng.exponential(1 / lam, n))
    # bursty: the rate is redrawn every 5 s with a mean-one log-normal factor (sigma 0.5)
    t, cur, sig = [], 0.0, 0.5
    while len(t) < n:
        rate = lam * rng.lognormal(-(sig**2) / 2, sig)
        m = rng.poisson(rate * 5.0)
        t.extend(np.sort(cur + 5.0 * rng.random(m)))
        cur += 5.0
    return np.array(t[:n])


def des_waits(lam, k, svc, arr, n=N_REQ, seed=0):
    rng = np.random.default_rng(seed)
    A = arrival_times(arr, lam, rng, n)
    S = service_times(svc, rng, n)
    free = [0.0] * k
    heapq.heapify(free)
    W = np.empty(n)
    for i in range(n):
        f = heapq.heappop(free)
        start = max(A[i], f)
        W[i] = start - A[i]
        heapq.heappush(free, start + S[i])
    return W[n // 10 :]


def p99_ttft(lam, k, svc, arr, rtt, n, seed=1):
    return float(np.quantile(des_waits(lam, k, svc, arr, n=n, seed=seed), 0.99)) + 0.8 + rtt


if __name__ == "__main__":
    grid = []
    for k in [10, 50, 200]:
        for rho in [0.5, 0.7, 0.8, 0.9, 0.95]:
            lam = rho * k * MU
            for svc, arr in [
                ("exp", "poisson"),
                ("lognormal_tokens", "poisson"),
                ("lognormal_tokens_heavy", "poisson"),
                ("lognormal_tokens", "bursty5s"),
            ]:
                W = des_waits(lam, k, svc, arr)
                grid.append(
                    dict(
                        k=k,
                        rho=rho,
                        service=svc,
                        arrivals=arr,
                        analytic_p99_wait=ec.wait_quantile(lam, MU, k),
                        des_p99_wait=float(np.quantile(W, 0.99)),
                        analytic_p_wait=ec.erlang_c(lam, MU, k),
                        des_p_wait=float((W > 1e-9).mean()),
                    )
                )
                print(grid[-1], flush=True)

    regions, _ = sg.create_default_topology()
    cfg = sg.SimulationConfig()
    guard = sg.build_guardrail_calculators(regions, cfg, safety_margin=1.0)["cloud_1"]
    rtt = regions[2].rtt / 1000
    n_check = int(0.75 * N_REQ)
    guardrail = []
    for lam in [2, 5, 10, 20, 40, 80]:
        k_min = guard.min_feasible_k(lam)
        for svc, arr in [("lognormal_tokens", "poisson"), ("lognormal_tokens", "bursty5s")]:
            kd = k_min
            while kd > 1 and p99_ttft(lam, kd - 1, svc, arr, rtt, n_check) <= 3.0:
                kd -= 1
            guardrail.append(
                dict(
                    lam=lam,
                    k_analytic=k_min,
                    service=svc,
                    arrivals=arr,
                    des_p99_ttft_at_k_analytic=p99_ttft(lam, k_min, svc, arr, rtt, n_check),
                    k_des_min=kd,
                )
            )
            print(guardrail[-1], flush=True)
    json.dump(dict(grid=grid, guardrail=guardrail), open(RESULTS / "des.json", "w"))

    n_margin = int(0.6 * N_REQ)
    margin = []
    for lam in [5, 10, 20, 40]:
        k0 = guard.min_feasible_k(lam)
        k = k0
        while p99_ttft(lam, k, "lognormal_tokens", "bursty5s", rtt, n_margin) > 3.0:
            k = int(np.ceil(k * 1.05))
        while k > k0 and p99_ttft(lam, k - 1, "lognormal_tokens", "bursty5s", rtt, n_margin) <= 3.0:
            k -= 1
        margin.append(dict(lam=lam, k_analytic=k0, k_needed_bursty=k, ratio=k / k0))
        print(margin[-1], flush=True)
    json.dump(margin, open(RESULTS / "des_margin.json", "w"))
