"""SLA-Guarded: tail-latency-aware edge-cloud scheduling for LLM serving.

Simulator, SLA-Guarded controller, baselines and ablations.
Entry points: run_policy(), make_controller().
"""

import math
import time
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


def calculate_effective_mu(token_rate, avg_response_tokens=300, ttft_base=0.8):
    """Service rate of one serving unit: 1 / (TTFT base + response tokens / token rate)."""
    avg_service_time = ttft_base + (avg_response_tokens / token_rate)
    return 1.0 / avg_service_time


class RealisticTraceGenerator:
    """Synthetic diurnal electricity-price and carbon-intensity traces per region."""

    def __init__(self, total_steps, interval_s=30, regions=None, seed=42):

        self.total_steps = total_steps
        self.interval_s = interval_s
        self.prices = {}
        self.carbons = {}
        self.rng = np.random.RandomState(seed)

        self._generate_synthetic(regions)

    def _generate_synthetic(self, regions):
        hours = np.array([(t * self.interval_s) / 3600.0 for t in range(self.total_steps)])

        shared_grid_noise = self.rng.randn(len(hours)) * 0.02
        shared_grid_noise = shared_grid_noise - shared_grid_noise.mean()

        for r in regions:
            base_p = r.price_trace
            base_c = r.carbon_trace

            peak_p = 1.0 + 0.35 * np.exp(-0.5 * ((hours - 18.5) ** 2 / 4.0))
            noise_p = shared_grid_noise * 0.8 + self.rng.randn(len(hours)) * 0.03
            p_trace = base_p * np.clip(peak_p + noise_p, 0.5, 2.5)

            peak_c = 1.0 - 0.45 * np.exp(-0.5 * ((hours - 12.5) ** 2 / 3.5))
            gas_peak_corr = 0.12 * np.exp(-0.5 * ((hours - 19.0) ** 2 / 2.0)) * (noise_p > 0)
            noise_c = shared_grid_noise * 0.5 + self.rng.randn(len(hours)) * 0.04
            c_trace = base_c * np.clip(peak_c + noise_c + gas_peak_corr, 0.3, 2.0)

            self.prices[r.name] = p_trace
            self.carbons[r.name] = c_trace

    def get(self, step):
        return {r: self.prices[r][step] for r in self.prices}, {
            r: self.carbons[r][step] for r in self.carbons
        }


OVERLOAD_RHO = 0.999
OVERLOAD_MEAN_WAIT_S = 10.0
OVERLOAD_P99_WAIT_S = 4.605 * OVERLOAD_MEAN_WAIT_S
TTFT_BASE_S = 0.8
ROUTING_CHANGE_TOL = 0.01


def erlang_b(a, k):
    """Erlang-B blocking probability computed with the numerically stable recursion."""
    if a <= 0:
        return 0.0
    B = 1.0
    for n in range(1, k + 1):
        B = a * B / (n + a * B)
    return B


def erlang_c_from_b(B, rho):
    """Erlang-C waiting probability obtained from the Erlang-B value."""
    return B / (1.0 - rho * (1.0 - B))


def approximate_region_p99_latency_and_ttft(
    lam,
    mu,
    k,
    rtt_ms,
):
    """p99 end-to-end latency and p99 TTFT of one region under the M/M/k model."""
    ec = ErlangC()
    rtt = rtt_ms / 1000.0
    p99_latency = ec.p99_latency(lam=lam, mu=mu, k=k, rtt=rtt)
    p99_ttft = ec.p99_ttft(lam=lam, mu=mu, k=k, rtt=rtt)
    LATENCY_CAP_SEC = 37.5
    TTFT_CAP_SEC = 15.0

    return (min(p99_latency, LATENCY_CAP_SEC) * 1000.0, min(p99_ttft, TTFT_CAP_SEC) * 1000.0)


class ErlangC:
    """M/M/k queueing quantities: waiting probability, waiting-time tail and quantiles."""

    def __init__(self):
        pass

    def erlang_c(self, lam, mu, k):

        if lam <= 0:
            return 0.0
        if k <= 0 or mu <= 0:
            return 1.0
        rho = lam / (k * mu)
        if rho >= OVERLOAD_RHO:
            return 1.0
        return erlang_c_from_b(erlang_b(lam / mu, int(k)), rho)

    def waiting_time(self, lam, mu, k):
        """Mean waiting time E[Wq] of an M/M/k FCFS queue (overload -> OVERLOAD_MEAN_WAIT_S)."""
        if lam <= 0:
            return 0.0
        if k <= 0 or mu <= 0:
            return OVERLOAD_MEAN_WAIT_S
        rho = lam / (k * mu)
        if rho >= OVERLOAD_RHO:
            return OVERLOAD_MEAN_WAIT_S
        return self.erlang_c(lam, mu, k) / max(k * mu - lam, 1e-9)

    def wait_quantile(self, lam, mu, k, q=0.99):
        if lam <= 0:
            return 0.0
        if k <= 0 or mu <= 0:
            return OVERLOAD_P99_WAIT_S
        rho = lam / (k * mu)
        if rho >= OVERLOAD_RHO:
            return OVERLOAD_P99_WAIT_S
        C = self.erlang_c(lam, mu, k)
        tail = 1.0 - q
        if C <= tail:
            return 0.0
        return math.log(C / tail) / max(k * mu - lam, 1e-9)

    def prob_wait_exceeds(self, lam, mu, k, t):
        if lam <= 0:
            return 0.0
        if k <= 0 or mu <= 0:
            return 1.0
        rho = lam / (k * mu)
        if rho >= OVERLOAD_RHO:
            return 1.0
        if t <= 0:
            return 1.0
        C = self.erlang_c(lam, mu, k)
        return C * math.exp(-(k * mu - lam) * t)

    def p99_latency(self, lam, mu, k, rtt):
        service = 1.0 / mu if mu > 0 else 1e5
        return min(self.wait_quantile(lam, mu, k) + service + rtt, 1e5)

    def p99_ttft(self, lam, mu, k, rtt):
        return min(self.wait_quantile(lam, mu, k) + TTFT_BASE_S + rtt, 1e5)


class Region:
    """Serving region (edge or cloud) with capacity, service rate, price and carbon parameters."""

    def __init__(self, name, rtt, pue, price_trace, carbon_trace, mu, max_k):
        self.name = name
        self.rtt = rtt
        self.pue = pue
        self.price_trace = price_trace
        self.carbon_trace = carbon_trace
        self.mu = mu
        self.max_k = max_k

        self.current_k = 0
        self.current_lambda = 0.0

        self.available_k = 0
        self.pending_activations = []


class EnergyCostCarbonModel:
    """Converts provisioned and busy capacity into energy, cost and carbon per interval."""

    def __init__(self, interval_seconds=30, busy_power=180.0, idle_power=120.0):
        self.interval = interval_seconds
        self.busy_power = busy_power
        self.idle_power = idle_power

    def compute(self, region, lam, mu, k, price, carbon_intensity):

        if k <= 0:
            return {"power": 0.0, "energy_kwh": 0.0, "cost": 0.0, "carbon": 0.0, "busy": 0.0, "idle": 0.0}
        util = min(1.0, lam / (k * mu))
        busy = k * util
        idle = k - busy
        raw_power = busy * self.busy_power + idle * self.idle_power
        power = raw_power * region.pue
        energy_kwh = power * self.interval / 3600.0 / 1000.0
        cost = energy_kwh * price
        carbon = energy_kwh * carbon_intensity
        return {
            "power": power,
            "energy_kwh": energy_kwh,
            "cost": cost,
            "carbon": carbon,
            "busy": busy,
            "idle": idle,
        }


class GuardrailCalculator:
    """Minimum capacity that keeps the p99 TTFT and p99 latency of a region within the SLO
    for a given routed load, inflated by a safety margin."""

    def __init__(self, table, lambda_axis, max_k, slo_latency, slo_ttft, mu, rtt_ms=0.0, safety_margin=1.5):
        self.max_k = max_k
        self.slo_latency_sec = slo_latency / 1000.0
        self.slo_ttft_sec = slo_ttft / 1000.0
        self.ec = ErlangC()
        self.mu = mu
        self.rtt = rtt_ms / 1000.0
        self.safety_margin = safety_margin

    def min_feasible_k(self, lam):
        """Smallest k meeting both p99 targets, before the safety margin."""
        if lam <= 0:
            return 1
        mu, a = self.mu, lam / self.mu
        service = 1.0 / mu
        B = 1.0
        for k in range(1, self.max_k + 1):
            B = a * B / (k + a * B)
            rho = lam / (k * mu)
            if rho >= OVERLOAD_RHO:
                continue
            C = erlang_c_from_b(B, rho)
            gap = k * mu - lam
            w99 = 0.0 if C <= 0.01 else math.log(C / 0.01) / gap
            if (
                w99 + service + self.rtt <= self.slo_latency_sec
                and w99 + TTFT_BASE_S + self.rtt <= self.slo_ttft_sec
            ):
                return k
        return self.max_k

    def compute_k_gr(self, lam):
        k_final = int(np.ceil(self.min_feasible_k(lam) * self.safety_margin))
        return int(min(max(k_final, 1), self.max_k))


