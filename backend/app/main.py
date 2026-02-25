from __future__ import annotations

import json
import math
import random
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .analysis_tools.ConnectivityRatioVisualizer import ConnectivityRatioVisualizer
from .analysis_tools.GraphAnalyzer import GraphAnalyzer
from .analysis_tools.PresetScaleTestAnalyzer import PresetScaleTestAnalyzer
from .analysis_tools.ScaleAnalyzer import ScaleAnalyzer
from .analysis_tools.ScaleVisualizer import ScaleVisualizer
from .analysis_tools.datareader import list_dataset_files, parse_scale_from_filename
from .algorithms import (
    solve_exact,
    solve_gccvc,
    solve_grccvc,
    solve_gwccvc,
    solve_hga,
    solve_hga_v2,
    solve_weighted_and_cover_oriented_hga,
    verify_solution,
)

SUPPORTED_METHODS = {
    "gccvc",
    "grccvc",
    "gwccvc",
    "hga",
    "hga_v2",
    "weighted-and-cover-oriented-hga",
    "exact",
}
SUPPORTED_OPTIMIZE_GOALS = {"min-feasible-k", "best-weight"}
DEFAULT_DAGDEVIREN_DATASET_DIR = Path(__file__).resolve().parents[1] / "data" / "DagdevirenDataset"
DAGDEVIREN_DEFAULT_RATIOS = [2.0, 4.0, 6.0, 8.0]
DAGDEVIREN_SCALE_ORDER = ["small", "medium", "large"]
DAGDEVIREN_DEFAULT_SMALL_SCALES = [10, 15, 20, 25]
DAGDEVIREN_DEFAULT_MEDIUM_SCALES = [50, 100, 150, 200]
DAGDEVIREN_DEFAULT_LARGE_SCALES = [250, 500, 750, 1000]
DAGDEVIREN_DEFAULT_CAPACITY_BY_SCALE = {"small": 18, "medium": 16, "large": 16}
PRESET_TEST_JOB_TTL_SECONDS = 6 * 60 * 60
PRESET_TEST_JOB_MAX_RECORDS = 128

_PRESET_TEST_JOBS: Dict[str, Dict[str, Any]] = {}
_PRESET_TEST_JOBS_LOCK = threading.Lock()

LOG_DIR = Path(__file__).resolve().parents[1] / "data"
SOLVE_LOG_PATH = LOG_DIR / "solve_runs.jsonl"
TEST_RESULTS_DIR = LOG_DIR / "test_results"


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
    optimizeGoal: str = "best-weight"
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


