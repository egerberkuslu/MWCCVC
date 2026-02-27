from __future__ import annotations

import math
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from ..algorithms import (
    solve_exact,
    solve_exact_time_limited,
    solve_gccvc,
    solve_grccvc,
    solve_gwccvc,
    solve_hga,
    solve_hga_v2,
    verify_solution,
)
from .datareader import list_dataset_files, parse_scale_from_filename, read_graph_from_file

SUPPORTED_METHODS = {
    "gccvc",
    "grccvc",
    "gwccvc",
    "hga",
    "hga_v2",
    "weighted-and-cover-oriented-hga",
    "exact",
}
DISABLED_METHODS = {"weighted-and-cover-oriented-hga"}
SCALE_KEYS = ("small", "medium", "large")
SUPPORTED_OPTIMIZE_GOALS = {"min-feasible-k", "best-weight"}


def _compute_capacity_bounds(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
) -> Dict[str, int]:
    n = len(vertex_data)
    m = len(edge_data)
    if n <= 0:
        return {"minK": 1, "maxK": 1, "ruleMin": 1, "ruleMax": 1, "maxDegree": 0}

    degree = {int(vertex["id"]): 0 for vertex in vertex_data}
    for u, v in edge_data:
        if u in degree:
            degree[u] += 1
        if v in degree:
            degree[v] += 1

    max_degree = max(degree.values()) if degree else 0
    rule_min = max(1, math.ceil(m / max(1, n)))
    rule_max = max(1, max_degree)
    return {
        "minK": max(1, min(rule_min, rule_max)),
        "maxK": max(rule_min, rule_max),
        "ruleMin": rule_min,
        "ruleMax": rule_max,
        "maxDegree": max_degree,
    }