class PlacementOptimizerHorizon:
    """Receding-horizon capacity search over a short forecast window."""

    def __init__(self, sim_config, energy_model):
        self.sim_config = sim_config
        self.energy_model = energy_model

    def solve(
        self,
        regions,
        clusters,
        predicted_arrivals_horizon,
        guardrail_k,
        alpha,
        prices_trace,
        carbon_trace,
        rtt_budget,
    ):

        horizon = len(predicted_arrivals_horizon)
        region_names = [r.name for r in regions]

        k_decision = {r.name: guardrail_k[r.name] for r in regions}

        routing_fraction = {}

        for cluster in clusters:
            nearest_rtt = min(cluster.rtt_to_region_ms.values())

            feasible_regions = []
            for r in regions:
                if cluster.rtt_to_region_ms[r.name] <= nearest_rtt + rtt_budget:
                    feasible_regions.append(r)

            max_price = max(prices_trace[r.name] for r in feasible_regions) + 1e-9
            max_carbon = max(carbon_trace[r.name] for r in feasible_regions) + 1e-9

            weights = {}
            for r in feasible_regions:
                price = prices_trace[r.name]
                carbon = carbon_trace[r.name]

                objective_coeff = (price / max_price) + alpha * (carbon / max_carbon)

                weights[r.name] = 1.0 / max(objective_coeff, 1e-9)

            total_w = sum(weights.values())
            routing_fraction[cluster.name] = {r: weights[r] / total_w for r in weights}

        total_objective = 0.0

        for t in range(horizon):
            arrivals_t = predicted_arrivals_horizon[t]

            lambda_region = {r: 0.0 for r in region_names}

            for cluster in clusters:
                lam_c = arrivals_t[cluster.name]
                for r in routing_fraction[cluster.name]:
                    lambda_region[r] += lam_c * routing_fraction[cluster.name][r]

            for r in regions:
                lam_r = lambda_region[r.name]
                mu = r.mu
                k = max(guardrail_k[r.name], 1)

                result = self.energy_model.compute(
                    region=r,
                    lam=lam_r,
                    mu=mu,
                    k=k,
                    price=prices_trace[r.name],
                    carbon_intensity=carbon_trace[r.name],
                )

                total_objective += result["cost"] + alpha * result["carbon"] * 1e-3

        return k_decision, routing_fraction


class MPCController:
    """Routing and capacity planner of SLA-Guarded.

    Routing assigns each user cluster to the admissible region (within the RTT budget)
    with the lowest normalized cost-carbon score, subject to the per-region guardrail
    on routed load. Capacity is chosen by a receding-horizon search with a churn
    penalty. Cold-start-aware switching keeps traffic on the current region until the
    target region has warm capacity."""

    def __init__(
        self,
        sim_config,
        optimizer=None,
        energy_model=None,
        eta=0.02,
        k_search_margin=12,
        use_forecast=True,
        routing_mode="inverse",
        routing_beta=0.15,
        prewarm=False,
    ):
        self.sim_config = sim_config

        self.use_forecast = use_forecast
        self.routing_mode = routing_mode
        self.prewarm = prewarm
        self._assigned = {}
        self._routed_prev = {}
        self._pending_age = {}
        self.prewarm_timeout = 10
        self._ranked = {}
        self.max_utilization = 0.92
        self.capacity_aware = True
        self.profile = None

        if optimizer is None:
            self.optimizer = self._default_optimizer
        else:
            self.optimizer = optimizer

        self.hysteresis = HysteresisFilter()

        self.alpha_tradeoff = sim_config.alpha_tradeoff

        self.beta = 0.65
        self.horizon = sim_config.horizon_steps

        self.eta = eta

        self.k_search_margin = k_search_margin

        self.energy_model = energy_model

        self._prev_lambda_region = {}
        self._prev_k_region = {}

        self.routing_beta = routing_beta
        self._prev_routing = {}

    def _forecast_region_horizon(self, lambda_region_now):
        forecast = {}
        if not self.use_forecast:
            return {r_name: [lam_now] for r_name, lam_now in lambda_region_now.items()}
        for r_name, lam_now in lambda_region_now.items():
            prev_ewma = self._prev_lambda_region.get(r_name, lam_now)
            ewma_now = self.beta * lam_now + (1 - self.beta) * prev_ewma
            self._prev_lambda_region[r_name] = ewma_now

            horizon_value = max(ewma_now, lam_now)
            forecast[r_name] = [horizon_value] * self.horizon
        return forecast

    def _solve_region_capacity_horizon(
        self, region, guard_k, forecast_lambdas, price, carbon, energy_model, max_utilization=None
    ):
        if max_utilization is None:
            max_utilization = self.max_utilization
        prev_k = self._prev_k_region.get(region.name, guard_k)
        k_min = max(int(guard_k), 1)
        worst_lambda = max(forecast_lambdas) if forecast_lambdas else 0.0

        def is_feasible(k):
            return worst_lambda / max(k * region.mu, 1e-9) < max_utilization

        k_max = min(region.max_k, k_min + self.k_search_margin)

        while not is_feasible(k_max) and k_max < region.max_k:
            k_max = min(region.max_k, k_max + self.k_search_margin)

        best_k = None
        best_obj = float("inf")
        for k in range(k_min, k_max + 1):
            if not is_feasible(k):
                continue
            obj = 0.0
            for lam_hat in forecast_lambdas:
                res = energy_model.compute(
                    region=region,
                    lam=lam_hat,
                    mu=region.mu,
                    k=k,
                    price=price,
                    carbon_intensity=carbon,
                )
                obj += (1 - self.alpha_tradeoff) * res["cost"] + self.alpha_tradeoff * res["carbon"] * 1e-3
            obj += self.eta * abs(k - prev_k)
            if obj < best_obj:
                best_obj = obj
                best_k = k

        if best_k is None:

            best_k = region.max_k

        self._prev_k_region[region.name] = best_k
        return best_k

    def _default_optimizer(
        self, regions, guardrails, prices, carbons, lambda_pred, rtt_matrix, nearest_region, rtt_budget
    ):

        routing = {}

        for cluster_name, lam in lambda_pred.items():
            nr = nearest_region[cluster_name]
            base_rtt = rtt_matrix[cluster_name][nr]

            feasible = []
            for r in regions:
                if rtt_matrix[cluster_name][r.name] <= base_rtt + rtt_budget:
                    feasible.append(r.name)

            max_price = max(prices[rn] for rn in feasible) + 1e-9
            max_carbon = max(carbons[rn] for rn in feasible) + 1e-9
            a = self.alpha_tradeoff
            score = {
                rn: (1 - a) * (prices[rn] / max_price) + a * (carbons[rn] / max_carbon) for rn in feasible
            }
            if self.routing_mode == "argmin":
                self._ranked[cluster_name] = sorted(feasible, key=lambda rn: score[rn])
                best = self._ranked[cluster_name][0]
                routing[cluster_name] = {r.name: float(r.name == best) for r in regions}
                continue
            weights = {rn: 1.0 / max(score[rn], 1e-9) for rn in feasible}

            denom = sum(weights.values())
            if denom < 1e-12:
                routing[cluster_name] = {r.name: (1.0 if r.name == nr else 0.0) for r in regions}
                continue

            routing[cluster_name] = {}
            for r in regions:
                if r.name in feasible:
                    routing[cluster_name][r.name] = weights[r.name] / denom
                else:
                    routing[cluster_name][r.name] = 0.0

        return routing

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices,
        carbons,
        energy_model,
        rtt_matrix,
        nearest_region,
        rtt_budget,
        **kwargs,
    ):
        _t0 = time.perf_counter()

        raw_routing = self.optimizer(
            regions=regions,
            guardrails=guardrails,
            prices=prices,
            carbons=carbons,
            lambda_pred=current_lambda,
            rtt_matrix=rtt_matrix,
            nearest_region=nearest_region,
            rtt_budget=rtt_budget,
        )

        routing = {}
        for cluster_name, target_fracs in raw_routing.items():
            prev_fracs = self._prev_routing.get(cluster_name, target_fracs)
            blended = {
                rname: self.routing_beta * target_fracs[rname]
                + (1 - self.routing_beta) * prev_fracs.get(rname, target_fracs[rname])
                for rname in target_fracs
            }
            total = sum(blended.values())
            if total > 1e-12:
                blended = {rname: v / total for rname, v in blended.items()}
            routing[cluster_name] = blended
            self._prev_routing[cluster_name] = blended

        guard_fn = kwargs.get("guard_fn")

        if self.routing_mode == "argmin" and self.capacity_aware and guard_fn is not None:
            by_name_ = {r.name: r for r in regions}
            load_ = {r.name: 0.0 for r in regions}
            for c in sorted(current_lambda, key=lambda c: -current_lambda[c]):
                ranked = self._ranked.get(c) or [max(routing[c], key=routing[c].get)]
                choice = ranked[0]
                for rn in ranked:
                    if guard_fn(rn, load_[rn] + current_lambda[c]) < by_name_[rn].max_k:
                        choice = rn
                        break
                load_[choice] += current_lambda[c]
                routing[c] = {rn: float(rn == choice) for rn in routing[c]}

        prewarm_extra = {r.name: 0.0 for r in regions}
        if self.routing_mode == "argmin" and self.prewarm:
            by_name = {r.name: r for r in regions}
            routed_now = {r.name: 0.0 for r in regions}
            for c, fr in routing.items():
                for rn, f in fr.items():
                    routed_now[rn] += current_lambda[c] * f
            for c in list(routing.keys()):
                best = max(routing[c], key=routing[c].get)
                cur = self._assigned.get(c, best)
                if best != cur:
                    lam_c = current_lambda[c]
                    need = (
                        guard_fn(best, self._routed_prev.get(best, 0.0) + lam_c)
                        if guard_fn is not None
                        else 1
                    )
                    age = self._pending_age.get(c, 0) + 1

                    if by_name[best].available_k >= need or age > self.prewarm_timeout:
                        cur = best
                        self._pending_age[c] = 0
                    else:
                        self._pending_age[c] = age
                        prewarm_extra[best] += lam_c
                        routing[c] = {rn: float(rn == cur) for rn in routing[c]}
                else:
                    self._pending_age[c] = 0
                self._assigned[c] = cur

        lambda_region_now = {}
        for r in regions:
            lambda_region_now[r.name] = sum(current_lambda[c] * routing[c][r.name] for c in current_lambda)
        self._routed_prev = dict(lambda_region_now)

        provision_lambda = {rn: lambda_region_now[rn] + prewarm_extra[rn] for rn in lambda_region_now}

        forecast_per_region = self._forecast_region_horizon(provision_lambda)

        _t2 = time.perf_counter()
        if guard_fn is not None:
            guardrails = {r.name: guard_fn(r.name, provision_lambda[r.name]) for r in regions}
        _t3 = time.perf_counter()

        k_proposed = {}
        for r in regions:
            guard_k = guardrails[r.name]
            k_proposed[r.name] = self._solve_region_capacity_horizon(
                region=r,
                guard_k=guard_k,
                forecast_lambdas=forecast_per_region[r.name],
                price=prices[r.name],
                carbon=carbons[r.name],
                energy_model=energy_model,
            )
        if self.profile is not None:
            _t4 = time.perf_counter()
            for key, dt in (("routing", _t2 - _t0), ("guardrail", _t3 - _t2), ("capacity_search", _t4 - _t3)):
                self.profile[key] = self.profile.get(key, 0.0) + dt

        return k_proposed, routing