class DagdevirenAnalysisRequest(BaseModel):
    datasetDir: Optional[str] = None
    files: Optional[List[str]] = None
    filenameContains: Optional[str] = None
    maxFiles: int = Field(default=400, ge=1, le=400)
    methods: Optional[List[str]] = None
    includeExact: bool = False
    capacityK: Optional[int] = Field(default=None, ge=1)
    optimizeK: bool = False
    optimizeGoal: str = "best-weight"
    optimizeMaxTrials: int = Field(default=18, ge=4, le=100)
    ratios: Optional[List[float]] = Field(default_factory=lambda: list(DAGDEVIREN_DEFAULT_RATIOS))
    smallScales: List[int] = Field(default_factory=lambda: list(DAGDEVIREN_DEFAULT_SMALL_SCALES))
    mediumScales: List[int] = Field(default_factory=lambda: list(DAGDEVIREN_DEFAULT_MEDIUM_SCALES))
    largeScales: List[int] = Field(default_factory=lambda: list(DAGDEVIREN_DEFAULT_LARGE_SCALES))
    capacityByScale: Dict[str, int] = Field(
        default_factory=lambda: dict(DAGDEVIREN_DEFAULT_CAPACITY_BY_SCALE)
    )
    popSize: int = Field(default=40, ge=2, le=300)
    generations: int = Field(default=60, ge=1, le=1000)
    seed: int = 42

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

    @field_validator("files")
    @classmethod
    def validate_files(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        cleaned = [Path(str(item)).name for item in value if str(item).strip()]
        deduped: List[str] = []
        seen = set()
        for item in cleaned:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped or None

    @field_validator("ratios")
    @classmethod
    def validate_ratios(cls, value: Optional[List[float]]) -> Optional[List[float]]:
        if value is None:
            return value
        ratios = sorted({round(float(item), 6) for item in value if float(item) > 0.0})
        return ratios or None

    @field_validator("smallScales", "mediumScales", "largeScales")
    @classmethod
    def validate_scale_lists(cls, value: List[int]) -> List[int]:
        deduped = sorted({int(item) for item in value if int(item) > 0})
        return deduped

    @field_validator("capacityByScale")
    @classmethod
    def validate_capacity_by_scale(cls, value: Dict[str, int]) -> Dict[str, int]:
        default_values = DAGDEVIREN_DEFAULT_CAPACITY_BY_SCALE
        normalized = dict(default_values)
        for key, item in value.items():
            name = str(key).strip().lower()
            if name not in default_values:
                continue
            ivalue = int(item)
            if ivalue >= 1:
                normalized[name] = ivalue
        return normalized


class DagdevirenPresetScaleTestRequest(BaseModel):
    datasetDir: Optional[str] = None
    filenameContains: Optional[str] = None
    maxFilesPerScale: int = Field(default=400, ge=1, le=400)
    scanLimit: int = Field(default=200000, ge=100, le=200000)
    targetScales: Optional[List[str]] = None
    fillMissingWithSynthetic: bool = False
    syntheticTargetPerScale: int = Field(default=1, ge=1, le=20)
    methods: Optional[List[str]] = None
    includeExact: bool = False
    capacityK: Optional[int] = Field(default=None, ge=1)
    optimizeK: bool = False
    optimizeGoal: str = "best-weight"
    optimizeMaxTrials: int = Field(default=18, ge=4, le=100)
    ratios: Optional[List[float]] = Field(default_factory=lambda: list(DAGDEVIREN_DEFAULT_RATIOS))
    capacityByScale: Dict[str, int] = Field(
        default_factory=lambda: dict(DAGDEVIREN_DEFAULT_CAPACITY_BY_SCALE)
    )
    popSize: int = Field(default=40, ge=2, le=300)
    generations: int = Field(default=60, ge=1, le=1000)
    seed: int = 42

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

    @field_validator("ratios")
    @classmethod
    def validate_ratios(cls, value: Optional[List[float]]) -> Optional[List[float]]:
        if value is None:
            return value
        ratios = sorted({round(float(item), 6) for item in value if float(item) > 0.0})
        return ratios or None

    @field_validator("capacityByScale")
    @classmethod
    def validate_capacity_by_scale(cls, value: Dict[str, int]) -> Dict[str, int]:
        default_values = DAGDEVIREN_DEFAULT_CAPACITY_BY_SCALE
        normalized = dict(default_values)
        for key, item in value.items():
            name = str(key).strip().lower()
            if name not in default_values:
                continue
            ivalue = int(item)
            if ivalue >= 1:
                normalized[name] = ivalue
        return normalized

    @field_validator("targetScales")
    @classmethod
    def validate_target_scales(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        allowed = set(DAGDEVIREN_SCALE_ORDER)
        deduped: List[str] = []
        seen = set()
        for item in value:
            name = str(item).strip().lower()
            if name not in allowed:
                raise ValueError(
                    f"Unsupported target scale: {name}. "
                    f"Use one of {', '.join(DAGDEVIREN_SCALE_ORDER)}."
                )
            if name not in seen:
                seen.add(name)
                deduped.append(name)
        return deduped or list(DAGDEVIREN_SCALE_ORDER)


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


def resolve_dataset_dir(raw_dataset_dir: Optional[str]) -> Path:
    if raw_dataset_dir is None or not str(raw_dataset_dir).strip():
        dataset_dir = DEFAULT_DAGDEVIREN_DATASET_DIR
    else:
        candidate = Path(str(raw_dataset_dir).strip()).expanduser()
        if not candidate.is_absolute():
            backend_root = Path(__file__).resolve().parents[1]
            candidate = backend_root / candidate
        dataset_dir = candidate

    dataset_dir = dataset_dir.resolve()
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Dataset directory not found: {dataset_dir}",
        )
    return dataset_dir


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


def _log_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"))
            f.write("\n")
    except Exception:
        # Logging must never break API responses.
        pass


def _safe_slug(value: Any, max_len: int = 80) -> str:
    text = str(value).strip().lower()
    if not text:
        return "item"
    chars: List[str] = []
    for ch in text:
        if ch.isalnum() or ch in {"-", "_"}:
            chars.append(ch)
        else:
            chars.append("_")
    slug = "".join(chars).strip("_")
    if not slug:
        slug = "item"
    return slug[:max_len]


def _write_json_snapshot(
    base_dir: Path,
    *,
    category: str,
    payload: Dict[str, Any],
    token: Optional[str] = None,
) -> Optional[str]:
    try:
        folder = base_dir / _safe_slug(category)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        name = stamp
        if token:
            name = f"{name}_{_safe_slug(token)}"
        file_path = folder / f"{name}.json"
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        return str(file_path)
    except Exception:
        # Snapshot persistence must never break API responses.
        return None


def _persist_test_snapshot(
    *,
    category: str,
    request_payload: Dict[str, Any],
    response_payload: Dict[str, Any],
    token: Optional[str] = None,
) -> Optional[str]:
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "request": request_payload,
        "response": response_payload,
    }
    return _write_json_snapshot(
        TEST_RESULTS_DIR,
        category=category,
        payload=snapshot,
        token=token,
    )


