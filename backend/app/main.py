from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .algorithms import (
    solve_exact,
    solve_gccvc,
    solve_grccvc,
    solve_gwccvc,
    solve_hga,
    verify_solution,
)

SUPPORTED_METHODS = {"gccvc", "grccvc", "gwccvc", "hga", "exact"}
SUPPORTED_OPTIMIZE_GOALS = {"min-feasible-k", "best-weight"}


class VertexIn(BaseModel):
    id: int
    weight: float
    x: float = 0.0
    y: float = 0.0


class SolveRequest(BaseModel):
    vertices: List[VertexIn]
    edges: List[Tuple[int, int]]
    capacityK: Optional[int] = Field(default=None, ge=1)
    optimizeK: bool = False
    optimizeGoal: str = "min-feasible-k"
    optimizeMaxTrials: int = Field(default=18, ge=4, le=100)
    popSize: int = Field(default=40, ge=2, le=300)
    generations: int = Field(default=60, ge=1, le=1000)
    seed: int = 42
    includeExact: bool = True
    methods: Optional[List[str]] = None

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        normalized = [method.lower().strip() for method in value]
        invalid = [method for method in normalized if method not in SUPPORTED_METHODS]
        if invalid:
            raise ValueError(f"Unsupported methods: {', '.join(invalid)}")
        deduped: List[str] = []
        seen = set()
        for method in normalized:
            if method not in seen:
                seen.add(method)
                deduped.append(method)
        return deduped

    @field_validator("optimizeGoal")
    @classmethod
    def validate_optimize_goal(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in SUPPORTED_OPTIMIZE_GOALS:
            raise ValueError(
                f"Unsupported optimizeGoal: {normalized}. "
                f"Use one of {', '.join(sorted(SUPPORTED_OPTIMIZE_GOALS))}."
            )
        return normalized


app = FastAPI(
    title="CCVC Solver API",
    version="1.0.0",
    description="Python backend for Capacitated Connected Vertex Cover algorithms.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_edges(
    vertex_data: List[Dict[str, Any]],
    edge_data: List[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    node_ids = {int(vertex["id"]) for vertex in vertex_data}
    seen = set()
    normalized: List[Tuple[int, int]] = []
    for raw_u, raw_v in edge_data:
        u = int(raw_u)
        v = int(raw_v)
        if u == v or u not in node_ids or v not in node_ids:
            continue
        key = (u, v) if u < v else (v, u)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def compute_capacity_bounds(
    vertex_data: List[Dict[str, Any]],
    normalized_edges: List[Tuple[int, int]],
) -> Dict[str, int]:
    node_ids = [int(vertex["id"]) for vertex in vertex_data]
    n = len(node_ids)
    m = len(normalized_edges)
    if n <= 0:
        return {
            "minK": 1,
            "maxK": 1,
            "maxDegree": 0,
            "ruleMin": 1,
            "ruleMax": 1,
        }

    degree = {node_id: 0 for node_id in node_ids}
    for u, v in normalized_edges:
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
        "maxDegree": max_degree,
        "ruleMin": rule_min,
        "ruleMax": rule_max,
    }


def best_valid_method_for_k(results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    best_method: Optional[str] = None
    best_weight = float("inf")
    for method, result in results.items():
        if result is None:
            continue
        verification = result.get("verification") or {}
        if not verification.get("isValid"):
            continue
        weight = float(verification.get("totalWeight", float("inf")))
        if weight < best_weight:
            best_weight = weight
            best_method = method

    if best_method is None:
        return None

    return {
        "method": best_method,
        "weight": round(float(best_weight), 3),
    }


def pick_scan_points(min_k: int, max_k: int, budget: int) -> List[int]:
    if budget <= 0 or max_k < min_k:
        return []
    total = max_k - min_k + 1
    if total <= budget:
        return list(range(min_k, max_k + 1))
    if budget == 1:
        return [min_k]

    points = set()
    span = max_k - min_k
    for i in range(budget):
        value = min_k + int(round((span * i) / (budget - 1)))
        points.add(value)

    ordered = sorted(points)
    if ordered[0] != min_k:
        ordered.insert(0, min_k)
    if ordered[-1] != max_k:
        ordered.append(max_k)
    return ordered


def adaptive_hga_budget(
    vertex_count: int,
    pop_size: int,
    generations: int,
) -> Tuple[int, int]:
    pop = int(pop_size)
    gens = int(generations)

    if vertex_count >= 120:
        pop = min(pop, 14)
        gens = min(gens, 18)
    elif vertex_count >= 90:
        pop = min(pop, 16)
        gens = min(gens, 20)
    elif vertex_count >= 60:
        pop = min(pop, 22)
        gens = min(gens, 28)
    elif vertex_count >= 40:
        pop = min(pop, 30)
        gens = min(gens, 40)

    return max(8, pop), max(10, gens)


def adaptive_trial_hga_budget(
    vertex_count: int,
    pop_size: int,
    generations: int,
) -> Tuple[int, int]:
    pop = min(int(pop_size), 14)
    gens = min(int(generations), 20)

    if vertex_count >= 160:
        pop = min(pop, 5)
        gens = min(gens, 6)
    elif vertex_count >= 120:
        pop = min(pop, 6)
        gens = min(gens, 8)
    elif vertex_count >= 90:
        pop = min(pop, 7)
        gens = min(gens, 9)
    elif vertex_count >= 60:
        pop = min(pop, 8)
        gens = min(gens, 11)
    elif vertex_count >= 40:
        pop = min(pop, 10)
        gens = min(gens, 14)

    return max(2, pop), max(1, gens)


def run_methods_for_k(
    *,
    vertex_data: List[Dict[str, Any]],
    normalized_edges: List[Tuple[int, int]],
    methods_to_run: List[str],
    capacity_k: int,
    pop_size: int,
    generations: int,
    seed: int,
    hga_budget_override: Optional[Tuple[int, int]] = None,
) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    n_vertices = len(vertex_data)
    for method in methods_to_run:
        result: Optional[Dict[str, Any]]
        if method == "gccvc":
            result = solve_gccvc(vertex_data, normalized_edges, capacity_k, seed)
        elif method == "grccvc":
            result = solve_grccvc(vertex_data, normalized_edges, capacity_k, seed)
        elif method == "gwccvc":
            result = solve_gwccvc(vertex_data, normalized_edges, capacity_k, seed)
        elif method == "hga":
            if hga_budget_override is None:
                effective_pop, effective_gens = adaptive_hga_budget(
                    n_vertices,
                    pop_size,
                    generations,
                )
            else:
                effective_pop = max(2, int(hga_budget_override[0]))
                effective_gens = max(1, int(hga_budget_override[1]))
            result = solve_hga(
                vertex_data,
                normalized_edges,
                capacity_k,
                effective_pop,
                effective_gens,
                seed,
            )
            result["effectivePopSize"] = effective_pop
            result["effectiveGenerations"] = effective_gens
        elif method == "exact":
            result = solve_exact(vertex_data, normalized_edges, capacity_k, max_n=18)
            if result is None:
                results["exact"] = None
                continue
        else:
            continue

        cover_list = sorted(int(node_id) for node_id in result["cover"])
        verification = verify_solution(
            vertex_data,
            normalized_edges,
            cover_list,
            capacity_k,
        )

        serialized_result: Dict[str, Any] = {
            "cover": cover_list,
            "verification": verification,
        }
        for key, value in result.items():
            if key == "cover":
                continue
            if key == "time_ms":
                serialized_result["time"] = round(float(value), 3)
            else:
                serialized_result[key] = value

        results[method] = serialized_result
    return results


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "CCVC backend is running"}


@app.post("/api/solve")
def solve(payload: SolveRequest) -> Dict[str, Any]:
    if not payload.vertices:
        raise HTTPException(status_code=400, detail="Graph must include at least one vertex.")
    if not payload.edges:
        raise HTTPException(status_code=400, detail="Graph must include at least one edge.")

    vertex_data = [vertex.model_dump() for vertex in payload.vertices]
    normalized_edges = normalize_edges(
        vertex_data,
        [(int(u), int(v)) for u, v in payload.edges],
    )
    if not normalized_edges:
        raise HTTPException(status_code=400, detail="Graph must include at least one valid edge.")

    if payload.methods is not None:
        methods_to_run = list(payload.methods)
    else:
        methods_to_run = ["gccvc", "grccvc", "gwccvc", "hga"]
        if payload.includeExact:
            methods_to_run.append("exact")

    if not payload.optimizeK and payload.capacityK is None:
        raise HTTPException(
            status_code=400,
            detail="capacityK is required when optimizeK is false.",
        )

    k_bounds = compute_capacity_bounds(vertex_data, normalized_edges)

    trial_by_k: Dict[int, Dict[str, Any]] = {}
    trial_results_by_k: Dict[int, Dict[str, Any]] = {}
    full_results_by_k: Dict[int, Dict[str, Any]] = {}

    trial_methods = [method for method in methods_to_run if method in {"gccvc", "grccvc", "gwccvc"}]
    if not trial_methods and methods_to_run:
        trial_methods = [methods_to_run[0]]

    trial_pop = min(payload.popSize, 22)
    trial_generations = min(payload.generations, 28)
    if "hga" in methods_to_run and "hga" not in trial_methods:
        trial_methods.append("hga")
    trial_hga_budget = adaptive_trial_hga_budget(
        len(vertex_data),
        trial_pop,
        trial_generations,
    )

    def evaluate_trial_k(k_value: int) -> Dict[str, Any]:
        k = max(1, int(k_value))
        if k in trial_results_by_k:
            return trial_results_by_k[k]

        run_results = run_methods_for_k(
            vertex_data=vertex_data,
            normalized_edges=normalized_edges,
            methods_to_run=trial_methods,
            capacity_k=k,
            pop_size=trial_pop,
            generations=trial_generations,
            seed=payload.seed,
            hga_budget_override=trial_hga_budget if "hga" in trial_methods else None,
        )
        trial_results_by_k[k] = run_results

        best_valid = best_valid_method_for_k(run_results)
        trial_by_k[k] = {
            "k": k,
            "feasible": bool(best_valid),
            "bestMethod": best_valid["method"] if best_valid else None,
            "bestWeight": best_valid["weight"] if best_valid else None,
        }
        return run_results

    def evaluate_full_k(k_value: int) -> Dict[str, Any]:
        k = max(1, int(k_value))
        if k in full_results_by_k:
            return full_results_by_k[k]

        run_results = run_methods_for_k(
            vertex_data=vertex_data,
            normalized_edges=normalized_edges,
            methods_to_run=methods_to_run,
            capacity_k=k,
            pop_size=payload.popSize,
            generations=payload.generations,
            seed=payload.seed,
        )
        full_results_by_k[k] = run_results
        return run_results

    selected_k = int(payload.capacityK or 1)
    selected_by = "manual"
    min_feasible_k: Optional[int] = None

    if payload.optimizeK:
        lo = int(k_bounds["minK"])
        hi = int(k_bounds["maxK"])

        while lo <= hi:
            mid = (lo + hi) // 2
            evaluate_trial_k(mid)
            if trial_by_k[mid]["feasible"]:
                min_feasible_k = mid
                hi = mid - 1
            else:
                lo = mid + 1

        if min_feasible_k is None:
            selected_k = int(k_bounds["maxK"])
            selected_by = "fallback-max-k"
            evaluate_trial_k(selected_k)
        elif payload.optimizeGoal == "best-weight":
            remaining_budget = max(0, int(payload.optimizeMaxTrials) - len(trial_by_k))
            scan_candidates = pick_scan_points(min_feasible_k, int(k_bounds["maxK"]), remaining_budget)
            for k in scan_candidates:
                evaluate_trial_k(k)

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

        final_results = evaluate_full_k(selected_k)
    else:
        selected_k = int(payload.capacityK or 1)
        final_results = evaluate_full_k(selected_k)

    optimization_meta: Dict[str, Any] = {
        "enabled": bool(payload.optimizeK),
    }
    if payload.optimizeK:
        trial_list = [trial_by_k[k] for k in sorted(trial_by_k)]
        feasible_trials = [trial for trial in trial_list if trial["feasible"]]
        best_trial = (
            min(feasible_trials, key=lambda trial: (float(trial["bestWeight"]), int(trial["k"])))
            if feasible_trials
            else None
        )
        optimization_meta.update(
            {
                "goal": payload.optimizeGoal,
                "selectedBy": selected_by,
                "selectedK": selected_k,
                "minFeasibleK": min_feasible_k,
                "bestTrialK": int(best_trial["k"]) if best_trial else None,
                "trialCount": len(trial_list),
                "trialMethods": trial_methods,
                "trialBudget": int(payload.optimizeMaxTrials),
                "trialHgaBudget": {
                    "popSize": int(trial_hga_budget[0]),
                    "generations": int(trial_hga_budget[1]),
                }
                if "hga" in trial_methods
                else None,
                "trials": trial_list,
            }
        )

    return {
        "results": final_results,
        "meta": {
            "vertexCount": len(vertex_data),
            "edgeCount": len(normalized_edges),
            "capacityK": selected_k,
            "requestedCapacityK": payload.capacityK,
            "methodsRun": methods_to_run,
            "kBounds": k_bounds,
            "optimization": optimization_meta,
        },
    }
