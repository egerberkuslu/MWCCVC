#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis_tools.PresetScaleTestAnalyzer import PresetScaleTestAnalyzer
from app.analysis_tools.GraphAnalyzer import GraphAnalyzer
from app.analysis_tools.datareader import list_dataset_files, parse_scale_from_filename

DEFAULT_DATASET_DIR = BACKEND_DIR / "data" / "DagdevirenDataset"
DEFAULT_METHODS = ["gccvc", "grccvc", "gwccvc", "hga", "hga_v2"]
DEFAULT_SMALL_SCALES = [10, 15, 20, 25]
DEFAULT_MEDIUM_SCALES = [50, 100, 150, 200]
DEFAULT_LARGE_SCALES = [250, 500, 750, 1000]
DEFAULT_CAPACITY_BY_SCALE = {"small": 18, "medium": 16, "large": 16}


def log(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_optional_int_env(name: str, default: Optional[int]) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"", "null", "none"}:
        return None
    return int(raw)


def parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None else int(raw)


def resolve_dataset_dir(raw_dataset_dir: Optional[str]) -> Path:
    if raw_dataset_dir is None:
        return DEFAULT_DATASET_DIR
    candidate = Path(str(raw_dataset_dir)).expanduser()
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    return candidate


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def normalized_ratio_set(values: Optional[Sequence[float]]) -> Optional[set[float]]:
    if not values:
        return None
    return {round(float(value), 6) for value in values if float(value) > 0.0}


def ratios_from_files(file_names: Sequence[str]) -> List[float]:
    values: set[float] = set()
    for file_name in file_names:
        parsed = scale_triplet_from_filename(file_name)
        if parsed is None:
            continue
        n, m, _ = parsed
        if n <= 0:
            continue
        values.add(round(float(m) / float(n), 6))
    return sorted(values)


def scale_triplet_from_filename(name: str) -> Optional[Tuple[int, int, int]]:
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


def select_bucket_files(
    *,
    candidate_files: Sequence[Path],
    node_counts: Sequence[int],
    allowed_ratios: Optional[set[float]],
) -> List[str]:
    wanted_nodes = {int(value) for value in node_counts if int(value) > 0}
    grouped: Dict[Tuple[int, int], List[Tuple[int, str]]] = {}
    for path in candidate_files:
        parsed = scale_triplet_from_filename(path.name)
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


def build_pair_coverage(file_names: Sequence[str]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[int, int], List[Tuple[int, str]]] = {}
    for file_name in file_names:
        parsed = scale_triplet_from_filename(file_name)
        if parsed is None:
            continue
        n, m, s = parsed
        grouped.setdefault((n, m), []).append((s, file_name))

    rows: List[Dict[str, Any]] = []
    for pair in sorted(grouped.keys()):
        n, m = pair
        values = sorted(grouped[pair], key=lambda item: (item[0], item[1]))
        rows.append(
            {
                "n": n,
                "m": m,
                "ratio": round(float(m) / float(n), 6) if n > 0 else None,
                "sCount": len(values),
                "sValues": [seed for seed, _ in values],
                "files": [name for _, name in values],
            }
        )
    return rows


def ratio_key(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def method_summary(graph_rows: Sequence[Dict[str, Any]], methods: Sequence[str]) -> Dict[str, Any]:
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
            "avgCoverSize": round(float(sum(cover_sizes) / len(cover_sizes)), 6)
            if cover_sizes
            else None,
        }
    return summary


def update_graph_analysis_summary(graph_analysis: Dict[str, Any]) -> None:
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
        key = ratio_key(ratio_value)
        ratio_counts[key] = ratio_counts.get(key, 0) + 1

    graph_analysis["discoveredRatios"] = sorted(discovered)
    graph_analysis["ratioCounts"] = ratio_counts
    graph_analysis["graphCount"] = len(graph_rows)
    graph_analysis["errorCount"] = len(graph_analysis.get("errors") or [])
    graph_analysis["summary"] = {
        "graphCount": len(graph_rows),
        "methodSummary": method_summary(graph_rows, methods),
    }


def safe_path_component(value: str) -> str:
    chars: List[str] = []
    for ch in str(value):
        if ch.isalnum() or ch in {"-", "_", "."}:
            chars.append(ch)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or "item"


def stable_hash(payload: Dict[str, Any], *, length: int = 16) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:length]