class HysteresisFilter:
    """Deadband filter on capacity changes.

    mode='relative': with base = current capacity k, changes smaller than
    low_ratio * k are suppressed, changes of at least high_ratio * k are applied
    in full, and intermediate changes are applied as a partial step.
    mode='absolute': the same rule with thresholds relative to ref_capacity."""

    def __init__(self, low_ratio=0.05, high_ratio=0.10, mode="absolute", ref_capacity=None):
        self.low_ratio = low_ratio
        self.high_ratio = high_ratio
        self.mode = mode
        self.ref_capacity = ref_capacity

    def apply(self, previous_k, proposed_k, max_capacity):
        if self.mode == "relative":
            return self._apply_relative(previous_k, proposed_k)
        if self.ref_capacity is not None:
            max_capacity = {r: self.ref_capacity for r in previous_k}
        return self._apply_absolute(previous_k, proposed_k, max_capacity)

    def _apply_relative(self, previous_k, proposed_k):
        filtered = {}
        for r in previous_k:
            k_prev, k_new = previous_k[r], proposed_k[r]
            base = max(k_prev, 1)
            low_thr, high_thr = self.low_ratio * base, self.high_ratio * base
            delta = k_new - k_prev
            if abs(delta) <= low_thr:
                filtered[r] = k_prev
            elif abs(delta) >= high_thr:
                filtered[r] = k_new
            else:
                step = max(1, int(abs(delta) / high_thr * low_thr))
                filtered[r] = k_prev + step if delta > 0 else k_prev - step
        return filtered

    def _apply_absolute(self, previous_k, proposed_k, max_capacity):

        filtered = {}
        for r in previous_k:
            k_prev = previous_k[r]
            k_new = proposed_k[r]
            cap = max_capacity[r]
            low_thr = self.low_ratio * cap
            high_thr = self.high_ratio * cap
            delta = k_new - k_prev
            if abs(delta) <= low_thr:
                filtered[r] = k_prev
            elif abs(delta) >= high_thr:
                filtered[r] = k_new
            else:
                step = int(abs(delta) / high_thr * low_thr)
                if delta > 0:
                    filtered[r] = k_prev + step
                else:
                    filtered[r] = k_prev - step
        return filtered


class SLAController:
    """SLA-Guarded controller: MPC planner followed by the hysteresis filter."""

    def __init__(self, sim_config, mpc, hysteresis, rtt_budget=None, tradeoff=None, horizon=None):

        self.sim_config = sim_config

        self.rtt_budget_ms = rtt_budget if rtt_budget is not None else sim_config.rtt_budget_ms

        self.tradeoff = tradeoff if tradeoff is not None else sim_config.alpha_tradeoff

        self.horizon_steps = horizon if horizon is not None else sim_config.horizon_steps

        self.mpc = mpc
        self.hysteresis = hysteresis

        if hasattr(self.mpc, "alpha_tradeoff"):
            self.mpc.alpha_tradeoff = self.tradeoff

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices,
        carbons,
        energy_model,
        rtt_matrix,
        nearest_region,
        **kwargs,
    ):

        k_next, routing = self.mpc.control_step(
            regions=regions,
            current_lambda=current_lambda,
            guardrails=guardrails,
            prices=prices,
            carbons=carbons,
            energy_model=energy_model,
            rtt_matrix=rtt_matrix,
            nearest_region=nearest_region,
            rtt_budget=self.rtt_budget_ms,
            guard_fn=kwargs.get("guard_fn"),
        )

        return k_next, routing


def routed_guard(kwargs, guardrails, region, routed_lambda):
    """Guardrail lower bound evaluated on the load actually routed to a region."""
    guard_fn = kwargs.get("guard_fn")
    if guard_fn is None:
        return guardrails[region.name]
    return guard_fn(region.name, routed_lambda)


class LatencyFirstController:
    """Baseline: routes each cluster to its lowest-RTT region."""

    def __init__(self):
        self.hysteresis = NoHysteresis()

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices=None,
        carbons=None,
        energy_model=None,
        rtt_matrix=None,
        nearest_region=None,
        rtt_budget=None,
        **kwargs,
    ):

        routing = {}
        k_next = {}

        for cluster_name, lam in current_lambda.items():
            routing[cluster_name] = {}

            nr_name = nearest_region[cluster_name]

            nearest_rtt = rtt_matrix[cluster_name][nr_name]

            feasible_regions = []
            for r in regions:
                rtt = rtt_matrix[cluster_name][r.name]
                if rtt <= nearest_rtt + rtt_budget:
                    feasible_regions.append(r.name)

            for r in regions:
                if r.name == nr_name and r.name in feasible_regions:
                    routing[cluster_name][r.name] = 1.0
                else:
                    routing[cluster_name][r.name] = 0.0

        for r in regions:
            arrival = sum(current_lambda[cname] * routing[cname][r.name] for cname in current_lambda)

            guard_k = routed_guard(kwargs, guardrails, r, arrival)
            load_k = int(np.ceil(arrival / max(r.mu, 1e-9)))

            k_next[r.name] = max(guard_k, load_k)

        return k_next, routing


class CostFirstController:
    """Baseline: routes each cluster to the cheapest admissible region."""

    def __init__(self, sim_config):
        self.sim_config = sim_config
        self.hysteresis = NoHysteresis()

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices=None,
        carbons=None,
        energy_model=None,
        rtt_matrix=None,
        nearest_region=None,
        rtt_budget=None,
        **kwargs,
    ):

        routing = {}
        k_next = {}

        for cluster_name, lam in current_lambda.items():
            routing[cluster_name] = {}

            nr_name = nearest_region[cluster_name]
            nr_rtt = rtt_matrix[cluster_name][nr_name]

            feasible = []
            for r in regions:
                rtt = rtt_matrix[cluster_name][r.name]
                if rtt <= nr_rtt + rtt_budget:
                    feasible.append(r.name)

            cheapest_region = min(feasible, key=lambda rn: prices[rn])

            for r in regions:
                routing[cluster_name][r.name] = 1.0 if r.name == cheapest_region else 0.0

        for r in regions:
            arrival = sum(current_lambda[c] * routing[c][r.name] for c in current_lambda)
            guard_k = routed_guard(kwargs, guardrails, r, arrival)
            load_k = int(np.ceil(arrival / max(r.mu, 1e-9)))
            k_next[r.name] = max(guard_k, load_k)

        return k_next, routing


