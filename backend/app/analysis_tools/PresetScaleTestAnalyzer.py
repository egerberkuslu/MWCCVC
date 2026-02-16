from __future__ import annotations

import math
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

SCALE_BUCKETS = ("small", "medium", "large")


def _method_metrics(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {
            "attempted": 0,
            "validRuns": 0,
            "validRate": 0.0,
            "avgWeight": None,
            "avgCoverSize": None,
            "avgTimeMs": None,
        }

    attempted = len(items)
    valid = [item for item in items if bool((item.get("verification") or {}).get("isValid"))]

    times = [float(item.get("time", float("nan"))) for item in items]
    valid_times = [value for value in times if math.isfinite(value)]

    weights = [
        float((item.get("verification") or {}).get("totalWeight", float("nan")))
        for item in valid
    ]
    valid_weights = [value for value in weights if math.isfinite(value)]

    cover_sizes = [
        float((item.get("verification") or {}).get("coverSize", float("nan")))
        for item in valid
    ]
    valid_cover_sizes = [value for value in cover_sizes if math.isfinite(value)]

    return {
        "attempted": attempted,
        "validRuns": len(valid),
        "validRate": round(float(len(valid) / attempted), 6) if attempted else 0.0,
        "avgWeight": round(float(mean(valid_weights)), 6) if valid_weights else None,
        "avgCoverSize": round(float(mean(valid_cover_sizes)), 6) if valid_cover_sizes else None,
        "avgTimeMs": round(float(mean(valid_times)), 6) if valid_times else None,
    }


def _sort_group_items(items: List[Dict[str, Any]], key_name: str) -> List[Dict[str, Any]]:
    def _sort_key(item: Dict[str, Any]) -> Tuple[int, float | str]:
        value = item.get(key_name)
        if isinstance(value, (int, float)):
            return (0, float(value))
        return (1, str(value))

    return sorted(items, key=_sort_key)


def _group_rows(
    graph_rows: List[Dict[str, Any]],
    *,
    key_name: str,
    key_builder,
) -> List[Dict[str, Any]]:
    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for row in graph_rows:
        group_key = key_builder(row)
        if group_key is None:
            continue
        grouped.setdefault(group_key, []).append(row)

    rows: List[Dict[str, Any]] = []
    for group_key, bucket_rows in grouped.items():
        methods = sorted(
            {
                method
                for row in bucket_rows
                for method in (row.get("results") or {}).keys()
            }
        )
        method_summary: Dict[str, Any] = {}
        for method in methods:
            method_items: List[Dict[str, Any]] = []
            for row in bucket_rows:
                row_results = row.get("results") or {}
                if method in row_results:
                    method_items.append(row_results.get(method) or {})
            method_summary[method] = _method_metrics(method_items)

        capacity_values: List[float] = []
        for row in bucket_rows:
            try:
                value = float(row.get("capacityK", float("nan")))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                capacity_values.append(value)

        rows.append(
            {
                key_name: group_key,
                "graphCount": len(bucket_rows),
                "avgCapacityK": round(float(mean(capacity_values)), 6) if capacity_values else None,
                "minCapacityK": int(min(capacity_values)) if capacity_values else None,
                "maxCapacityK": int(max(capacity_values)) if capacity_values else None,
                "methods": method_summary,
            }
        )

    return _sort_group_items(rows, key_name)


def _build_chart(groups: List[Dict[str, Any]], x_key: str, metric_key: str) -> List[Dict[str, Any]]:
    methods = sorted(
        {
            method
            for group in groups
            for method in (group.get("methods") or {}).keys()
        }
    )
    chart_rows: List[Dict[str, Any]] = []
    for group in groups:
        row: Dict[str, Any] = {
            x_key: group.get(x_key),
            "graphCount": group.get("graphCount", 0),
        }
        for method in methods:
            row[method] = (group.get("methods") or {}).get(method, {}).get(metric_key)
        chart_rows.append(row)
    return chart_rows


def _build_capacity_chart(groups: List[Dict[str, Any]], x_key: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for group in groups:
        rows.append(
            {
                x_key: group.get(x_key),
                "graphCount": group.get("graphCount", 0),
                "avgCapacityK": group.get("avgCapacityK"),
                "minCapacityK": group.get("minCapacityK"),
                "maxCapacityK": group.get("maxCapacityK"),
            }
        )
    return rows


def _bucket_method_summary(graph_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    methods = sorted(
        {
            method
            for row in graph_rows
            for method in (row.get("results") or {}).keys()
        }
    )
    summary: Dict[str, Any] = {}
    for method in methods:
        items: List[Dict[str, Any]] = []
        for row in graph_rows:
            row_results = row.get("results") or {}
            if method in row_results:
                items.append(row_results.get(method) or {})
        summary[method] = _method_metrics(items)
    return summary


class PresetScaleTestAnalyzer:
    def build(self, graph_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        scale_buckets: Dict[str, Any] = {}
        for bucket in SCALE_BUCKETS:
            bucket_rows = [row for row in graph_rows if row.get("scaleBucket") == bucket]
            by_node_count = _group_rows(
                bucket_rows,
                key_name="nodeCount",
                key_builder=lambda row: int((row.get("stats") or {}).get("n", 0)) or None,
            )
            by_connectivity_ratio = _group_rows(
                bucket_rows,
                key_name="connectivityRatio",
                key_builder=lambda row: (
                    round(float(row.get("ratio")), 6)
                    if row.get("ratio") is not None
                    else None
                ),
            )
            scale_buckets[bucket] = {
                "graphCount": len(bucket_rows),
                "methodSummary": _bucket_method_summary(bucket_rows),
                "byNodeCount": by_node_count,
                "byConnectivityRatio": by_connectivity_ratio,
                "nodeWeightChart": _build_chart(by_node_count, "nodeCount", "avgWeight"),
                "nodeCoverSizeChart": _build_chart(by_node_count, "nodeCount", "avgCoverSize"),
                "nodeKChart": _build_capacity_chart(by_node_count, "nodeCount"),
                "ratioWeightChart": _build_chart(
                    by_connectivity_ratio, "connectivityRatio", "avgWeight"
                ),
                "ratioCoverSizeChart": _build_chart(
                    by_connectivity_ratio, "connectivityRatio", "avgCoverSize"
                ),
                "ratioKChart": _build_capacity_chart(by_connectivity_ratio, "connectivityRatio"),
            }

        return {"scaleBuckets": scale_buckets}