def file_result_path(results_dir: Path, index: int, file_name: str) -> Path:
    return results_dir / f"{index + 1:03d}_{safe_path_component(file_name)}.json"


def build_single_file_payload(
    *,
    file_name: str,
    dataset_filter: str,
    max_files_per_scale: int,
    manual_capacity_k: Optional[int],
    optimize_k: bool,
    optimize_goal: str,
    optimize_trials: int,
    pop_size: int,
    generations: int,
    seed: int,
    selected_ratios: Sequence[float],
) -> Dict[str, Any]:
    return {
        "files": [file_name],
        "filenameContains": dataset_filter or None,
        "maxFiles": max(1, min(max_files_per_scale, 400)),
        "methods": list(DEFAULT_METHODS),
        "includeExact": False,
        "capacityK": manual_capacity_k,
        "optimizeK": optimize_k,
        "optimizeGoal": optimize_goal,
        "optimizeMaxTrials": optimize_trials,
        "ratios": list(selected_ratios),
        "smallScales": list(DEFAULT_SMALL_SCALES),
        "mediumScales": list(DEFAULT_MEDIUM_SCALES),
        "largeScales": list(DEFAULT_LARGE_SCALES),
        "capacityByScale": dict(DEFAULT_CAPACITY_BY_SCALE),
        "popSize": pop_size,
        "generations": generations,
        "seed": seed,
    }


def run_single_file_analysis_local(payload: Dict[str, Any]) -> Dict[str, Any]:
    dataset_dir = resolve_dataset_dir(payload.get("datasetDir"))
    methods = list(payload.get("methods") or DEFAULT_METHODS)
    small_scales = list(payload.get("smallScales") or DEFAULT_SMALL_SCALES)
    medium_scales = list(payload.get("mediumScales") or DEFAULT_MEDIUM_SCALES)
    large_scales = list(payload.get("largeScales") or DEFAULT_LARGE_SCALES)
    capacity_by_scale = dict(payload.get("capacityByScale") or DEFAULT_CAPACITY_BY_SCALE)

    graph_analyzer = GraphAnalyzer(
        methods=methods,
        include_exact=bool(payload.get("includeExact")),
        pop_size=int(payload.get("popSize") or 100),
        generations=int(payload.get("generations") or 100),
        seed=int(payload.get("seed") or 42),
        fixed_capacity_k=payload.get("capacityK"),
        optimize_k=bool(payload.get("optimizeK")),
        optimize_goal=str(payload.get("optimizeGoal") or "best-weight"),
        optimize_max_trials=int(payload.get("optimizeMaxTrials") or 14),
        ratios=[],
        small_scales=small_scales,
        medium_scales=medium_scales,
        large_scales=large_scales,
        capacity_by_scale=capacity_by_scale,
        exact_timebox_scales=["medium", "large"],
        exact_timebox_multiplier=2.0,
        exact_timebox_min_ms=1.0,
        exact_forced_scales=["small", "medium", "large"],
        exact_unbounded_scales=["small"],
    )
    graph_analysis = graph_analyzer.analyze_dataset(
        dataset_dir=dataset_dir,
        files=payload.get("files"),
        filename_contains=payload.get("filenameContains"),
        max_files=int(payload.get("maxFiles") or 400),
    )

    return {
        "meta": {
            "datasetDir": str(dataset_dir),
            "methods": graph_analysis["methods"],
            "capacityK": payload.get("capacityK"),
            "optimizeK": bool(payload.get("optimizeK")),
            "optimizeGoal": payload.get("optimizeGoal"),
            "optimizeMaxTrials": payload.get("optimizeMaxTrials"),
            "maxFiles": int(payload.get("maxFiles") or 400),
            "filenameContains": payload.get("filenameContains"),
            "singleFileMode": True,
            "ratios": [],
            "smallScales": small_scales,
            "mediumScales": medium_scales,
            "largeScales": large_scales,
            "capacityByScale": capacity_by_scale,
            "singleFileExactPolicy": {
                "enabled": True,
                "forcedScales": ["small", "medium", "large"],
                "smallScaleTimeBudget": "none",
                "timedScales": ["medium", "large"],
                "timeBudgetMultiplier": 2.0,
                "timeBudgetReference": "longest-non-exact-time",
                "onInvalid": "solution is not valid",
            },
            "graphCount": graph_analysis["graphCount"],
            "errorCount": graph_analysis["errorCount"],
        },
        "graphAnalysis": graph_analysis,
    }