class RoundRobinController:
    """Baseline: spreads each cluster evenly over its admissible regions."""

    def __init__(self, sim_config):
        self.sim_config = sim_config
        self.hysteresis = NoHysteresis()

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices=None,
        carbons=None,
        energy_model=None,
        rtt_matrix=None,
        nearest_region=None,
        rtt_budget=None,
        **kwargs,
    ):

        routing = {}
        k_next = {}

        for cluster_name, lam in current_lambda.items():
            routing[cluster_name] = {}

            nr_name = nearest_region[cluster_name]
            nr_rtt = rtt_matrix[cluster_name][nr_name]

            feasible_regions_names = []
            for r in regions:
                rtt = rtt_matrix[cluster_name][r.name]
                if rtt <= nr_rtt + rtt_budget:
                    feasible_regions_names.append(r.name)

            if not feasible_regions_names:
                feasible_regions_names = [nr_name]

            weight = 1.0 / len(feasible_regions_names)

            for r in regions:
                if r.name in feasible_regions_names:
                    routing[cluster_name][r.name] = weight
                else:
                    routing[cluster_name][r.name] = 0.0

        for r in regions:
            arrival = sum(current_lambda[c] * routing[c][r.name] for c in current_lambda)
            guard_k = routed_guard(kwargs, guardrails, r, arrival)
            load_k = int(np.ceil(arrival / max(r.mu, 1e-9)))
            k_next[r.name] = max(guard_k, load_k)

        return k_next, routing


class SLOAwareCostController:
    """Baseline in the style of QLM: SLO-aware admission with cost-ordered placement."""

    def __init__(self, sim_config):
        self.sim_config = sim_config
        self.hysteresis = NoHysteresis()
        self.ec = ErlangC()

    def can_meet_slo(self, r, lam, rtt_ms):
        min_k_stable = int(np.ceil(lam / r.mu))

        for k in range(min_k_stable, r.max_k + 1):
            p99_lat = self.ec.p99_latency(lam, r.mu, k, rtt_ms / 1000.0)
            if p99_lat * 1000 <= self.sim_config.p99_latency_slo_ms:
                return True, k

        return False, min_k_stable

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices=None,
        carbons=None,
        energy_model=None,
        rtt_matrix=None,
        nearest_region=None,
        rtt_budget=None,
        **kwargs,
    ):

        routing = {}
        k_next = {}
        assigned = {r.name: 0.0 for r in regions}

        for cluster_name, lam in current_lambda.items():
            routing[cluster_name] = {}
            nr_name = nearest_region[cluster_name]
            nr_rtt = rtt_matrix[cluster_name][nr_name]

            feasible = [r for r in regions if rtt_matrix[cluster_name][r.name] <= nr_rtt + rtt_budget]
            if not feasible:
                feasible = [next(r for r in regions if r.name == nr_name)]

            slo_safe_regions = []
            for r in feasible:
                actual_rtt = rtt_matrix[cluster_name][r.name]
                can_meet, _ = self.can_meet_slo(r, assigned[r.name] + lam, actual_rtt)
                if can_meet:
                    slo_safe_regions.append(r)

            if slo_safe_regions:
                selected_region = min(slo_safe_regions, key=lambda rr: prices[rr.name])
            else:
                selected_region = next(r for r in feasible if r.name == nr_name)

            for r in regions:
                routing[cluster_name][r.name] = 1.0 if r.name == selected_region.name else 0.0
            assigned[selected_region.name] += lam

        for r in regions:
            arrival = assigned[r.name]
            k_next[r.name] = max(
                routed_guard(kwargs, guardrails, r, arrival), int(np.ceil(arrival / max(r.mu, 1e-9))), 1
            )

        return k_next, routing


class SOLAStyleController:
    """Baseline in the style of SOLA: SLO-attainment-driven placement and scaling."""

    def __init__(self, sim_config):
        self.sim_config = sim_config
        self.hysteresis = NoHysteresis()
        self.ec = ErlangC()

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices=None,
        carbons=None,
        energy_model=None,
        rtt_matrix=None,
        nearest_region=None,
        rtt_budget=None,
        **kwargs,
    ):

        routing = {}
        k_next = {}
        assigned = {r.name: 0.0 for r in regions}

        for cluster_name, lam in current_lambda.items():
            routing[cluster_name] = {}
            nr_name = nearest_region[cluster_name]
            nr_rtt = rtt_matrix[cluster_name][nr_name]

            feasible = [r for r in regions if rtt_matrix[cluster_name][r.name] <= nr_rtt + rtt_budget]
            if not feasible:
                feasible = [next(r for r in regions if r.name == nr_name)]

            best_region = None
            best_ttft = float("inf")
            for r in feasible:
                actual_rtt = rtt_matrix[cluster_name][r.name]
                k = max(getattr(r, "available_k", 0), 1)
                p99_ttft = self.ec.p99_ttft(assigned[r.name] + lam, r.mu, k, actual_rtt / 1000.0)
                if p99_ttft < best_ttft:
                    best_ttft = p99_ttft
                    best_region = r

            for r in regions:
                routing[cluster_name][r.name] = 1.0 if r.name == best_region.name else 0.0
            assigned[best_region.name] += lam

        for r in regions:
            arrival = assigned[r.name]
            k_next[r.name] = max(
                routed_guard(kwargs, guardrails, r, arrival), int(np.ceil(arrival / max(r.mu, 1e-9))), 1
            )

        return k_next, routing


class CarbonFirstController:
    """Baseline: routes each cluster to the lowest-carbon admissible region."""

    def __init__(self, sim_config):
        self.sim_config = sim_config
        self.hysteresis = NoHysteresis()

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices=None,
        carbons=None,
        energy_model=None,
        rtt_matrix=None,
        nearest_region=None,
        rtt_budget=None,
        **kwargs,
    ):

        routing = {}
        k_next = {}

        for cluster_name, lam in current_lambda.items():
            routing[cluster_name] = {}

            nr_name = nearest_region[cluster_name]
            nr_rtt = rtt_matrix[cluster_name][nr_name]

            feasible = []
            for r in regions:
                rtt = rtt_matrix[cluster_name][r.name]
                if rtt <= nr_rtt + rtt_budget:
                    feasible.append(r.name)

            greenest_region = min(feasible, key=lambda rn: carbons[rn])

            for r in regions:
                routing[cluster_name][r.name] = 1.0 if r.name == greenest_region else 0.0

        for r in regions:
            arrival = sum(current_lambda[c] * routing[c][r.name] for c in current_lambda)
            guard_k = routed_guard(kwargs, guardrails, r, arrival)
            load_k = int(np.ceil(arrival / max(r.mu, 1e-9)))
            k_next[r.name] = max(guard_k, load_k)

        return k_next, routing


class ThresholdBasedController:
    """
    ThresholdBased (Reactive) Baseline: Mimics industry-standard reactive auto-scalers
    (e.g., Kubernetes HPA).

    Uses max(r.current_k, guardrails[r.name]) as effective capacity to avoid
    bootstrap deadlock in the first control step when current_k=0, so the
    policy can accept initial traffic and begin reactive scaling, just like
    other baseline policies that use guardrails as a minimum capacity floor.
    """

    def __init__(self, sim_config, stabilization_steps=0):
        self.sim_config = sim_config
        self.hysteresis = NoHysteresis()
        self.routing_util_threshold = 0.80
        self.util_high = 0.85
        self.util_target = 0.70
        self.util_low = 0.50
        self.stabilization_steps = stabilization_steps
        self._rec_hist = {}

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices=None,
        carbons=None,
        energy_model=None,
        rtt_matrix=None,
        nearest_region=None,
        rtt_budget=None,
        **kwargs,
    ):
        routing = {}
        k_next = {}
        assigned_lambda_r = {r.name: 0.0 for r in regions}

        for cluster_name, lam in current_lambda.items():
            routing[cluster_name] = {r.name: 0.0 for r in regions}
            if lam <= 1e-9:
                continue

            nr_name = nearest_region[cluster_name]
            nr_rtt = rtt_matrix[cluster_name][nr_name]
            feasible = [r for r in regions if rtt_matrix[cluster_name][r.name] <= nr_rtt + rtt_budget]
            if not feasible:
                feasible = [next(r for r in regions if r.name == nr_name)]

            alpha = self.sim_config.alpha_tradeoff
            max_p = max(prices[r.name] for r in feasible) + 1e-9
            max_c = max(carbons[r.name] for r in feasible) + 1e-9

            def score(r):
                return (1 - alpha) * (prices[r.name] / max_p) + alpha * (carbons[r.name] / max_c)

            feasible.sort(key=score)

            remaining_lam = lam
            for r in feasible:
                if remaining_lam <= 1e-9:
                    break
                effective_k = max(r.current_k, 1)
                max_lam_for_threshold = self.routing_util_threshold * effective_k * r.mu
                available_lam = max(0.0, max_lam_for_threshold - assigned_lambda_r[r.name])
                assign_lam = min(remaining_lam, available_lam)
                if assign_lam > 1e-9:
                    routing[cluster_name][r.name] += assign_lam / lam
                    assigned_lambda_r[r.name] += assign_lam
                    remaining_lam -= assign_lam

            if remaining_lam > 1e-9:

                def headroom(r):
                    return max(r.current_k, 1) * r.mu - assigned_lambda_r[r.name]

                tgt = max(feasible, key=headroom)
                routing[cluster_name][tgt.name] += remaining_lam / lam
                assigned_lambda_r[tgt.name] += remaining_lam

        for r in regions:
            arrival = assigned_lambda_r[r.name]
            effective_k = max(r.current_k, 1)
            util = arrival / max(effective_k * r.mu, 1e-9)

            if util > self.util_high:
                rec = int(np.ceil(arrival / (self.util_target * r.mu)))
            elif util < self.util_low:
                rec = max(1, int(np.ceil(arrival / (0.60 * r.mu))))
            else:
                rec = effective_k
            rec = max(rec, int(np.ceil(arrival / max(r.mu, 1e-9))), 1)

            if self.stabilization_steps > 0:
                hist = self._rec_hist.setdefault(r.name, [])
                hist.append(rec)
                del hist[: -self.stabilization_steps]
                rec = max(hist)
            k_next[r.name] = rec

        return k_next, routing