def _compute_graph_stats(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
) -> Dict[str, Any]:
    node_ids = [int(vertex["id"]) for vertex in vertex_data]
    n = len(node_ids)
    m = len(edge_data)
    weights = [float(vertex["weight"]) for vertex in vertex_data]

    adjacency: Dict[int, Set[int]] = {node_id: set() for node_id in node_ids}
    for u, v in edge_data:
        adjacency.setdefault(u, set()).add(v)
        adjacency.setdefault(v, set()).add(u)

    visited: Set[int] = set()
    component_sizes: List[int] = []
    for node_id in node_ids:
        if node_id in visited:
            continue
        stack = [node_id]
        visited.add(node_id)
        size = 0
        while stack:
            cur = stack.pop()
            size += 1
            for neighbor in adjacency.get(cur, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        component_sizes.append(size)

    largest_component = max(component_sizes) if component_sizes else 0
    density = (2 * m) / (n * (n - 1)) if n > 1 else 0.0
    avg_degree = (2 * m) / n if n > 0 else 0.0
    return {
        "n": n,
        "m": m,
        "density": round(float(density), 6),
        "avgDegree": round(float(avg_degree), 6),
        "components": len(component_sizes),
        "largestComponentSize": largest_component,
        "largestComponentRatio": round(float(largest_component / n), 6) if n else 0.0,
        "avgWeight": round(float(mean(weights)), 6) if weights else 0.0,
        "minWeight": round(float(min(weights)), 6) if weights else 0.0,
        "maxWeight": round(float(max(weights)), 6) if weights else 0.0,
    }


def _adaptive_hga_budget(vertex_count: int, pop_size: int, generations: int) -> Tuple[int, int]:
    pop = int(pop_size)
    gens = int(generations)

    if vertex_count >= 200:
        pop = min(pop, 10)
        gens = min(gens, 16)
    elif vertex_count >= 120:
        pop = min(pop, 14)
        gens = min(gens, 22)
    elif vertex_count >= 80:
        pop = min(pop, 18)
        gens = min(gens, 28)
    elif vertex_count >= 50:
        pop = min(pop, 24)
        gens = min(gens, 36)

    return max(8, pop), max(8, gens)


def _adaptive_trial_hga_budget(vertex_count: int, pop_size: int, generations: int) -> Tuple[int, int]:
    pop = min(int(pop_size), 14)
    gens = min(int(generations), 20)

    if vertex_count >= 180:
        pop = min(pop, 5)
        gens = min(gens, 6)
    elif vertex_count >= 120:
        pop = min(pop, 6)
        gens = min(gens, 8)
    elif vertex_count >= 80:
        pop = min(pop, 7)
        gens = min(gens, 10)
    elif vertex_count >= 50:
        pop = min(pop, 9)
        gens = min(gens, 12)

    return max(2, pop), max(1, gens)


def _best_valid_method_for_results(results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    best_method: Optional[str] = None
    best_weight = float("inf")
    for method, result in results.items():
        if not result:
            continue
        verification = result.get("verification") or {}
        if not bool(verification.get("isValid")):
            continue
        total_weight = float(verification.get("totalWeight", float("inf")))
        if total_weight < best_weight:
            best_weight = total_weight
            best_method = method

    if best_method is None:
        return None
    return {"method": best_method, "weight": float(best_weight)}


def _pick_scan_points(min_k: int, max_k: int, budget: int) -> List[int]:
    if budget <= 0 or max_k < min_k:
        return []
    total = max_k - min_k + 1
    if total <= budget:
        return list(range(min_k, max_k + 1))
    if budget == 1:
        return [min_k]

    points = set()
    span = max_k - min_k
    for index in range(budget):
        value = min_k + int(round((span * index) / (budget - 1)))
        points.add(value)

    ordered = sorted(points)
    if ordered and ordered[0] != min_k:
        ordered.insert(0, min_k)
    if ordered and ordered[-1] != max_k:
        ordered.append(max_k)
    return ordered


def _as_int_set(values: Optional[Sequence[int]]) -> Set[int]:
    if not values:
        return set()
    parsed: Set[int] = set()
    for value in values:
        ivalue = int(value)
        if ivalue > 0:
            parsed.add(ivalue)
    return parsed


def _normalize_capacity_by_scale(raw: Optional[Dict[str, Any]]) -> Dict[str, int]:
    default_values = {"small": 18, "medium": 16, "large": 16}
    if not raw:
        return default_values

    normalized = dict(default_values)
    for key, value in raw.items():
        name = str(key).strip().lower()
        if name not in SCALE_KEYS:
            continue
        ivalue = int(value)
        if ivalue >= 1:
            normalized[name] = ivalue
    return normalized


def _ratio_from_scale(scale: Dict[str, Any]) -> Optional[float]:
    n = scale.get("n")
    m = scale.get("m")
    if n is None or m is None:
        return None
    n_value = int(n)
    if n_value <= 0:
        return None
    return float(m) / float(n_value)


def _run_method(
    *,
    method: str,
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    pop_size: int,
    generations: int,
    seed: int,
    exact_time_limit_ms: Optional[float] = None,
    exact_max_n: Optional[int] = 18,
) -> Optional[Dict[str, Any]]:
    if method == "gccvc":
        result = solve_gccvc(vertex_data, edge_data, capacity_k, seed)
    elif method == "grccvc":
        result = solve_grccvc(vertex_data, edge_data, capacity_k, seed)
    elif method == "gwccvc":
        result = solve_gwccvc(vertex_data, edge_data, capacity_k, seed)
    elif method in {"hga", "hga_v2"}:
        effective_pop, effective_gens = _adaptive_hga_budget(len(vertex_data), pop_size, generations)
        if method == "hga_v2":
            result = solve_hga_v2(vertex_data, edge_data, capacity_k, effective_pop, effective_gens, seed)
        else:
            result = solve_hga(vertex_data, edge_data, capacity_k, effective_pop, effective_gens, seed)
        result["effectivePopSize"] = effective_pop
        result["effectiveGenerations"] = effective_gens
    elif method == "exact":
        if exact_time_limit_ms is not None:
            result = solve_exact_time_limited(
                vertex_data,
                edge_data,
                capacity_k,
                time_limit_ms=float(exact_time_limit_ms),
                max_n=exact_max_n,
            )
        else:
            if exact_max_n is None:
                result = solve_exact(vertex_data, edge_data, capacity_k, max_n=None)
            else:
                result = solve_exact(vertex_data, edge_data, capacity_k, max_n=int(exact_max_n))
    else:
        return None

    if result is None:
        return None

    cover = sorted(int(node_id) for node_id in result.get("cover", []))
    verification = verify_solution(vertex_data, edge_data, cover, capacity_k)
    payload: Dict[str, Any] = {
        "cover": cover,
        "verification": verification,
    }
    for key, value in result.items():
        if key == "cover":
            continue
        if key == "time_ms":
            payload["time"] = round(float(value), 3)
        else:
            payload[key] = value
    return payload


def _method_summary(graph_rows: Sequence[Dict[str, Any]], methods: Sequence[str]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for method in methods:
        attempted = 0
        valid_runs = 0
        times: List[float] = []
        weights: List[float] = []
        cover_sizes: List[float] = []

        for row in graph_rows:
            result = (row.get("results") or {}).get(method)
            if method in (row.get("results") or {}):
                attempted += 1
            if not result:
                continue

            result_time = float(result.get("time", float("nan")))
            if math.isfinite(result_time):
                times.append(result_time)

            verification = result.get("verification") or {}
            if bool(verification.get("isValid")):
                valid_runs += 1
                weight = float(verification.get("totalWeight", float("nan")))
                cover_size = float(verification.get("coverSize", float("nan")))
                if math.isfinite(weight):
                    weights.append(weight)
                if math.isfinite(cover_size):
                    cover_sizes.append(cover_size)

        summary[method] = {
            "attempted": attempted,
            "validRuns": valid_runs,
            "validRate": round(float(valid_runs / attempted), 6) if attempted else 0.0,
            "avgTimeMs": round(float(mean(times)), 6) if times else None,
            "avgWeight": round(float(mean(weights)), 6) if weights else None,
            "avgCoverSize": round(float(mean(cover_sizes)), 6) if cover_sizes else None,
        }
    return summary


class GraphAnalyzer:
    def __init__(
        self,
        *,
        methods: Sequence[str],
        include_exact: bool,
        pop_size: int,
        generations: int,
        seed: int,
        fixed_capacity_k: Optional[int] = None,
        optimize_k: bool = False,
        optimize_goal: str = "best-weight",
        optimize_max_trials: int = 18,
        ratios: Optional[Sequence[float]] = None,
        small_scales: Optional[Sequence[int]] = None,
        medium_scales: Optional[Sequence[int]] = None,
        large_scales: Optional[Sequence[int]] = None,
        capacity_by_scale: Optional[Dict[str, Any]] = None,
        exact_timebox_scales: Optional[Sequence[str]] = None,
        exact_timebox_multiplier: float = 2.0,
        exact_timebox_min_ms: float = 1.0,
        exact_forced_scales: Optional[Sequence[str]] = None,
        exact_unbounded_scales: Optional[Sequence[str]] = None,
    ) -> None:
        normalized = []
        seen = set()
        for raw in methods:
            method = str(raw).strip().lower()
            if method not in SUPPORTED_METHODS or method in seen or method in DISABLED_METHODS:
                continue
            seen.add(method)
            normalized.append(method)

        self.exact_requested = bool(include_exact) or ("exact" in seen)
        if include_exact and "exact" not in seen:
            normalized.append("exact")
        self.exact_timebox_scales = {
            str(value).strip().lower()
            for value in (exact_timebox_scales or [])
            if str(value).strip().lower() in SCALE_KEYS
        }
        self.exact_forced_scales = {
            str(value).strip().lower()
            for value in (exact_forced_scales or [])
            if str(value).strip().lower() in SCALE_KEYS
        }
        self.exact_unbounded_scales = {
            str(value).strip().lower()
            for value in (exact_unbounded_scales or [])
            if str(value).strip().lower() in SCALE_KEYS
        }
        self.exact_timebox_multiplier = max(1.0, float(exact_timebox_multiplier))
        self.exact_timebox_min_ms = max(1.0, float(exact_timebox_min_ms))
        if (self.exact_timebox_scales or self.exact_forced_scales) and "exact" not in normalized:
            normalized.append("exact")
        self.methods = normalized or [
            "gccvc",
            "grccvc",
            "gwccvc",
            "hga",
            "hga_v2",
        ]
        self.pop_size = int(pop_size)
        self.generations = int(generations)
        self.seed = int(seed)
        self.fixed_capacity_k = int(fixed_capacity_k) if fixed_capacity_k else None
        self.optimize_k = bool(optimize_k) and self.fixed_capacity_k is None
        normalized_goal = str(optimize_goal or "best-weight").strip().lower()
        self.optimize_goal = (
            normalized_goal if normalized_goal in SUPPORTED_OPTIMIZE_GOALS else "best-weight"
        )
        self.optimize_max_trials = max(4, min(int(optimize_max_trials), 100))
        self.ratios = sorted({float(value) for value in (ratios or []) if float(value) > 0.0})
        self.small_scales = _as_int_set(small_scales)
        self.medium_scales = _as_int_set(medium_scales)
        self.large_scales = _as_int_set(large_scales)
        self.capacity_by_scale = _normalize_capacity_by_scale(capacity_by_scale)

    def _scale_bucket_for_node_count(self, node_count: int) -> Optional[str]:
        if node_count in self.small_scales:
            return "small"
        if node_count in self.medium_scales:
            return "medium"
        if node_count in self.large_scales:
            return "large"
        return None

    def _capacity_for_graph(
        self,
        *,
        node_count: int,
        bounds: Dict[str, int],
    ) -> Tuple[int, str]:
        if self.fixed_capacity_k is not None:
            return int(self.fixed_capacity_k), "fixed"

        scale_bucket = self._scale_bucket_for_node_count(node_count)
        if scale_bucket is not None:
            configured = int(self.capacity_by_scale.get(scale_bucket, 0))
            if configured >= 1:
                return configured, f"capacity_by_scale:{scale_bucket}"

        return int(bounds["minK"]), "k_bounds_min"

    def _run_methods_for_k(
        self,
        *,
        methods: Sequence[str],
        vertex_data: Sequence[Dict[str, Any]],
        edge_data: Sequence[Tuple[int, int]],
        capacity_k: int,
        pop_size: int,
        generations: int,
        seed: int,
        scale_bucket: Optional[str] = None,
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        method_order: List[str] = []
        seen = set()
        for raw in methods:
            method = str(raw).strip().lower()
            if method in seen:
                continue
            seen.add(method)
            method_order.append(method)

        exact_timebox_enabled = (
            scale_bucket is not None
            and scale_bucket in self.exact_timebox_scales
        )
        exact_forced_enabled = (
            scale_bucket is not None
            and scale_bucket in self.exact_forced_scales
        )
        if (exact_timebox_enabled or exact_forced_enabled) and "exact" not in seen:
            method_order.append("exact")

        for method in method_order:
            if method == "exact":
                continue
            results[method] = _run_method(
                method=method,
                vertex_data=vertex_data,
                edge_data=edge_data,
                capacity_k=capacity_k,
                pop_size=pop_size,
                generations=generations,
                seed=seed,
            )

        run_exact = "exact" in method_order and (
            exact_timebox_enabled or exact_forced_enabled or self.exact_requested
        )
        if run_exact:
            exact_budget_ms: Optional[float] = None
            exact_max_n: Optional[int] = 18
            if exact_timebox_enabled:
                longest_time_ms = 0.0
                for method in method_order:
                    if method == "exact":
                        continue
                    method_result = results.get(method)
                    if not method_result:
                        continue
                    method_time = float(method_result.get("time", float("nan")))
                    if math.isfinite(method_time):
                        longest_time_ms = max(longest_time_ms, method_time)
                exact_budget_ms = max(
                    float(self.exact_timebox_min_ms),
                    float(self.exact_timebox_multiplier) * float(longest_time_ms),
                )
                exact_max_n = None
            elif (
                scale_bucket is not None
                and scale_bucket in self.exact_unbounded_scales
            ):
                exact_max_n = None

            exact_result = _run_method(
                method="exact",
                vertex_data=vertex_data,
                edge_data=edge_data,
                capacity_k=capacity_k,
                pop_size=pop_size,
                generations=generations,
                seed=seed,
                exact_time_limit_ms=exact_budget_ms,
                exact_max_n=exact_max_n,
            )
            if exact_result is not None and exact_budget_ms is not None:
                exact_result["timeBudgetMs"] = round(float(exact_budget_ms), 3)
                exact_result["timeBudgetMultiplier"] = float(self.exact_timebox_multiplier)
                exact_result["timeBudgetSource"] = "2x-longest-non-exact"
                verification = exact_result.get("verification") or {}
                if not bool(verification.get("isValid")):
                    exact_result["status"] = "solution is not valid"
            results["exact"] = exact_result
        return results

    def _optimize_capacity_for_graph(
        self,
        *,
        vertex_data: Sequence[Dict[str, Any]],
        edge_data: Sequence[Tuple[int, int]],
        bounds: Dict[str, int],
    ) -> Tuple[int, str, Dict[str, Any]]:
        trial_results_by_k: Dict[int, Dict[str, Any]] = {}
        trial_by_k: Dict[int, Dict[str, Any]] = {}

        # Anchor k-optimization to GRCCVC for stable baseline comparison.
        trial_methods = ["grccvc"]
        trial_selector_method = "grccvc"

        trial_pop = min(self.pop_size, 22)
        trial_generations = min(self.generations, 28)
        trial_hga_budget = _adaptive_trial_hga_budget(
            len(vertex_data),
            trial_pop,
            trial_generations,
        )

        def _evaluate_trial_k(k_value: int) -> None:
            k = max(1, int(k_value))
            if k in trial_results_by_k:
                return

            run_results = self._run_methods_for_k(
                methods=trial_methods,
                vertex_data=vertex_data,
                edge_data=edge_data,
                capacity_k=k,
                pop_size=trial_pop,
                generations=trial_generations,
                seed=self.seed,
            )
            trial_results_by_k[k] = run_results
            selector_result = run_results.get(trial_selector_method) or {}
            verification = selector_result.get("verification") or {}
            is_valid = bool(verification.get("isValid"))
            selector_weight = (
                round(float(verification.get("totalWeight", float("inf"))), 6)
                if is_valid
                else None
            )
            trial_by_k[k] = {
                "k": k,
                "feasible": is_valid,
                "bestMethod": trial_selector_method if is_valid else None,
                "bestWeight": selector_weight,
            }

        min_k = int(bounds["minK"])
        max_k = int(bounds["maxK"])
        lo = min_k
        hi = max_k
        min_feasible_k: Optional[int] = None
        while lo <= hi:
            mid = (lo + hi) // 2
            _evaluate_trial_k(mid)
            if trial_by_k[mid]["feasible"]:
                min_feasible_k = mid
                hi = mid - 1
            else:
                lo = mid + 1

        if min_feasible_k is None:
            selected_k = int(max_k)
            selected_by = "fallback-max-k"
            _evaluate_trial_k(selected_k)
        elif self.optimize_goal == "best-weight":
            remaining_budget = max(0, int(self.optimize_max_trials) - len(trial_by_k))
            scan_candidates = _pick_scan_points(min_feasible_k, max_k, remaining_budget)
            for k_value in scan_candidates:
                _evaluate_trial_k(k_value)

            best_choice: Optional[Dict[str, Any]] = None
            for trial in trial_by_k.values():
                if not trial["feasible"]:
                    continue
                k = int(trial["k"])
                if k < min_feasible_k:
                    continue
                weight = float(trial["bestWeight"])
                if (
                    best_choice is None
                    or weight < best_choice["bestWeight"]
                    or (weight == best_choice["bestWeight"] and k < best_choice["k"])
                ):
                    best_choice = {"k": k, "bestWeight": weight}

            selected_k = int(best_choice["k"] if best_choice else min_feasible_k)
            selected_by = "binary-search-then-sampled-weight-scan"
        else:
            selected_k = int(min_feasible_k)
            selected_by = "binary-search-min-feasible"

        trial_list = [trial_by_k[k] for k in sorted(trial_by_k)]
        optimization_meta = {
            "enabled": True,
            "goal": self.optimize_goal,
            "selectedBy": selected_by,
            "selectedK": selected_k,
            "minFeasibleK": min_feasible_k,
            "trialCount": len(trial_list),
            "trialMethods": trial_methods,
            "trialSelector": trial_selector_method,
            "trialBudget": int(self.optimize_max_trials),
            "trialHgaBudget": {
                "popSize": int(trial_hga_budget[0]),
                "generations": int(trial_hga_budget[1]),
            }
            if any(
                method in trial_methods
                for method in {"hga", "hga_v2"}
            )
            else None,
            "trials": trial_list,
        }
        return selected_k, f"optimized:{self.optimize_goal}", optimization_meta

    def _analyze_single_graph(self, graph_payload: Dict[str, Any]) -> Dict[str, Any]:
        vertex_data = graph_payload["vertices"]
        edge_data = [tuple(edge) for edge in graph_payload["edges"]]
        stats = _compute_graph_stats(vertex_data, edge_data)
        bounds = _compute_capacity_bounds(vertex_data, edge_data)
        scale = parse_scale_from_filename(graph_payload["name"])
        scale_ratio = _ratio_from_scale(scale)
        node_count = int(scale.get("n") or stats.get("n") or 0)
        scale_bucket = self._scale_bucket_for_node_count(node_count)
        if self.optimize_k:
            capacity_k, capacity_source, optimization_meta = self._optimize_capacity_for_graph(
                vertex_data=vertex_data,
                edge_data=edge_data,
                bounds=bounds,
            )
        else:
            capacity_k, capacity_source = self._capacity_for_graph(
                node_count=node_count,
                bounds=bounds,
            )
            optimization_meta = {"enabled": False}

        results = self._run_methods_for_k(
            methods=self.methods,
            vertex_data=vertex_data,
            edge_data=edge_data,
            capacity_k=capacity_k,
            pop_size=self.pop_size,
            generations=self.generations,
            seed=self.seed,
            scale_bucket=scale_bucket,
        )

        best_valid_method: Optional[str] = None
        best_valid_weight = float("inf")
        for method, result in results.items():
            if not result:
                continue
            verification = result.get("verification") or {}
            if not bool(verification.get("isValid")):
                continue
            total_weight = float(verification.get("totalWeight", float("inf")))
            if total_weight < best_valid_weight:
                best_valid_weight = total_weight
                best_valid_method = method

        return {
            "file": graph_payload["name"],
            "scale": scale,
            "ratio": round(float(scale_ratio), 6) if scale_ratio is not None else None,
            "scaleBucket": scale_bucket,
            "declaredNodeCount": graph_payload["declaredNodeCount"],
            "declaredEdgeCount": graph_payload["declaredEdgeCount"],
            "stats": stats,
            "capacityK": capacity_k,
            "capacitySource": capacity_source,
            "kOptimization": optimization_meta,
            "kBounds": bounds,
            "bestValidMethod": best_valid_method,
            "bestValidWeight": round(float(best_valid_weight), 6) if best_valid_method else None,
            "results": results,
        }

    def analyze_dataset(
        self,
        *,
        dataset_dir: Path,
        files: Optional[Sequence[str]] = None,
        filename_contains: Optional[str] = None,
        max_files: int = 30,
    ) -> Dict[str, Any]:
        candidate_files = list_dataset_files(
            dataset_dir,
            files=files,
            filename_contains=filename_contains,
            max_files=max_files,
        )
        discovered_ratios = sorted(
            {
                round(float(ratio), 6)
                for ratio in (
                    _ratio_from_scale(parse_scale_from_filename(path.name))
                    for path in candidate_files
                )
                if ratio is not None
            }
        )

        if self.ratios:
            target_ratios = {round(float(value), 6) for value in self.ratios}
            dataset_files = []
            for path in candidate_files:
                ratio = _ratio_from_scale(parse_scale_from_filename(path.name))
                if ratio is None:
                    continue
                if round(float(ratio), 6) in target_ratios:
                    dataset_files.append(path)
        else:
            dataset_files = list(candidate_files)

        graph_rows: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        for path in dataset_files:
            try:
                graph_payload = read_graph_from_file(path)
                graph_rows.append(self._analyze_single_graph(graph_payload))
            except Exception as exc:
                errors.append({"file": path.name, "error": str(exc)})

        method_summary = _method_summary(graph_rows, self.methods)
        ratio_counts: Dict[str, int] = {}
        for row in graph_rows:
            ratio = row.get("ratio")
            if ratio is None:
                continue
            key = f"{float(ratio):.6f}".rstrip("0").rstrip(".")
            ratio_counts[key] = ratio_counts.get(key, 0) + 1

        return {
            "datasetDir": str(dataset_dir),
            "requestedFiles": [str(item) for item in files] if files else None,
            "filters": {
                "filenameContains": filename_contains,
                "maxFiles": max_files,
                "ratios": list(self.ratios),
                "optimizeK": bool(self.optimize_k),
                "optimizeGoal": self.optimize_goal if self.optimize_k else None,
                "optimizeMaxTrials": int(self.optimize_max_trials) if self.optimize_k else None,
            },
            "discoveredRatios": discovered_ratios,
            "ratioCounts": ratio_counts,
            "capacityByScale": dict(self.capacity_by_scale),
            "scaleConfig": {
                "small": sorted(self.small_scales),
                "medium": sorted(self.medium_scales),
                "large": sorted(self.large_scales),
            },
            "methods": list(self.methods),
            "graphCount": len(graph_rows),
            "errorCount": len(errors),
            "graphs": graph_rows,
            "errors": errors,
            "summary": {
                "graphCount": len(graph_rows),
                "methodSummary": method_summary,
            },
        }