def _summarize_results(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for method, result in results.items():
        if result is None:
            summary.append({"method": method, "status": "null"})
            continue
        verification = result.get("verification") or {}
        summary.append(
            {
                "method": method,
                "isValid": bool(verification.get("isValid")),
                "weight": verification.get("totalWeight"),
                "coverSize": verification.get("coverSize"),
                "timeMs": result.get("time"),
                "paretoSize": len(result.get("paretoFront", []))
                if isinstance(result.get("paretoFront"), list)
                else None,
            }
        )
    return summary


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
        elif method in {"hga", "hga_v2", "weighted-and-cover-oriented-hga"}:
            if hga_budget_override is None:
                effective_pop, effective_gens = adaptive_hga_budget(
                    n_vertices,
                    pop_size,
                    generations,
                )
            else:
                effective_pop = max(2, int(hga_budget_override[0]))
                effective_gens = max(1, int(hga_budget_override[1]))
            if method == "hga_v2":
                result = solve_hga_v2(
                    vertex_data,
                    normalized_edges,
                    capacity_k,
                    effective_pop,
                    effective_gens,
                    seed,
                )
            elif method == "weighted-and-cover-oriented-hga":
                result = solve_weighted_and_cover_oriented_hga(
                    vertex_data,
                    normalized_edges,
                    capacity_k,
                    effective_pop,
                    effective_gens,
                    seed,
                )
            else:
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
        methods_to_run = [
            "gccvc",
            "grccvc",
            "gwccvc",
            "hga",
            "hga_v2",
            "weighted-and-cover-oriented-hga",
        ]
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

    # Capacity-k optimization is anchored to GRCCVC so selected k is directly comparable
    # against the same baseline in manual runs.
    trial_methods = ["grccvc"]
    trial_selector_method = "grccvc"

    trial_pop = min(payload.popSize, 22)
    trial_generations = min(payload.generations, 28)
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
            hga_budget_override=None,
        )
        trial_results_by_k[k] = run_results

        selector_result = run_results.get(trial_selector_method) or {}
        verification = selector_result.get("verification") or {}
        is_valid = bool(verification.get("isValid"))
        selector_weight = (
            round(float(verification.get("totalWeight", float("inf"))), 3)
            if is_valid
            else None
        )
        trial_by_k[k] = {
            "k": k,
            "feasible": is_valid,
            "bestMethod": trial_selector_method if is_valid else None,
            "bestWeight": selector_weight,
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
                "trialSelector": trial_selector_method,
                "trialBudget": int(payload.optimizeMaxTrials),
                "trialHgaBudget": {
                    "popSize": int(trial_hga_budget[0]),
                    "generations": int(trial_hga_budget[1]),
                }
                if any(
                    method in trial_methods
                    for method in {"hga", "hga_v2", "weighted-and-cover-oriented-hga"}
                )
                else None,
                "trials": trial_list,
            }
        )

    log_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request": payload.model_dump(),
        "meta": {
            "vertexCount": len(vertex_data),
            "edgeCount": len(normalized_edges),
            "capacityK": selected_k,
            "methodsRun": methods_to_run,
            "kBounds": k_bounds,
            "optimization": optimization_meta,
        },
        "resultsSummary": _summarize_results(final_results),
        "results": final_results,
    }
    _log_jsonl(SOLVE_LOG_PATH, log_payload)

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


@app.get("/api/analysis/dagdeviren/files")
def dagdeviren_files(
    datasetDir: Optional[str] = None,
    filenameContains: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=2000),
) -> Dict[str, Any]:
    dataset_dir = resolve_dataset_dir(datasetDir)
    files = list_dataset_files(
        dataset_dir,
        filename_contains=filenameContains,
        max_files=limit,
    )
    return {
        "datasetDir": str(dataset_dir),
        "count": len(files),
        "files": [file.name for file in files],
    }


@app.get("/api/analysis/dagdeviren/ratios")
def dagdeviren_ratios(
    datasetDir: Optional[str] = None,
    filenameContains: Optional[str] = None,
    limit: int = Query(default=2000, ge=1, le=20000),
) -> Dict[str, Any]:
    dataset_dir = resolve_dataset_dir(datasetDir)
    files = list_dataset_files(
        dataset_dir,
        filename_contains=filenameContains,
        max_files=limit,
    )

    ratios = sorted(
        {
            round(float(scale["m"]) / float(scale["n"]), 6)
            for scale in (parse_scale_from_filename(path.name) for path in files)
            if scale["n"] and scale["m"]
        }
    )
    ratio_file_counts: Dict[str, int] = {}
    for path in files:
        scale = parse_scale_from_filename(path.name)
        if not scale["n"] or not scale["m"]:
            continue
        key = f"{(float(scale['m']) / float(scale['n'])):.6f}".rstrip("0").rstrip(".")
        ratio_file_counts[key] = ratio_file_counts.get(key, 0) + 1

    return {
        "datasetDir": str(dataset_dir),
        "count": len(ratios),
        "ratios": ratios,
        "ratioFileCounts": ratio_file_counts,
    }


def _normalized_ratio_set(values: Optional[List[float]]) -> Optional[set]:
    if not values:
        return None
    return {round(float(value), 6) for value in values if float(value) > 0.0}


def _scale_triplet_from_filename(name: str) -> Optional[Tuple[int, int, int]]:
    scale = parse_scale_from_filename(name)
    n = scale.get("n")
    m = scale.get("m")
    s = scale.get("s")
    if n is None or m is None or s is None:
        return None
    n_value = int(n)
    m_value = int(m)
    s_value = int(s)
    if n_value <= 0 or m_value < 0 or s_value <= 0:
        return None
    return (n_value, m_value, s_value)