class CarbonAdvisorStyleController:
    """
    CarbonAdvisor-Style Baseline: Adapts the core spatial-shifting logic of
    state-of-the-art carbon-aware schedulers (e.g., CarbonAdvisor, GEM) to
    the edge-cloud LLM setting.
    - Routing: Aggressively shifts traffic to the RTT-feasible region with the
      lowest predicted carbon intensity over the next H steps.
    - Capacity: Reactively scales based on immediate load to meet the shifted
      demand, WITHOUT the SLO-prioritized queueing guardrails or hysteresis
      smoothing used in SLA-Guarded.
    - Purpose: Demonstrates that simply applying advanced carbon-aware routing
      to LLM workloads is insufficient and leads to high SLO violations due
      to unmanaged queueing pressure and cold-start scaling churn.
    """

    def __init__(self, sim_config):
        self.sim_config = sim_config
        self.hysteresis = NoHysteresis()
        self.horizon = sim_config.horizon_steps

    def control_step(
        self,
        regions,
        current_lambda,
        guardrails,
        prices=None,
        carbons=None,
        energy_model=None,
        rtt_matrix=None,
        nearest_region=None,
        rtt_budget=None,
        **kwargs,
    ):
        routing = {}
        k_next = {}

        assigned_lambda_r = {r.name: 0.0 for r in regions}

        for cluster_name, lam in current_lambda.items():
            routing[cluster_name] = {r.name: 0.0 for r in regions}
            if lam <= 1e-9:
                continue

            nr_name = nearest_region[cluster_name]
            nr_rtt = rtt_matrix[cluster_name][nr_name]
            feasible = [r for r in regions if rtt_matrix[cluster_name][r.name] <= nr_rtt + rtt_budget]
            if not feasible:
                feasible = [next(r for r in regions if r.name == nr_name)]

            feasible.sort(key=lambda r: carbons[r.name])

            greenest_region = feasible[0]
            routing[cluster_name][greenest_region.name] = 1.0
            assigned_lambda_r[greenest_region.name] += lam

        for r in regions:
            arrival = assigned_lambda_r[r.name]
            if arrival > 1e-9:
                k_next[r.name] = max(1, int(np.ceil(arrival / (0.70 * r.mu))))
            else:
                k_next[r.name] = 1

        return k_next, routing


@dataclass
class UserClusterConfig:
    """User cluster with its RTT to every region."""

    name: str
    rtt_to_region_ms: Dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationConfig:
    """Global simulation parameters (horizon, control interval, SLO targets, alpha)."""

    control_interval_s: float = 30.0
    horizon_steps: int = 8
    total_steps: int = 2880
    p99_latency_slo_ms: float = 30000.0
    ttft_p99_slo_ms: float = 3000.0
    rtt_budget_ms: float = 20.0
    alpha_tradeoff: float = 0.5
    lambda_reg: float = 0.1


def build_rtt_matrix(clusters, regions):
    """RTT matrix between user clusters and regions, and the nearest region per cluster."""
    rtt_matrix = {}
    nearest_region = {}
    for c in clusters:
        rtt_matrix[c.name] = {}
        min_rtt = 1e9
        nearest = None
        for r in regions:
            rtt = c.rtt_to_region_ms[r.name]
            rtt_matrix[c.name][r.name] = rtt
            if rtt < min_rtt:
                min_rtt = rtt
                nearest = r.name
        nearest_region[c.name] = nearest
    return rtt_matrix, nearest_region


def create_default_topology(
    avg_response_tokens=300, max_k=4096
) -> Tuple[List[Region], List[UserClusterConfig]]:
    """Default scenario: two edge regions and two cloud regions with four user clusters."""
    mu_edge = calculate_effective_mu(token_rate=50.0, avg_response_tokens=avg_response_tokens)
    mu_cloud = calculate_effective_mu(token_rate=70.0, avg_response_tokens=avg_response_tokens)

    regions = [
        Region(
            name="edge_1",
            rtt=20.0,
            max_k=max_k,
            pue=1.40,
            price_trace=0.70,
            carbon_trace=850.0,
            mu=mu_edge,
        ),
        Region(
            name="edge_2",
            rtt=28.0,
            max_k=max_k,
            pue=1.40,
            price_trace=0.65,
            carbon_trace=900.0,
            mu=mu_edge,
        ),
        Region(
            name="cloud_1",
            rtt=35.0,
            max_k=max_k,
            pue=1.20,
            price_trace=0.12,
            carbon_trace=750.0,
            mu=mu_cloud,
        ),
        Region(
            name="cloud_2",
            rtt=38.0,
            max_k=max_k,
            pue=1.10,
            price_trace=0.55,
            carbon_trace=50.0,
            mu=mu_cloud,
        ),
    ]

    clusters = []
    c1 = UserClusterConfig(name="cluster_north")
    c1.rtt_to_region_ms = {"edge_1": 20.0, "edge_2": 28.0, "cloud_1": 35.0, "cloud_2": 38.0}
    clusters.append(c1)

    c2 = UserClusterConfig(name="cluster_south")
    c2.rtt_to_region_ms = {"edge_1": 32.0, "edge_2": 22.0, "cloud_1": 38.0, "cloud_2": 40.0}
    clusters.append(c2)

    c3 = UserClusterConfig(name="cluster_central")
    c3.rtt_to_region_ms = {"edge_1": 24.0, "edge_2": 26.0, "cloud_1": 32.0, "cloud_2": 36.0}
    clusters.append(c3)

    c4 = UserClusterConfig(name="cluster_remote")
    c4.rtt_to_region_ms = {"edge_1": 42.0, "edge_2": 48.0, "cloud_1": 55.0, "cloud_2": 68.0}
    clusters.append(c4)

    return regions, clusters


def create_scaled_topology(n_regions, n_clusters, avg_response_tokens=300, max_k=4096, seed=0):
    """Parametrized topology generator for the scalability experiment
    . Generates n_regions regions and n_clusters user
     clusters with price, carbon, RTT, and PUE values drawn from the same
     ranges used in the hand-crafted 4-region default topology (price
     0.10-0.75 USD/unit, carbon 50-900 g/kWh-equivalent, RTT 15-70 ms
     inter-cluster, alternating edge/cloud service rates and PUE), so that
     quality metrics remain comparable in kind as region count grows. Half
     the regions are "edge"-like (higher PUE, lower mu, tighter base RTT)
     and half are "cloud"-like (lower PUE, higher mu, wider base RTT),
     matching the qualitative edge/cloud split of the default topology.
    """
    rng = np.random.RandomState(seed)
    mu_edge = calculate_effective_mu(token_rate=50.0, avg_response_tokens=avg_response_tokens)
    mu_cloud = calculate_effective_mu(token_rate=70.0, avg_response_tokens=avg_response_tokens)

    regions = []
    for i in range(n_regions):
        is_edge = i < (n_regions + 1) // 2
        regions.append(
            Region(
                name=f"region_{i}",
                rtt=float(rng.uniform(15.0, 30.0) if is_edge else rng.uniform(30.0, 45.0)),
                max_k=max_k,
                pue=float(rng.uniform(1.25, 1.45) if is_edge else rng.uniform(1.05, 1.25)),
                price_trace=float(rng.uniform(0.45, 0.75) if is_edge else rng.uniform(0.10, 0.55)),
                carbon_trace=float(rng.uniform(600.0, 900.0) if is_edge else rng.uniform(50.0, 750.0)),
                mu=mu_edge if is_edge else mu_cloud,
            )
        )

    clusters = []
    for j in range(n_clusters):
        c = UserClusterConfig(name=f"cluster_{j}")
        c.rtt_to_region_ms = {r.name: float(max(5.0, r.rtt + rng.uniform(-8.0, 20.0))) for r in regions}
        clusters.append(c)

    return regions, clusters