def run_single_file_analysis(
    *,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return run_single_file_analysis_local(payload)


def load_result_artifact(path: Path, expected_file: str) -> Optional[Dict[str, Any]]:
    data = load_json(path)
    if not data or data.get("file") != expected_file:
        return None
    response = data.get("response") or {}
    graph_analysis = response.get("graphAnalysis") or {}
    if not isinstance(graph_analysis.get("graphs"), list):
        return None
    if not isinstance(graph_analysis.get("errors"), list):
        return None
    return data


def collect_completed_artifacts(
    *,
    selected_files: Sequence[str],
    results_dir: Path,
) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for index, file_name in enumerate(selected_files):
        artifact = load_result_artifact(file_result_path(results_dir, index, file_name), file_name)
        if artifact is not None:
            artifacts.append(artifact)
    return artifacts


def build_selection_payload(
    *,
    dataset_dir: Path,
    dataset_filter: str,
    max_files_per_scale: int,
) -> Dict[str, Any]:
    candidate_files = list_dataset_files(
        dataset_dir,
        filename_contains=dataset_filter or None,
        max_files=200000,
    )
    selected_files = select_bucket_files(
        candidate_files=candidate_files,
        node_counts=DEFAULT_LARGE_SCALES,
        allowed_ratios=None,
    )
    pair_coverage = build_pair_coverage(selected_files)
    analysis_max_files = max(1, len(selected_files) or max_files_per_scale * 3)
    return {
        "datasetDir": str(dataset_dir),
        "candidateCount": len(candidate_files),
        "selectedFiles": selected_files,
        "selectedRatios": ratios_from_files(selected_files),
        "pairCoverage": pair_coverage,
        "selectedPairCount": len(pair_coverage),
        "analysisMaxFiles": analysis_max_files,
    }


def build_manifest(
    *,
    run_key: str,
    run_dir: Path,
    export_json_path: Path,
    results_dir: Path,
    aggregate_path: Path,
    config_payload: Dict[str, Any],
    selection_payload: Dict[str, Any],
    completed_artifacts: Sequence[Dict[str, Any]],
    status: str,
    created_at: str,
) -> Dict[str, Any]:
    completed_files = [str(item.get("file")) for item in completed_artifacts if item.get("file")]
    selected_files = list(selection_payload.get("selectedFiles") or [])
    completed_file_set = set(completed_files)
    pending_files = [name for name in selected_files if name not in completed_file_set]
    return {
        "version": 1,
        "runKey": run_key,
        "targetScale": "large",
        "status": status,
        "createdAt": created_at,
        "updatedAt": utc_now_iso(),
        "runDir": str(run_dir),
        "aggregateResultPath": str(aggregate_path),
        "latestExportPath": str(export_json_path),
        "perFileResultsDir": str(results_dir),
        "config": config_payload,
        "selection": selection_payload,
        "selectedFiles": selected_files,
        "completedFiles": completed_files,
        "completedCount": len(completed_files),
        "pendingFiles": pending_files,
        "pendingCount": len(pending_files),
        "lastCompletedFile": completed_files[-1] if completed_files else None,
        "nextFile": pending_files[0] if pending_files else None,
    }


def build_aggregate_result(
    *,
    aggregate_path: Path,
    manifest_path: Path,
    results_dir: Path,
    dataset_filter: str,
    max_files_per_scale: int,
    manual_capacity_k: Optional[int],
    optimize_k: bool,
    optimize_goal: str,
    optimize_trials: int,
    seed: int,
    synthetic_target_per_scale: int,
    selection_payload: Dict[str, Any],
    completed_artifacts: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    graph_rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for artifact in completed_artifacts:
        response = artifact.get("response") or {}
        graph_analysis = response.get("graphAnalysis") or {}
        rows = graph_analysis.get("graphs") or []
        if rows:
            graph_rows.extend(rows)
        file_errors = graph_analysis.get("errors") or []
        if isinstance(file_errors, list):
            errors.extend(file_errors)

    graph_analysis = {
        "datasetDir": selection_payload["datasetDir"],
        "requestedFiles": list(selection_payload["selectedFiles"]),
        "filters": {
            "filenameContains": dataset_filter or None,
            "maxFiles": selection_payload["analysisMaxFiles"],
            "ratios": list(selection_payload["selectedRatios"]),
            "optimizeK": bool(optimize_k),
            "optimizeGoal": optimize_goal if optimize_k else None,
            "optimizeMaxTrials": int(optimize_trials) if optimize_k else None,
        },
        "discoveredRatios": [],
        "ratioCounts": {},
        "capacityByScale": dict(DEFAULT_CAPACITY_BY_SCALE),
        "scaleConfig": {
            "small": list(DEFAULT_SMALL_SCALES),
            "medium": list(DEFAULT_MEDIUM_SCALES),
            "large": list(DEFAULT_LARGE_SCALES),
        },
        "methods": list(DEFAULT_METHODS),
        "graphCount": len(graph_rows),
        "errorCount": len(errors),
        "graphs": graph_rows,
        "errors": errors,
        "summary": {},
    }
    update_graph_analysis_summary(graph_analysis)
    preset_scale_tests = PresetScaleTestAnalyzer().build(graph_rows)

    return {
        "meta": {
            "datasetDir": selection_payload["datasetDir"],
            "methods": list(DEFAULT_METHODS),
            "capacityK": manual_capacity_k,
            "optimizeK": optimize_k,
            "optimizeGoal": optimize_goal,
            "optimizeMaxTrials": optimize_trials,
            "filenameContains": dataset_filter or None,
            "ratios": list(selection_payload["selectedRatios"]),
            "targetScales": ["large"],
            "smallScales": list(DEFAULT_SMALL_SCALES),
            "mediumScales": list(DEFAULT_MEDIUM_SCALES),
            "largeScales": list(DEFAULT_LARGE_SCALES),
            "capacityByScale": dict(DEFAULT_CAPACITY_BY_SCALE),
            "maxFilesPerScale": max_files_per_scale,
            "selectionMode": "grouped-by-n-m-include-all-s",
            "presetExactPolicy": {
                "enabled": False,
                "reason": "includeExact flag disabled for this run",
            },
            "syntheticEnabled": False,
            "syntheticTargetPerScale": synthetic_target_per_scale,
            "syntheticGeneratedCount": 0,
            "graphCount": graph_analysis["graphCount"],
            "errorCount": graph_analysis["errorCount"],
            "savedResultPath": str(aggregate_path),
            "progressManifestPath": str(manifest_path),
            "perFileResultsDir": str(results_dir),
            "completedFileCount": len(completed_artifacts),
            "seed": seed,
        },
        "selection": {
            "candidateCount": selection_payload["candidateCount"],
            "selectedCount": len(selection_payload["selectedFiles"]),
            "selectedPairCount": selection_payload["selectedPairCount"],
            "totalAnalyzedGraphs": graph_analysis["graphCount"],
            "targetScales": ["large"],
            "small": {
                "requestedNodeCounts": list(DEFAULT_SMALL_SCALES),
                "selectedFiles": [],
                "pairCoverage": [],
                "syntheticFiles": [],
            },
            "medium": {
                "requestedNodeCounts": list(DEFAULT_MEDIUM_SCALES),
                "selectedFiles": [],
                "pairCoverage": [],
                "syntheticFiles": [],
            },
            "large": {
                "requestedNodeCounts": list(DEFAULT_LARGE_SCALES),
                "selectedFiles": list(selection_payload["selectedFiles"]),
                "pairCoverage": list(selection_payload["pairCoverage"]),
                "syntheticFiles": [],
            },
            "synthetic": {
                "enabled": False,
                "targetPerScale": synthetic_target_per_scale,
                "generatedCount": 0,
            },
        },
        "graphAnalysis": graph_analysis,
        "presetScaleTests": preset_scale_tests,
    }


def export_aggregate_json(aggregate: Dict[str, Any], export_json_path: Path) -> None:
    write_json_atomic(export_json_path, aggregate)


def generate_figures(aggregate: Dict[str, Any], figures_dir: Path) -> List[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(f"matplotlib is required to generate preset figures: {exc}") from exc

    figures_dir.mkdir(parents=True, exist_ok=True)
    scale_bucket = (
        ((aggregate.get("presetScaleTests") or {}).get("scaleBuckets") or {}).get("large") or {}
    )
    if not isinstance(scale_bucket, dict) or not scale_bucket:
        return []

    generated_paths: List[str] = []
    output_template = figures_dir / "large_{name}.png"
    no_data_sentinel = float("nan")
    chart_exclude_keys = {"graphCount"}

    def normalized_rows(rows: Sequence[Dict[str, Any]], x_key: str) -> List[Dict[str, Any]]:
        data = [row for row in rows if row.get(x_key) is not None]
        return sorted(data, key=lambda item: item.get(x_key))

    def extract_methods(rows: Sequence[Dict[str, Any]], x_key: str) -> List[str]:
        methods = set()
        for row in rows:
            for key in row.keys():
                if key in chart_exclude_keys or key == x_key:
                    continue
                methods.add(key)
        return sorted(methods)

    def to_float(value: Any) -> float:
        try:
            if value is None:
                return no_data_sentinel
            return float(value)
        except (TypeError, ValueError):
            return no_data_sentinel

    def plot_method_chart(
        rows: Sequence[Dict[str, Any]],
        *,
        x_key: str,
        x_label: str,
        title: str,
        y_label: str,
        name: str,
    ) -> None:
        data = normalized_rows(rows, x_key)
        if not data:
            return
        methods = extract_methods(data, x_key)
        plotted = False
        x_values = [row.get(x_key) for row in data]
        fig, ax = plt.subplots(figsize=(8, 5))
        for method in methods:
            y_values = [to_float(row.get(method)) for row in data]
            if all(math.isnan(value) for value in y_values):
                continue
            ax.plot(x_values, y_values, marker="o", linewidth=2, label=method)
            plotted = True
        if not plotted:
            plt.close(fig)
            return
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend()
        fig.tight_layout()
        output_path = Path(str(output_template).format(name=name))
        fig.savefig(output_path, dpi=180)
        plt.close(fig)
        generated_paths.append(str(output_path))

    def plot_capacity_chart(
        rows: Sequence[Dict[str, Any]],
        *,
        x_key: str,
        x_label: str,
        title: str,
        name: str,
    ) -> None:
        data = normalized_rows(rows, x_key)
        if not data:
            return
        x_values = [row.get(x_key) for row in data]
        avg_values = [to_float(row.get("avgCapacityK")) for row in data]
        if all(math.isnan(value) for value in avg_values):
            return
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(x_values, avg_values, marker="o", linewidth=2.2, color="#d97706", label="Avg K")
        min_values = [to_float(row.get("minCapacityK")) for row in data]
        max_values = [to_float(row.get("maxCapacityK")) for row in data]
        if all(math.isfinite(val) for val in min_values + max_values):
            ax.fill_between(
                x_values,
                min_values,
                max_values,
                color="#fcd34d",
                alpha=0.25,
                label="Min/Max Range",
            )
            ax.plot(x_values, min_values, linestyle="--", color="#a16207", linewidth=1)
            ax.plot(x_values, max_values, linestyle="--", color="#a16207", linewidth=1)
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel("Capacity K")
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend()
        fig.tight_layout()
        output_path = Path(str(output_template).format(name=name))
        fig.savefig(output_path, dpi=180)
        plt.close(fig)
        generated_paths.append(str(output_path))

    plot_method_chart(
        scale_bucket.get("nodeWeightChart") or [],
        x_key="nodeCount",
        x_label="Node Count",
        title="Average Weight vs Node Count",
        y_label="Weight",
        name="node_weight",
    )
    plot_method_chart(
        scale_bucket.get("nodeCoverSizeChart") or [],
        x_key="nodeCount",
        x_label="Node Count",
        title="Average Cover Size vs Node Count",
        y_label="Cover Size",
        name="node_cover",
    )
    plot_capacity_chart(
        scale_bucket.get("nodeKChart") or [],
        x_key="nodeCount",
        x_label="Node Count",
        title="Capacity K vs Node Count",
        name="node_k",
    )
    plot_method_chart(
        scale_bucket.get("ratioWeightChart") or [],
        x_key="connectivityRatio",
        x_label="Connectivity Ratio (m/n)",
        title="Average Weight vs Connectivity Ratio",
        y_label="Weight",
        name="ratio_weight",
    )
    plot_method_chart(
        scale_bucket.get("ratioCoverSizeChart") or [],
        x_key="connectivityRatio",
        x_label="Connectivity Ratio (m/n)",
        title="Average Cover Size vs Connectivity Ratio",
        y_label="Cover Size",
        name="ratio_cover",
    )
    plot_capacity_chart(
        scale_bucket.get("ratioKChart") or [],
        x_key="connectivityRatio",
        x_label="Connectivity Ratio (m/n)",
        title="Capacity K vs Connectivity Ratio",
        name="ratio_k",
    )

    return generated_paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Runs the Dagdeviren preset scale tests for the large bucket one file at a time, "
            "saving per-file JSON artifacts and resuming automatically from completed files."
        )
    )
    parser.add_argument(
        "-o",
        dest="output_dir",
        default="experiments",
        help="Directory for experiment artifacts (default: experiments)",
    )
    parser.add_argument(
        "-f",
        dest="dataset_filter",
        default="",
        help="Optional filename filter passed to the backend selection logic",
    )
    parser.add_argument(
        "-s",
        dest="backend_service",
        default="backend",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    output_dir = (REPO_ROOT / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    dataset_filter = args.dataset_filter.strip()
    max_files_per_scale = parse_int_env("MAX_FILES_PER_SCALE", 400)
    manual_capacity_k = parse_optional_int_env("MANUAL_CAPACITY_K", None)
    optimize_k = os.getenv("OPTIMIZE_K", "true").strip().lower() not in {"0", "false", "no", "off"}
    optimize_goal = os.getenv("OPTIMIZE_GOAL", "best-weight").strip() or "best-weight"
    optimize_trials = parse_int_env("OPTIMIZE_TRIALS", 14)
    pop_size = 100
    generations = 100
    seed = parse_int_env("SEED", 42)
    dataset_dir = DEFAULT_DATASET_DIR

    log("Using local Python modules for per-file runs")

    output_dir.mkdir(parents=True, exist_ok=True)
    log(f"Artifacts will be written to {output_dir}")

    selection_payload = build_selection_payload(
        dataset_dir=dataset_dir,
        dataset_filter=dataset_filter,
        max_files_per_scale=max_files_per_scale,
    )
    synthetic_target_per_scale = max(
        len(DEFAULT_LARGE_SCALES),
        len(selection_payload["selectedRatios"]),
    )

    run_key = stable_hash(
        {
            "config": {
                "targetScale": "large",
                "datasetFilter": dataset_filter or None,
                "datasetDir": str(dataset_dir),
                "maxFilesPerScale": max_files_per_scale,
                "methods": list(DEFAULT_METHODS),
                "capacityK": manual_capacity_k,
                "optimizeK": optimize_k,
                "optimizeGoal": optimize_goal,
                "optimizeMaxTrials": optimize_trials,
                "ratios": list(selection_payload["selectedRatios"]),
                "capacityByScale": dict(DEFAULT_CAPACITY_BY_SCALE),
                "includeExact": False,
                "fillMissingWithSynthetic": False,
                "syntheticTargetPerScale": synthetic_target_per_scale,
                "popSize": pop_size,
                "generations": generations,
                "seed": seed,
            },
            "selectedFiles": selection_payload["selectedFiles"],
        }
    )
    config_payload = {
        "targetScale": "large",
        "datasetFilter": dataset_filter or None,
        "datasetDir": str(dataset_dir),
        "maxFilesPerScale": max_files_per_scale,
        "methods": list(DEFAULT_METHODS),
        "capacityK": manual_capacity_k,
        "optimizeK": optimize_k,
        "optimizeGoal": optimize_goal,
        "optimizeMaxTrials": optimize_trials,
        "ratios": list(selection_payload["selectedRatios"]),
        "capacityByScale": dict(DEFAULT_CAPACITY_BY_SCALE),
        "includeExact": False,
        "fillMissingWithSynthetic": False,
        "syntheticTargetPerScale": synthetic_target_per_scale,
        "popSize": pop_size,
        "generations": generations,
        "seed": seed,
    }
    run_dir = output_dir / f"large_resume_{run_key}"
    results_dir = run_dir / "files"
    figures_dir = run_dir / "figures"
    manifest_path = run_dir / "manifest.json"
    aggregate_path = run_dir / "aggregate.json"
    export_json_path = output_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_large_preset.json"

    log(f"Run directory: {run_dir}")
    log(
        "Selected "
        f"{len(selection_payload['selectedFiles'])} large preset files "
        f"across {selection_payload['selectedPairCount']} (n,m) pairs"
    )

    existing_manifest = load_json(manifest_path) or {}
    created_at = str(existing_manifest.get("createdAt") or utc_now_iso())
    completed_artifacts = collect_completed_artifacts(
        selected_files=selection_payload["selectedFiles"],
        results_dir=results_dir,
    )

    write_json_atomic(
        manifest_path,
        build_manifest(
            run_key=run_key,
            run_dir=run_dir,
            export_json_path=export_json_path,
            results_dir=results_dir,
            aggregate_path=aggregate_path,
            config_payload=config_payload,
            selection_payload=selection_payload,
            completed_artifacts=completed_artifacts,
            status="running",
            created_at=created_at,
        ),
    )

    if completed_artifacts:
        log(
            f"Found {len(completed_artifacts)} completed file artifacts; "
            "resuming from the first unfinished file."
        )

    for index, file_name in enumerate(selection_payload["selectedFiles"]):
        artifact_path = file_result_path(results_dir, index, file_name)
        if load_result_artifact(artifact_path, file_name) is not None:
            continue

        log(f"Running file {index + 1}/{len(selection_payload['selectedFiles'])}: {file_name}")
        single_payload = build_single_file_payload(
            file_name=file_name,
            dataset_filter=dataset_filter,
            max_files_per_scale=max_files_per_scale,
            manual_capacity_k=manual_capacity_k,
            optimize_k=optimize_k,
            optimize_goal=optimize_goal,
            optimize_trials=optimize_trials,
            pop_size=pop_size,
            generations=generations,
            seed=seed,
            selected_ratios=selection_payload["selectedRatios"],
        )
        response = run_single_file_analysis(
            payload=single_payload,
        )
        artifact_payload = {
            "version": 1,
            "runKey": run_key,
            "targetScale": "large",
            "index": index,
            "file": file_name,
            "completedAt": utc_now_iso(),
            "request": single_payload,
            "response": response,
        }
        write_json_atomic(artifact_path, artifact_payload)

        completed_artifacts = collect_completed_artifacts(
            selected_files=selection_payload["selectedFiles"],
            results_dir=results_dir,
        )
        partial_aggregate = build_aggregate_result(
            aggregate_path=aggregate_path,
            manifest_path=manifest_path,
            results_dir=results_dir,
            dataset_filter=dataset_filter,
            max_files_per_scale=max_files_per_scale,
            manual_capacity_k=manual_capacity_k,
            optimize_k=optimize_k,
            optimize_goal=optimize_goal,
            optimize_trials=optimize_trials,
            seed=seed,
            synthetic_target_per_scale=synthetic_target_per_scale,
            selection_payload=selection_payload,
            completed_artifacts=completed_artifacts,
        )
        write_json_atomic(aggregate_path, partial_aggregate)
        write_json_atomic(
            manifest_path,
            build_manifest(
                run_key=run_key,
                run_dir=run_dir,
                export_json_path=export_json_path,
                results_dir=results_dir,
                aggregate_path=aggregate_path,
                config_payload=config_payload,
                selection_payload=selection_payload,
                completed_artifacts=completed_artifacts,
                status="running",
                created_at=created_at,
            ),
        )

    completed_artifacts = collect_completed_artifacts(
        selected_files=selection_payload["selectedFiles"],
        results_dir=results_dir,
    )
    aggregate = build_aggregate_result(
        aggregate_path=aggregate_path,
        manifest_path=manifest_path,
        results_dir=results_dir,
        dataset_filter=dataset_filter,
        max_files_per_scale=max_files_per_scale,
        manual_capacity_k=manual_capacity_k,
        optimize_k=optimize_k,
        optimize_goal=optimize_goal,
        optimize_trials=optimize_trials,
        seed=seed,
        synthetic_target_per_scale=synthetic_target_per_scale,
        selection_payload=selection_payload,
        completed_artifacts=completed_artifacts,
    )
    write_json_atomic(aggregate_path, aggregate)
    export_aggregate_json(aggregate, export_json_path)
    figure_paths = generate_figures(aggregate, figures_dir)

    write_json_atomic(
        manifest_path,
        build_manifest(
            run_key=run_key,
            run_dir=run_dir,
            export_json_path=export_json_path,
            results_dir=results_dir,
            aggregate_path=aggregate_path,
            config_payload=config_payload,
            selection_payload=selection_payload,
            completed_artifacts=completed_artifacts,
            status="completed",
            created_at=created_at,
        ),
    )

    log(f"Saved aggregate preset JSON to {aggregate_path}")
    log(f"Exported timestamped preset JSON to {export_json_path}")
    if figure_paths:
        log("Generated figures:")
        for fig in figure_paths:
            print(f"  {fig}")
    log(f"Per-file artifacts: {results_dir}")
    log("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