def _select_bucket_files(
    *,
    candidate_files: List[Path],
    node_counts: List[int],
    allowed_ratios: Optional[set],
    max_files: int,
) -> List[str]:
    wanted_nodes = {int(value) for value in node_counts if int(value) > 0}
    # Keep signature compatibility; preset selection now always includes all s seeds per (n,m) pair.
    _ = max(1, int(max_files))
    grouped: Dict[Tuple[int, int], List[Tuple[int, str]]] = {}
    for path in candidate_files:
        parsed = _scale_triplet_from_filename(path.name)
        if parsed is None:
            continue
        n, m, s = parsed
        if n not in wanted_nodes:
            continue
        ratio = round(float(m) / float(max(1, n)), 6)
        if allowed_ratios is not None and ratio not in allowed_ratios:
            continue
        grouped.setdefault((n, m), []).append((s, path.name))

    selected: List[str] = []
    for pair in sorted(grouped.keys()):
        seeds = sorted(grouped[pair], key=lambda item: (item[0], item[1]))
        selected.extend(name for _, name in seeds)
    return selected


def _ratio_key(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _build_pair_coverage(file_names: List[str]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[int, int], List[Tuple[int, str]]] = {}
    for file_name in file_names:
        parsed = _scale_triplet_from_filename(file_name)
        if parsed is None:
            continue
        n, m, s = parsed
        grouped.setdefault((n, m), []).append((s, file_name))

    rows: List[Dict[str, Any]] = []
    for pair in sorted(grouped.keys()):
        n, m = pair
        values = sorted(grouped[pair], key=lambda item: (item[0], item[1]))
        s_values = [seed for seed, _ in values]
        rows.append(
            {
                "n": n,
                "m": m,
                "ratio": round(float(m) / float(n), 6) if n > 0 else None,
                "sCount": len(values),
                "sValues": s_values,
                "files": [name for _, name in values],
            }
        )
    return rows


def _method_summary(graph_rows: List[Dict[str, Any]], methods: List[str]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for method in methods:
        attempted = 0
        valid_runs = 0
        times: List[float] = []
        weights: List[float] = []
        cover_sizes: List[float] = []

        for row in graph_rows:
            results = row.get("results") or {}
            if method in results:
                attempted += 1
            result = results.get(method)
            if not result:
                continue

            result_time = float(result.get("time", float("nan")))
            if math.isfinite(result_time):
                times.append(result_time)

            verification = result.get("verification") or {}
            if bool(verification.get("isValid")):
                valid_runs += 1
                total_weight = float(verification.get("totalWeight", float("nan")))
                cover_size = float(verification.get("coverSize", float("nan")))
                if math.isfinite(total_weight):
                    weights.append(total_weight)
                if math.isfinite(cover_size):
                    cover_sizes.append(cover_size)

        summary[method] = {
            "attempted": attempted,
            "validRuns": valid_runs,
            "validRate": round(float(valid_runs / attempted), 6) if attempted else 0.0,
            "avgTimeMs": round(float(sum(times) / len(times)), 6) if times else None,
            "avgWeight": round(float(sum(weights) / len(weights)), 6) if weights else None,
            "avgCoverSize": round(float(sum(cover_sizes) / len(cover_sizes)), 6) if cover_sizes else None,
        }

    return summary


def _update_graph_analysis_summary(graph_analysis: Dict[str, Any]) -> None:
    graph_rows = graph_analysis.get("graphs") or []
    methods = list(graph_analysis.get("methods") or [])

    discovered: set[float] = set()
    ratio_counts: Dict[str, int] = {}
    for row in graph_rows:
        ratio = row.get("ratio")
        if ratio is None:
            continue
        ratio_value = round(float(ratio), 6)
        discovered.add(ratio_value)
        key = _ratio_key(ratio_value)
        ratio_counts[key] = ratio_counts.get(key, 0) + 1

    graph_analysis["discoveredRatios"] = sorted(discovered)
    graph_analysis["ratioCounts"] = ratio_counts
    graph_analysis["graphCount"] = len(graph_rows)
    graph_analysis["errorCount"] = len(graph_analysis.get("errors") or [])
    graph_analysis["summary"] = {
        "graphCount": len(graph_rows),
        "methodSummary": _method_summary(graph_rows, methods),
    }


def _build_synthetic_graph_payload(
    *,
    node_count: int,
    ratio: float,
    seed: int,
) -> Dict[str, Any]:
    n = max(2, int(node_count))
    ratio_value = max(0.5, float(ratio))
    target_edges = int(round(n * ratio_value))
    min_edges = n - 1
    max_edges = (n * (n - 1)) // 2
    target_edges = max(min_edges, min(max_edges, target_edges))

    rnd = random.Random(seed)
    vertices = [
        {"id": node_id, "weight": round(1.0 + rnd.random() * 99.0, 3)}
        for node_id in range(1, n + 1)
    ]

    edges: set[Tuple[int, int]] = set()
    for node_id in range(2, n + 1):
        parent = rnd.randint(1, node_id - 1)
        edges.add((parent, node_id) if parent < node_id else (node_id, parent))

    attempts = 0
    max_attempts = max(10_000, target_edges * 12)
    while len(edges) < target_edges and attempts < max_attempts:
        attempts += 1
        u = rnd.randint(1, n)
        v = rnd.randint(1, n - 1)
        if v >= u:
            v += 1
        edge = (u, v) if u < v else (v, u)
        edges.add(edge)

    edge_list = sorted(edges)
    actual_edges = len(edge_list)
    synthetic_name = f"n{n}_m{actual_edges}_s{seed}.txt"
    return {
        "name": synthetic_name,
        "vertices": vertices,
        "edges": edge_list,
        "declaredNodeCount": n,
        "declaredEdgeCount": actual_edges,
        "parsedNodeCount": n,
        "parsedEdgeCount": actual_edges,
    }


def _planned_synthetic_specs(
    *,
    bucket: str,
    node_counts: List[int],
    ratios: List[float],
    existing_files: List[str],
    needed_count: int,
    base_seed: int,
) -> List[Dict[str, Any]]:
    if needed_count <= 0:
        return []

    existing_node_counts: set[int] = set()
    existing_ratios: set[float] = set()
    for file_name in existing_files:
        scale = parse_scale_from_filename(file_name)
        n = scale.get("n")
        m = scale.get("m")
        if n and m and int(n) > 0:
            existing_node_counts.add(int(n))
            existing_ratios.add(round(float(m) / float(n), 6))

    node_candidates = [
        int(value)
        for value in node_counts
        if int(value) > 0 and int(value) not in existing_node_counts
    ] or [int(value) for value in node_counts if int(value) > 0]
    ratio_candidates = [
        round(float(value), 6)
        for value in ratios
        if float(value) > 0.0 and round(float(value), 6) not in existing_ratios
    ] or [round(float(value), 6) for value in ratios if float(value) > 0.0]

    if not node_candidates or not ratio_candidates:
        return []

    bucket_offset = {"small": 0, "medium": 10000, "large": 20000}.get(bucket, 30000)
    planned: List[Dict[str, Any]] = []
    for index in range(needed_count):
        node_count = node_candidates[index % len(node_candidates)]
        ratio_value = ratio_candidates[index % len(ratio_candidates)]
        planned.append(
            {
                "bucket": bucket,
                "nodeCount": node_count,
                "ratio": ratio_value,
                "seed": int(base_seed) + bucket_offset + index,
            }
        )
    return planned


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prune_preset_test_jobs_locked(now_ts: float) -> None:
    expired_job_ids: List[str] = []
    for job_id, job in _PRESET_TEST_JOBS.items():
        status = str(job.get("status") or "")
        if status in {"queued", "running"}:
            continue
        reference_ts = float(job.get("completedAtTs") or job.get("createdAtTs") or 0.0)
        if reference_ts > 0.0 and now_ts - reference_ts > PRESET_TEST_JOB_TTL_SECONDS:
            expired_job_ids.append(job_id)
    for job_id in expired_job_ids:
        _PRESET_TEST_JOBS.pop(job_id, None)

    overflow = len(_PRESET_TEST_JOBS) - PRESET_TEST_JOB_MAX_RECORDS
    if overflow > 0:
        ordered = sorted(
            _PRESET_TEST_JOBS.items(),
            key=lambda item: float(item[1].get("createdAtTs") or 0.0),
        )
        for job_id, _ in ordered[:overflow]:
            _PRESET_TEST_JOBS.pop(job_id, None)


def _run_dagdeviren_preset_tests(payload: DagdevirenPresetScaleTestRequest) -> Dict[str, Any]:
    dataset_dir = resolve_dataset_dir(payload.datasetDir)
    methods = payload.methods or [
        "gccvc",
        "grccvc",
        "gwccvc",
        "hga",
        "hga_v2",
        "weighted-and-cover-oriented-hga",
    ]
    ratios = payload.ratios or list(DAGDEVIREN_DEFAULT_RATIOS)
    ratio_set = _normalized_ratio_set(ratios)
    capacity_by_scale = payload.capacityByScale or dict(DAGDEVIREN_DEFAULT_CAPACITY_BY_SCALE)
    requested_scales = payload.targetScales or list(DAGDEVIREN_SCALE_ORDER)
    enabled_scales = set(requested_scales)

    candidate_files = list_dataset_files(
        dataset_dir,
        filename_contains=payload.filenameContains,
        max_files=payload.scanLimit,
    )
    small_files = (
        _select_bucket_files(
            candidate_files=candidate_files,
            node_counts=DAGDEVIREN_DEFAULT_SMALL_SCALES,
            allowed_ratios=ratio_set,
            max_files=payload.maxFilesPerScale,
        )
        if "small" in enabled_scales
        else []
    )
    medium_files = (
        _select_bucket_files(
            candidate_files=candidate_files,
            node_counts=DAGDEVIREN_DEFAULT_MEDIUM_SCALES,
            allowed_ratios=ratio_set,
            max_files=payload.maxFilesPerScale,
        )
        if "medium" in enabled_scales
        else []
    )
    large_files = (
        _select_bucket_files(
            candidate_files=candidate_files,
            node_counts=DAGDEVIREN_DEFAULT_LARGE_SCALES,
            allowed_ratios=ratio_set,
            max_files=payload.maxFilesPerScale,
        )
        if "large" in enabled_scales
        else []
    )

    selected_files: List[str] = []
    seen = set()
    for name in small_files + medium_files + large_files:
        if name in seen:
            continue
        seen.add(name)
        selected_files.append(name)

    small_pair_coverage = _build_pair_coverage(small_files)
    medium_pair_coverage = _build_pair_coverage(medium_files)
    large_pair_coverage = _build_pair_coverage(large_files)
    selected_pair_count = (
        len(small_pair_coverage)
        + len(medium_pair_coverage)
        + len(large_pair_coverage)
    )

    analysis_files: Optional[List[str]]
    if payload.targetScales is not None:
        analysis_files = list(selected_files)
    else:
        analysis_files = selected_files or None

    graph_analyzer = GraphAnalyzer(
        methods=methods,
        include_exact=payload.includeExact,
        pop_size=payload.popSize,
        generations=payload.generations,
        seed=payload.seed,
        fixed_capacity_k=payload.capacityK,
        optimize_k=payload.optimizeK,
        optimize_goal=payload.optimizeGoal,
        optimize_max_trials=payload.optimizeMaxTrials,
        ratios=ratios,
        small_scales=DAGDEVIREN_DEFAULT_SMALL_SCALES,
        medium_scales=DAGDEVIREN_DEFAULT_MEDIUM_SCALES,
        large_scales=DAGDEVIREN_DEFAULT_LARGE_SCALES,
        capacity_by_scale=capacity_by_scale,
        exact_timebox_scales=["small", "medium"],
        exact_timebox_multiplier=2.0,
        exact_timebox_min_ms=1.0,
    )
    graph_analysis = graph_analyzer.analyze_dataset(
        dataset_dir=dataset_dir,
        files=analysis_files,
        filename_contains=None if analysis_files is not None else payload.filenameContains,
        max_files=max(1, len(selected_files) or payload.maxFilesPerScale * 3),
    )

    synthetic_generated_by_scale: Dict[str, List[str]] = {
        "small": [],
        "medium": [],
        "large": [],
    }
    synthetic_target_per_scale = max(
        1,
        min(
            int(payload.syntheticTargetPerScale),
            int(payload.maxFilesPerScale),
            max(1, max(len(DAGDEVIREN_DEFAULT_SMALL_SCALES), len(ratios))),
        ),
    )

    if payload.fillMissingWithSynthetic:
        scale_input = {
            "small": {
                "nodeCounts": list(DAGDEVIREN_DEFAULT_SMALL_SCALES),
                "selectedFiles": list(small_files),
            },
            "medium": {
                "nodeCounts": list(DAGDEVIREN_DEFAULT_MEDIUM_SCALES),
                "selectedFiles": list(medium_files),
            },
            "large": {
                "nodeCounts": list(DAGDEVIREN_DEFAULT_LARGE_SCALES),
                "selectedFiles": list(large_files),
            },
        }

        for bucket_name, bucket_payload in scale_input.items():
            if bucket_name not in enabled_scales:
                continue
            selected_bucket_files = bucket_payload["selectedFiles"]
            needed_count = max(0, synthetic_target_per_scale - len(selected_bucket_files))
            specs = _planned_synthetic_specs(
                bucket=bucket_name,
                node_counts=bucket_payload["nodeCounts"],
                ratios=ratios,
                existing_files=selected_bucket_files,
                needed_count=needed_count,
                base_seed=payload.seed,
            )
            for spec in specs:
                graph_payload = _build_synthetic_graph_payload(
                    node_count=spec["nodeCount"],
                    ratio=spec["ratio"],
                    seed=spec["seed"],
                )
                try:
                    graph_row = graph_analyzer._analyze_single_graph(graph_payload)
                    graph_analysis["graphs"].append(graph_row)
                    synthetic_generated_by_scale[bucket_name].append(graph_payload["name"])
                except Exception as exc:
                    graph_analysis.setdefault("errors", []).append(
                        {
                            "file": graph_payload["name"],
                            "error": f"synthetic_generation_failed: {exc}",
                        }
                    )

    _update_graph_analysis_summary(graph_analysis)
    preset_scale_tests = PresetScaleTestAnalyzer().build(graph_analysis["graphs"])
    synthetic_generated_count = sum(len(value) for value in synthetic_generated_by_scale.values())

    return {
        "meta": {
            "datasetDir": str(dataset_dir),
            "methods": graph_analysis["methods"],
            "capacityK": payload.capacityK,
            "optimizeK": payload.optimizeK,
            "optimizeGoal": payload.optimizeGoal,
            "optimizeMaxTrials": payload.optimizeMaxTrials,
            "filenameContains": payload.filenameContains,
            "ratios": ratios,
            "targetScales": requested_scales,
            "smallScales": list(DAGDEVIREN_DEFAULT_SMALL_SCALES),
            "mediumScales": list(DAGDEVIREN_DEFAULT_MEDIUM_SCALES),
            "largeScales": list(DAGDEVIREN_DEFAULT_LARGE_SCALES),
            "capacityByScale": capacity_by_scale,
            "maxFilesPerScale": payload.maxFilesPerScale,
            "selectionMode": "grouped-by-n-m-include-all-s",
            "presetExactPolicy": {
                "enabledForScales": ["small", "medium"],
                "runOrder": "non-exact-first-then-exact",
                "timeBudgetMultiplier": 2.0,
                "timeBudgetReference": "longest-non-exact-time",
                "onInvalid": "solution is not valid",
            },
            "syntheticEnabled": payload.fillMissingWithSynthetic,
            "syntheticTargetPerScale": synthetic_target_per_scale,
            "syntheticGeneratedCount": synthetic_generated_count,
            "graphCount": graph_analysis["graphCount"],
            "errorCount": graph_analysis["errorCount"],
        },
        "selection": {
            "candidateCount": len(candidate_files),
            "selectedCount": len(selected_files),
            "selectedPairCount": selected_pair_count,
            "totalAnalyzedGraphs": graph_analysis["graphCount"],
            "targetScales": requested_scales,
            "small": {
                "requestedNodeCounts": list(DAGDEVIREN_DEFAULT_SMALL_SCALES),
                "selectedFiles": small_files,
                "pairCoverage": small_pair_coverage,
                "syntheticFiles": synthetic_generated_by_scale["small"],
            },
            "medium": {
                "requestedNodeCounts": list(DAGDEVIREN_DEFAULT_MEDIUM_SCALES),
                "selectedFiles": medium_files,
                "pairCoverage": medium_pair_coverage,
                "syntheticFiles": synthetic_generated_by_scale["medium"],
            },
            "large": {
                "requestedNodeCounts": list(DAGDEVIREN_DEFAULT_LARGE_SCALES),
                "selectedFiles": large_files,
                "pairCoverage": large_pair_coverage,
                "syntheticFiles": synthetic_generated_by_scale["large"],
            },
            "synthetic": {
                "enabled": payload.fillMissingWithSynthetic,
                "targetPerScale": synthetic_target_per_scale,
                "generatedCount": synthetic_generated_count,
            },
        },
        "graphAnalysis": graph_analysis,
        "presetScaleTests": preset_scale_tests,
    }


def _preset_test_job_worker(job_id: str, payload_data: Dict[str, Any]) -> None:
    started_at_ts = time.time()
    with _PRESET_TEST_JOBS_LOCK:
        job = _PRESET_TEST_JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "running"
        job["startedAt"] = _utc_now_iso()
        job["startedAtTs"] = started_at_ts

    try:
        payload = DagdevirenPresetScaleTestRequest.model_validate(payload_data)
        result = _run_dagdeviren_preset_tests(payload)
        result_file = _persist_test_snapshot(
            category="dagdeviren_preset_tests_job",
            request_payload=payload_data,
            response_payload=result,
            token=job_id,
        )
        if result_file:
            result_meta = result.get("meta")
            if isinstance(result_meta, dict):
                result_meta["savedResultPath"] = result_file
            else:
                result["meta"] = {"savedResultPath": result_file}
    except Exception as exc:
        result_file = _persist_test_snapshot(
            category="dagdeviren_preset_tests_job_failed",
            request_payload=payload_data,
            response_payload={
                "jobId": job_id,
                "error": str(exc),
            },
            token=job_id,
        )
        completed_at_ts = time.time()
        with _PRESET_TEST_JOBS_LOCK:
            job = _PRESET_TEST_JOBS.get(job_id)
            if job is None:
                return
            job["status"] = "failed"
            job["error"] = str(exc)
            job["completedAt"] = _utc_now_iso()
            job["completedAtTs"] = completed_at_ts
            job["result"] = None
            job["resultFile"] = result_file
        return

    completed_at_ts = time.time()
    with _PRESET_TEST_JOBS_LOCK:
        job = _PRESET_TEST_JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "completed"
        job["error"] = None
        job["completedAt"] = _utc_now_iso()
        job["completedAtTs"] = completed_at_ts
        job["result"] = result
        job["resultFile"] = result.get("meta", {}).get("savedResultPath")


@app.post("/api/analysis/dagdeviren/preset-tests")
def dagdeviren_preset_tests(payload: DagdevirenPresetScaleTestRequest) -> Dict[str, Any]:
    result = _run_dagdeviren_preset_tests(payload)
    result_file = _persist_test_snapshot(
        category="dagdeviren_preset_tests",
        request_payload=payload.model_dump(),
        response_payload=result,
    )
    if result_file:
        result_meta = result.get("meta")
        if isinstance(result_meta, dict):
            result_meta["savedResultPath"] = result_file
        else:
            result["meta"] = {"savedResultPath": result_file}
    return result


@app.post("/api/analysis/dagdeviren/preset-tests/start")
def dagdeviren_preset_tests_start(payload: DagdevirenPresetScaleTestRequest) -> Dict[str, Any]:
    job_id = uuid.uuid4().hex
    created_at_ts = time.time()
    payload_data = payload.model_dump()
    created_at = _utc_now_iso()
    with _PRESET_TEST_JOBS_LOCK:
        _prune_preset_test_jobs_locked(created_at_ts)
        _PRESET_TEST_JOBS[job_id] = {
            "status": "queued",
            "createdAt": created_at,
            "createdAtTs": created_at_ts,
            "startedAt": None,
            "startedAtTs": None,
            "completedAt": None,
            "completedAtTs": None,
            "error": None,
            "result": None,
            "resultFile": None,
        }

    worker = threading.Thread(
        target=_preset_test_job_worker,
        args=(job_id, payload_data),
        daemon=True,
    )
    worker.start()
    return {
        "jobId": job_id,
        "status": "queued",
        "createdAt": created_at,
    }


@app.get("/api/analysis/dagdeviren/preset-tests/jobs/{job_id}")
def dagdeviren_preset_tests_job_status(job_id: str) -> Dict[str, Any]:
    with _PRESET_TEST_JOBS_LOCK:
        _prune_preset_test_jobs_locked(time.time())
        job = _PRESET_TEST_JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Preset test job not found.")
        payload: Dict[str, Any] = {
            "jobId": job_id,
            "status": job.get("status"),
            "createdAt": job.get("createdAt"),
            "startedAt": job.get("startedAt"),
            "completedAt": job.get("completedAt"),
            "error": job.get("error"),
            "resultFile": job.get("resultFile"),
        }
        if job.get("status") == "completed":
            payload["result"] = job.get("result")
        return payload


@app.post("/api/analysis/dagdeviren/run")
def dagdeviren_run(payload: DagdevirenAnalysisRequest) -> Dict[str, Any]:
    dataset_dir = resolve_dataset_dir(payload.datasetDir)
    methods = payload.methods or [
        "gccvc",
        "grccvc",
        "gwccvc",
        "hga",
        "hga_v2",
        "weighted-and-cover-oriented-hga",
    ]
    ratios = payload.ratios or list(DAGDEVIREN_DEFAULT_RATIOS)
    small_scales = payload.smallScales or list(DAGDEVIREN_DEFAULT_SMALL_SCALES)
    medium_scales = payload.mediumScales or list(DAGDEVIREN_DEFAULT_MEDIUM_SCALES)
    large_scales = payload.largeScales or list(DAGDEVIREN_DEFAULT_LARGE_SCALES)
    capacity_by_scale = payload.capacityByScale or dict(DAGDEVIREN_DEFAULT_CAPACITY_BY_SCALE)

    graph_analyzer = GraphAnalyzer(
        methods=methods,
        include_exact=payload.includeExact,
        pop_size=payload.popSize,
        generations=payload.generations,
        seed=payload.seed,
        fixed_capacity_k=payload.capacityK,
        optimize_k=payload.optimizeK,
        optimize_goal=payload.optimizeGoal,
        optimize_max_trials=payload.optimizeMaxTrials,
        ratios=ratios,
        small_scales=small_scales,
        medium_scales=medium_scales,
        large_scales=large_scales,
        capacity_by_scale=capacity_by_scale,
    )
    graph_analysis = graph_analyzer.analyze_dataset(
        dataset_dir=dataset_dir,
        files=payload.files,
        filename_contains=payload.filenameContains,
        max_files=payload.maxFiles,
    )

    scale_analysis = ScaleAnalyzer().analyze(graph_analysis["graphs"])
    connectivity_visualization = ConnectivityRatioVisualizer().build(graph_analysis["graphs"])
    scale_visualization = ScaleVisualizer().build(scale_analysis)

    response_payload = {
        "meta": {
            "datasetDir": str(dataset_dir),
            "methods": graph_analysis["methods"],
            "capacityK": payload.capacityK,
            "optimizeK": payload.optimizeK,
            "optimizeGoal": payload.optimizeGoal,
            "optimizeMaxTrials": payload.optimizeMaxTrials,
            "maxFiles": payload.maxFiles,
            "filenameContains": payload.filenameContains,
            "ratios": ratios,
            "smallScales": small_scales,
            "mediumScales": medium_scales,
            "largeScales": large_scales,
            "capacityByScale": capacity_by_scale,
            "graphCount": graph_analysis["graphCount"],
            "errorCount": graph_analysis["errorCount"],
        },
        "graphAnalysis": graph_analysis,
        "scaleAnalysis": scale_analysis,
        "connectivityRatioVisualization": connectivity_visualization,
        "scaleVisualization": scale_visualization,
    }
    result_file = _persist_test_snapshot(
        category="dagdeviren_run",
        request_payload=payload.model_dump(),
        response_payload=response_payload,
    )
    if result_file:
        response_payload["meta"]["savedResultPath"] = result_file
    return response_payload