class SLASimulator:
    """Discrete-time simulator with 30 s control intervals.

    Each interval: generate arrivals, ask the controller for routing and capacity,
    apply cold-start delays, evaluate tail latency per region with the M/M/k model,
    and record SLO violations, cost and carbon."""

    def __init__(
        self,
        sim_config: SimulationConfig,
        sla_controller,
        regions: List[Region],
        clusters: List[UserClusterConfig],
        energy_model,
        base_lambda_per_cluster,
        guardrail_calculator,
        rtt_budget_ms: float = None,
        policy_name=None,
        trace_seed: int = 42,
        warmup_steps: int = 2,
        use_routed_guardrail: bool = True,
        warmup_sampler=None,
        scaledown_delay_steps: int = 0,
        bill_from_launch: bool = True,
    ):
        self.use_routed_guardrail = use_routed_guardrail

        self.warmup_sampler = warmup_sampler
        self.scaledown_delay_steps = scaledown_delay_steps
        self.bill_from_launch = bill_from_launch
        self._warm_rng = np.random.RandomState(10_000 + int(trace_seed))
        self._k_decisions = {}
        self.profile = None
        self.sim_config = sim_config
        self.controller = sla_controller
        self.regions = regions
        self.clusters = clusters
        self.energy_model = energy_model
        self.base_lambda_per_cluster = base_lambda_per_cluster
        self.guardrail_calculator = guardrail_calculator
        self.rtt_budget_ms = rtt_budget_ms if rtt_budget_ms is not None else sim_config.rtt_budget_ms

        self.warmup_steps = warmup_steps
        self.policy_name = policy_name
        self.rtt_matrix, self.nearest_region = build_rtt_matrix(clusters, regions)
        self.trace_generator = RealisticTraceGenerator(
            total_steps=sim_config.total_steps,
            interval_s=sim_config.control_interval_s,
            regions=regions,
            seed=trace_seed,
        )
        self.current_step = 0
        self.time_s = 0.0
        self.workload_gen = None
        self.history = {
            "p99_latency_ms": [],
            "p99_ttft_ms": [],
            "slo_violation": [],
            "total_energy_kwh": [],
            "total_cost_usd": [],
            "total_carbon_g": [],
            "k_per_region": [],
            "routing_fraction": [],
            "scaling_changes": [],
            "routing_changes": [],
            "lambda_per_region": [],
            "lambda_per_cluster": [],
            "energy_per_region": [],
            "cost_per_region": [],
            "carbon_per_region": [],
            "p99_latency_per_region_ms": [],
            "p99_ttft_per_region_ms": [],
            "total_requests_per_step": [],
            "available_k_per_region": [],
            "violating_requests_per_step": [],
        }

        self.prev_routing = None
        self.prices = None
        self.carbons = None

    def _run_single_step(self):
        if self.workload_gen is None:
            raise RuntimeError("workload_gen must be attached before run()")
        cluster_arrivals = self.workload_gen.sample_arrival_rates(step=self.current_step)
        step_requests = sum(cluster_arrivals.values()) * self.sim_config.control_interval_s
        lam_r_initial = self._initial_region_lambda(cluster_arrivals)
        guardrails = {}
        for r in self.regions:
            guardrails[r.name] = self.guardrail_calculator[r.name].compute_k_gr(lam_r_initial[r.name])
        self.prices, self.carbons = self.trace_generator.get(self.current_step)

        k_prop, x_next = self.controller.control_step(
            regions=self.regions,
            current_lambda=cluster_arrivals,
            guardrails=guardrails,
            prices=self.prices,
            carbons=self.carbons,
            energy_model=self.energy_model,
            rtt_matrix=self.rtt_matrix,
            nearest_region=self.nearest_region,
            rtt_budget=self.rtt_budget_ms,
            clusters=self.clusters,
            guard_fn=self._guard_fn if self.use_routed_guardrail else None,
        )

        for c, fr in x_next.items():
            tot = sum(fr.values())
            if cluster_arrivals.get(c, 0) > 1e-9 and abs(tot - 1.0) > 1e-6:
                raise AssertionError(f"routing fractions of {c} sum to {tot:.4f}, not 1")

        if self.prev_routing is None:
            route_changes = 0
        else:
            route_changes = 0
            for c in x_next:
                for r in x_next[c]:
                    if abs(x_next[c][r] - self.prev_routing[c][r]) > ROUTING_CHANGE_TOL:
                        route_changes += 1
        self.history["routing_changes"].append(route_changes)
        self.prev_routing = x_next
        lam_r = self._route_cluster_to_region(cluster_lambdas=cluster_arrivals, routing=x_next)
        prev_k = {r.name: r.current_k for r in self.regions}
        max_k = {r.name: r.max_k for r in self.regions}
        _th = time.perf_counter()
        final_k = self.controller.hysteresis.apply(
            previous_k=prev_k,
            proposed_k=k_prop,
            max_capacity=max_k,
        )
        if self.profile is not None:
            self.profile["hysteresis"] = self.profile.get("hysteresis", 0.0) + time.perf_counter() - _th
        if self.scaledown_delay_steps > 0:
            for rn in final_k:
                hist_k = self._k_decisions.setdefault(rn, [])
                hist_k.append(final_k[rn])
                del hist_k[: -(self.scaledown_delay_steps + 1)]
                final_k[rn] = max(hist_k)
        scale_changes = sum(int(prev_k[r] != final_k[r]) for r in prev_k)
        self.history["scaling_changes"].append(scale_changes)
        for r in self.regions:
            new_k = final_k[r.name]
            r.current_k = new_k

            if new_k <= r.available_k:

                r.available_k = new_k
                r.pending_activations = [(step, k) for (step, k) in r.pending_activations if k <= new_k]
            else:

                delay = (
                    self.warmup_steps
                    if self.warmup_sampler is None
                    else int(self.warmup_sampler(self._warm_rng))
                )
                activation_step = self.current_step + delay
                r.pending_activations.append((activation_step, new_k))
                r.pending_activations = [
                    (step, k) for (step, k) in r.pending_activations if k > r.available_k
                ]
        for r in self.regions:
            matured = [k for (step, k) in r.pending_activations if step <= self.current_step]
            if matured:
                r.available_k = max(matured)
                r.pending_activations = [
                    (step, k) for (step, k) in r.pending_activations if step > self.current_step
                ]

        metrics = self._compute_step_metrics(
            lambda_region=lam_r, routing=x_next, prices=self.prices, carbons=self.carbons
        )
        self._record_history(
            metrics,
            final_k,
            lambda_region=lam_r,
            lambda_cluster=cluster_arrivals,
            total_requests=step_requests,
        )
        self.history["routing_fraction"].append(x_next.copy())
        self.time_s += self.sim_config.control_interval_s
        self.current_step += 1

        return True

    def _guard_fn(self, region_name, routed_lambda):
        return self.guardrail_calculator[region_name].compute_k_gr(routed_lambda)

    def run(self, num_steps: int, seed: int = 0):
        np.random.seed(seed)
        self.current_step = 0
        self.time_s = 0.0
        for _ in range(num_steps):
            self._run_single_step()
        return self.history

    def _initial_region_lambda(self, cluster_lambdas):
        region_lambda = {r.name: 0.0 for r in self.regions}
        for c_name, lam_c in cluster_lambdas.items():
            nr = self.nearest_region[c_name]
            region_lambda[nr] += lam_c
        return region_lambda

    def _route_cluster_to_region(self, cluster_lambdas, routing):
        region_lambda = {r.name: 0.0 for r in self.regions}
        for c_name, lam_c in cluster_lambdas.items():
            if c_name not in routing:
                nr = self.nearest_region[c_name]
                region_lambda[nr] += lam_c
                continue
            frac_map = routing[c_name]
            for r_name, frac in frac_map.items():
                region_lambda[r_name] += lam_c * frac
        return region_lambda

    def _control_step(self, current_lambda_region, guardrails, prices, carbons):
        k_next, routing = self.controller.control_step(
            regions=self.regions,
            current_lambda=current_lambda_region,
            guardrails=guardrails,
            prices=prices,
            carbons=carbons,
            energy_model=self.energy_model,
            rtt_matrix=self.rtt_matrix,
            nearest_region=self.nearest_region,
            rtt_budget=self.rtt_budget_ms,
        )
        return k_next, routing

    def _compute_step_metrics(self, lambda_region, routing, prices, carbons):
        p99_latencies = []
        p99_ttfts = []
        total_energy_kwh = 0.0
        total_cost = 0.0
        total_carbon = 0.0

        energy_per_region = {}
        cost_per_region = {}
        carbon_per_region = {}
        p99_latency_per_region_ms = {}
        p99_ttft_per_region_ms = {}
        violating_requests = 0.0

        for r in self.regions:
            lam_r = lambda_region[r.name]
            mu = r.mu
            k_serving = max(1, r.available_k)
            k_billed = max(1, r.current_k if self.bill_from_launch else r.available_k)

            p99_lat, p99_ttft = approximate_region_p99_latency_and_ttft(lam_r, mu, k_serving, rtt_ms=r.rtt)

            if np.isinf(p99_lat) or np.isnan(p99_lat):
                p99_lat = 1e5
            if np.isinf(p99_ttft) or np.isnan(p99_ttft):
                p99_ttft = 1e5

            slack = min(
                self.sim_config.ttft_p99_slo_ms / 1000.0 - TTFT_BASE_S - r.rtt / 1000.0,
                self.sim_config.p99_latency_slo_ms / 1000.0 - 1.0 / mu - r.rtt / 1000.0,
            )
            p_viol = ErlangC().prob_wait_exceeds(lam_r, mu, k_serving, slack)
            violating_requests += lam_r * self.sim_config.control_interval_s * p_viol

            p99_latencies.append(p99_lat)
            p99_ttfts.append(p99_ttft)
            p99_latency_per_region_ms[r.name] = p99_lat
            p99_ttft_per_region_ms[r.name] = p99_ttft

            result = self.energy_model.compute(
                region=r,
                lam=lam_r,
                mu=mu,
                k=k_billed,
                price=prices[r.name],
                carbon_intensity=carbons[r.name],
            )

            energy_per_region[r.name] = result["energy_kwh"]
            cost_per_region[r.name] = result["cost"]
            carbon_per_region[r.name] = result["carbon"]

            total_energy_kwh += result["energy_kwh"]
            total_cost += result["cost"]
            total_carbon += result["carbon"]

        p99_latency_ms = max(p99_latencies) if p99_latencies else 0.0
        p99_ttft_ms = max(p99_ttfts) if p99_ttfts else 0.0

        slo_latency = self.sim_config.p99_latency_slo_ms
        slo_ttft = self.sim_config.ttft_p99_slo_ms

        slo_violation = int((p99_latency_ms > slo_latency) or (p99_ttft_ms > slo_ttft))
        if np.isinf(p99_latency_ms) or np.isnan(p99_latency_ms):
            slo_violation = 1

        return {
            "p99_latency_ms": p99_latency_ms,
            "p99_ttft_ms": p99_ttft_ms,
            "slo_violation": slo_violation,
            "total_energy_kwh": total_energy_kwh,
            "total_cost_usd": total_cost,
            "total_carbon_g": total_carbon,
            "energy_per_region": energy_per_region,
            "cost_per_region": cost_per_region,
            "carbon_per_region": carbon_per_region,
            "p99_latency_per_region_ms": p99_latency_per_region_ms,
            "p99_ttft_per_region_ms": p99_ttft_per_region_ms,
            "violating_requests": violating_requests,
        }

    def _record_history(self, metrics, k_next, lambda_region=None, lambda_cluster=None, total_requests=0):
        self.history["p99_latency_ms"].append(metrics["p99_latency_ms"])
        self.history["p99_ttft_ms"].append(metrics["p99_ttft_ms"])
        self.history["slo_violation"].append(metrics["slo_violation"])

        self.history["total_energy_kwh"].append(metrics["total_energy_kwh"])
        self.history["total_cost_usd"].append(metrics["total_cost_usd"])
        self.history["total_carbon_g"].append(metrics["total_carbon_g"])

        self.history["k_per_region"].append(k_next.copy())

        self.history["energy_per_region"].append(metrics["energy_per_region"].copy())
        self.history["cost_per_region"].append(metrics["cost_per_region"].copy())
        self.history["carbon_per_region"].append(metrics["carbon_per_region"].copy())

        self.history["p99_latency_per_region_ms"].append(metrics["p99_latency_per_region_ms"].copy())
        self.history["p99_ttft_per_region_ms"].append(metrics["p99_ttft_per_region_ms"].copy())

        if lambda_region is not None:
            self.history["lambda_per_region"].append(lambda_region.copy())

        if lambda_cluster is not None:
            self.history["lambda_per_cluster"].append(lambda_cluster.copy())
        self.history["total_requests_per_step"].append(total_requests)
        self.history["available_k_per_region"].append({r.name: r.available_k for r in self.regions})
        self.history["violating_requests_per_step"].append(metrics.get("violating_requests", 0.0))


class NoGuardrailWrapper:
    """Guardrail that always returns zero (ablation without the guardrail)."""

    def compute_k_gr(self, lam):
        return 1


class NoHysteresis:
    """Pass-through filter (ablation without hysteresis)."""

    def apply(self, previous_k, proposed_k, max_capacity):
        return proposed_k


PROMPT_LEN_MEAN_LOG = 4.64
PROMPT_LEN_STD_LOG = 0.60
RESPONSE_LEN_MEAN_LOG = 5.40
RESPONSE_LEN_STD_LOG = 0.70
BURST_FACTOR = 0.8
TTFT_BASE_STD_S = 0.2
TOKENS_PER_SEC_EDGE = 50.0
TOKENS_PER_SEC_CLOUD = 70.0


def _base_lambda_per_cluster():
    """Mean arrival rate (req/s) of each user cluster."""
    return {
        "cluster_north": 12.0,
        "cluster_south": 10.0,
        "cluster_central": 15.0,
        "cluster_remote": 8.0,
    }


class WorkloadGenerator:
    """Diurnal, bursty arrival process per user cluster."""

    def __init__(
        self,
        regions: List[Region],
        clusters: List[UserClusterConfig],
        sim_config: SimulationConfig,
        base_lambda_per_cluster: Dict[str, float],
        diurnal_shape_file: str = None,
    ):
        self.regions = regions
        self.clusters = clusters
        self.sim_config = sim_config
        self.base_lambda_per_cluster = base_lambda_per_cluster
        self.diurnal_pattern = self._load_diurnal_pattern(diurnal_shape_file)
        self.token_rates = {}
        for r in regions:
            if "edge" in r.name:
                self.token_rates[r.name] = TOKENS_PER_SEC_EDGE
            else:
                self.token_rates[r.name] = TOKENS_PER_SEC_CLOUD
        self.current_step = 0
        self.current_time_s = 0.0
        self.rtt_matrix, self.nearest_region = build_rtt_matrix(clusters, regions)

    def _load_diurnal_pattern(self, filename: str):

        if filename:
            print(f"Warning: Diurnal pattern file '{filename}' not implemented. Using sine wave.")
            pass
        steps_in_day = int(24 * 60 * 60 / self.sim_config.control_interval_s)
        t = np.linspace(0, 24 * 60 * 60, steps_in_day, endpoint=False)
        phase_shift = -14 * 60 * 60
        pattern = 0.5 * (1 + np.sin((t + phase_shift) * 2 * np.pi / (24 * 60 * 60)))
        return pattern

    def _get_diurnal_factor(self, current_time_s: float) -> float:
        steps_in_day = len(self.diurnal_pattern)
        time_of_day_s = current_time_s % (24 * 60 * 60)
        index = int(time_of_day_s / (24 * 60 * 60) * steps_in_day)
        return self.diurnal_pattern[index]

    def _sample_prompt_length(self) -> int:
        length = np.random.lognormal(PROMPT_LEN_MEAN_LOG, PROMPT_LEN_STD_LOG)
        return max(50, int(length))

    def _sample_response_length(self) -> int:
        length = np.random.lognormal(RESPONSE_LEN_MEAN_LOG, RESPONSE_LEN_STD_LOG)
        return max(150, int(length))

    def _sample_burst_arrival_rate(self, current_lambda_t: float) -> float:
        U = np.random.lognormal(0, 1)
        bursty_rate = current_lambda_t * (1 + BURST_FACTOR * (U - 1))
        return max(0, bursty_rate)

    def sample_arrival_rates(self, step: int = None) -> Dict[str, float]:
        if step is None:
            step = self.current_step
        current_time_s = step * self.sim_config.control_interval_s
        arrival_rates = {}
        for cluster in self.clusters:
            base_lambda = self.base_lambda_per_cluster[cluster.name]
            diurnal_factor = self._get_diurnal_factor(current_time_s)
            lambda_base_t = base_lambda * diurnal_factor
            sampled_lambda = self._sample_burst_arrival_rate(lambda_base_t)
            arrival_rates[cluster.name] = sampled_lambda
        self.current_step += 1
        self.current_time_s += self.sim_config.control_interval_s
        return arrival_rates

    def sample_request_params(self, cluster_name: str) -> Dict:
        prompt_len = self._sample_prompt_length()
        response_len = self._sample_response_length()
        return {
            "prompt_tokens": prompt_len,
            "response_tokens": response_len,
        }


def build_guardrail_calculators(regions, sim_config, lambda_max=500.0, safety_margin=None):
    """One GuardrailCalculator per region with the given safety margin."""
    if safety_margin is None:
        safety_margin = getattr(sim_config, "guardrail_safety_margin", 1.5)
    return {
        r.name: GuardrailCalculator(
            table=None,
            lambda_axis=None,
            max_k=r.max_k,
            slo_latency=sim_config.p99_latency_slo_ms,
            slo_ttft=sim_config.ttft_p99_slo_ms,
            mu=r.mu,
            rtt_ms=r.rtt,
            safety_margin=safety_margin,
        )
        for r in regions
    }


def collect_policy_summary(hist):
    """Aggregate a simulation history into summary metrics."""
    total_steps = len(hist["p99_latency_ms"])
    slo_rate = float(np.sum(hist["slo_violation"]) / total_steps)
    p99_lat = float(np.mean(hist["p99_latency_ms"]))
    p99_ttft = float(np.mean(hist["p99_ttft_ms"]))
    cost = float(np.sum(hist["total_cost_usd"]))
    carbon = float(np.sum(hist["total_carbon_g"]))
    scaling_changes = int(np.sum(hist["scaling_changes"]))
    routing_changes = int(np.sum(hist["routing_changes"]))

    total_requests = float(np.sum(hist["total_requests_per_step"]))

    if hist.get("violating_requests_per_step"):
        violating = float(np.sum(hist["violating_requests_per_step"]))
        successful_requests = max(total_requests - violating, 0.0)
    else:
        violating = total_requests * slo_rate
        successful_requests = total_requests * (1.0 - slo_rate)

    cost_per_success = cost / max(successful_requests, 1e-9)
    carbon_per_success = carbon / max(successful_requests, 1e-9)

    return {
        "SLO_Violation_Rate": slo_rate,
        "Avg_p99_Latency_ms": p99_lat,
        "Avg_p99_TTFT_ms": p99_ttft,
        "Total_Cost_USD": cost,
        "Total_Carbon_g": carbon,
        "Scaling_Changes": scaling_changes,
        "Routing_Changes": routing_changes,
        "Request_Violation_Rate": violating / max(total_requests, 1e-9),
        "Mean_Provisioned_k": float(np.mean([sum(d.values()) for d in hist["k_per_region"]])),
        "Total_Requests": total_requests,
        "Successful_Requests": successful_requests,
        "Cost_per_Success_USD": cost_per_success,
        "Carbon_per_Success_g": carbon_per_success,
    }


DEFAULT_HYSTERESIS = dict(mode="absolute", low_ratio=0.05, high_ratio=0.10, ref_capacity=None)

RULE_BASELINES = [
    "LatencyFirst",
    "CostFirst",
    "CarbonFirst",
    "RoundRobin",
    "QLM_style",
    "SOLA_style",
    "ThresholdBased",
    "CarbonAdvisor_Style",
    "SLA_Guarded",
]
HYSTERESIS_BASELINES = ["LatencyFirst+H", "CostFirst+H", "CarbonFirst+H", "RoundRobin+H", "HPA_Stab"]


ABLATIONS = ["no_guardrail", "no_prediction", "no_hysteresis", "no_margin", "no_prewarm", "with_spreading"]
SLA_VARIANTS = ["SLA_Guarded", "SLA_Guarded_InvWeight"] + ABLATIONS


def make_controller(name, sim_config, hysteresis=None):
    """Build a controller by name. `hysteresis` is a dict for HysteresisFilter
    and is used for SLA-Guarded and for every '+H' baseline, so all
    hysteresis-equipped policies share the same filter."""
    hyst = dict(DEFAULT_HYSTERESIS, **(hysteresis or {}))
    H = lambda: HysteresisFilter(**hyst)
    base = name[:-2] if name.endswith("+H") else name
    if base == "LatencyFirst":
        c = LatencyFirstController()
    elif base == "CostFirst":
        c = CostFirstController(sim_config)
    elif base == "CarbonFirst":
        c = CarbonFirstController(sim_config)
    elif base == "RoundRobin":
        c = RoundRobinController(sim_config)
    elif base == "QLM_style":
        c = SLOAwareCostController(sim_config)
    elif base == "SOLA_style":
        c = SOLAStyleController(sim_config)
    elif base == "ThresholdBased":
        c = ThresholdBasedController(sim_config)
    elif base == "HPA_Stab":
        c = ThresholdBasedController(sim_config, stabilization_steps=10)
    elif base == "CarbonAdvisor_Style":
        c = CarbonAdvisorStyleController(sim_config)
    else:
        if name not in SLA_VARIANTS:
            raise ValueError(f"Unknown policy: {name}")

        mpc_kw = dict(routing_mode="argmin", routing_beta=1.0, prewarm=True)
        hyst_obj = H()
        if name in ("SLA_Guarded_InvWeight", "with_spreading"):

            mpc_kw = dict(routing_mode="inverse", routing_beta=0.15, prewarm=False)
        if name == "no_prewarm":
            mpc_kw["prewarm"] = False
        if name == "no_prediction":
            mpc_kw["use_forecast"] = False
        if name == "no_hysteresis":
            hyst_obj = NoHysteresis()
        mpc = MPCController(sim_config=sim_config, **mpc_kw)
        return SLAController(
            sim_config=sim_config,
            mpc=mpc,
            hysteresis=hyst_obj,
            rtt_budget=sim_config.rtt_budget_ms,
            tradeoff=sim_config.alpha_tradeoff,
        )
    if name.endswith("+H"):
        c.hysteresis = H()
    return c


def run_policy(
    name,
    seed=0,
    trace_seed=None,
    sim_config=None,
    hysteresis=None,
    warmup_steps=2,
    max_k=4096,
    guardrail_margin=1.5,
    return_history=False,
    mpc_overrides=None,
    sim_kwargs=None,
    topology=None,
    profile=False,
):
    """Run one policy for one seed.

    mpc_overrides : dict of MPCController attributes for SLA-Guarded variants,
                    e.g. {"max_utilization": 0.9, "eta": 0.05}.
    sim_kwargs    : extra SLASimulator arguments (warmup_sampler,
                    scaledown_delay_steps, bill_from_launch).
    topology      : (regions, clusters, base_lambda_per_cluster) to replace the
                    default 4-region scenario (scalability experiment).
    profile       : if True, the summary contains per-stage wall-clock times.
    """
    sim_config = sim_config if sim_config is not None else SimulationConfig()
    trace_seed = seed if trace_seed is None else trace_seed
    if topology is None:
        regions, clusters = create_default_topology(max_k=max_k)
        base_lambda = _base_lambda_per_cluster()
    else:
        regions, clusters, base_lambda = topology
    margin = 1.0 if name == "no_margin" else guardrail_margin
    if name == "no_guardrail":
        guards = {r.name: NoGuardrailWrapper() for r in regions}
    else:
        guards = build_guardrail_calculators(regions, sim_config, safety_margin=margin)
    controller = make_controller(name, sim_config, hysteresis)
    mpc = getattr(controller, "mpc", None)
    if mpc is not None and mpc_overrides:
        for k_, v_ in mpc_overrides.items():
            setattr(mpc, k_, v_)
    sim = SLASimulator(
        sim_config=sim_config,
        sla_controller=controller,
        regions=regions,
        clusters=clusters,
        energy_model=EnergyCostCarbonModel(
            interval_seconds=sim_config.control_interval_s, busy_power=180.0, idle_power=120.0
        ),
        base_lambda_per_cluster=base_lambda,
        guardrail_calculator=guards,
        rtt_budget_ms=sim_config.rtt_budget_ms,
        policy_name=name,
        trace_seed=trace_seed,
        warmup_steps=warmup_steps,
        **(sim_kwargs or {}),
    )
    if profile:
        sim.profile = {}
        if mpc is not None:
            mpc.profile = sim.profile
    sim.workload_gen = WorkloadGenerator(
        regions=regions, clusters=clusters, sim_config=sim_config, base_lambda_per_cluster=base_lambda
    )
    t_start = time.perf_counter()
    step_times = []
    np.random.seed(seed)
    sim.current_step, sim.time_s = 0, 0.0
    for _ in range(sim_config.total_steps):
        t0 = time.perf_counter()
        sim._run_single_step()
        step_times.append(time.perf_counter() - t0)
    hist = sim.history
    summary = collect_policy_summary(hist)
    summary.update(Policy=name, Seed=seed, Warmup_Steps=warmup_steps)
    if profile:
        summary["Wall_s"] = time.perf_counter() - t_start
        summary["Mean_Step_ms"] = 1000 * float(np.mean(step_times))
        summary["P99_Step_ms"] = 1000 * float(np.percentile(step_times, 99))
        for k_, v_ in sim.profile.items():
            summary[f"Stage_{k_}_ms_per_step"] = 1000 * v_ / sim_config.total_steps
    return (summary, hist) if return_history else summary
