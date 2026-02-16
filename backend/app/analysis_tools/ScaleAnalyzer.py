from __future__ import annotations

import math
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple


def _method_aggregate(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows_list = list(rows)
    attempted = len(rows_list)
    valid_rows = [row for row in rows_list if bool((row.get("verification") or {}).get("isValid"))]
    times = [float(row.get("time", float("nan"))) for row in rows_list]
    valid_times = [value for value in times if math.isfinite(value)]

    weights = [
        float((row.get("verification") or {}).get("totalWeight", float("nan")))
        for row in valid_rows
    ]
    weights = [value for value in weights if math.isfinite(value)]

    cover_sizes = [
        float((row.get("verification") or {}).get("coverSize", float("nan")))
        for row in valid_rows
    ]
    cover_sizes = [value for value in cover_sizes if math.isfinite(value)]

    return {
        "attempted": attempted,
        "validRuns": len(valid_rows),
        "validRate": round(float(len(valid_rows) / attempted), 6) if attempted else 0.0,
        "avgTimeMs": round(float(mean(valid_times)), 6) if valid_times else None,
        "avgWeight": round(float(mean(weights)), 6) if weights else None,
        "avgCoverSize": round(float(mean(cover_sizes)), 6) if cover_sizes else None,
    }


def _group_by(
    graph_rows: List[Dict[str, Any]],
    *,
    key_name: str,
    key_builder,
) -> List[Dict[str, Any]]:
    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for row in graph_rows:
        group_key = key_builder(row)
        grouped.setdefault(group_key, []).append(row)

    result: List[Dict[str, Any]] = []
    for group_key, rows in grouped.items():
        methods = sorted({method for row in rows for method in (row.get("results") or {}).keys()})
        method_summary: Dict[str, Any] = {}
        for method in methods:
            method_rows = []
            for row in rows:
                row_results = row.get("results") or {}
                if method in row_results:
                    method_rows.append(row_results.get(method) or {})
            method_summary[method] = _method_aggregate(method_rows)

        densities = [float((row.get("stats") or {}).get("density", 0.0)) for row in rows]
        capacity_values: List[float] = []
        for row in rows:
            try:
                value = float(row.get("capacityK", float("nan")))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                capacity_values.append(value)
        result.append(
            {
                key_name: group_key,
                "graphCount": len(rows),
                "avgDensity": round(float(mean(densities)), 6) if densities else 0.0,
                "avgCapacityK": round(float(mean(capacity_values)), 6) if capacity_values else None,
                "minCapacityK": int(min(capacity_values)) if capacity_values else None,
                "maxCapacityK": int(max(capacity_values)) if capacity_values else None,
                "methods": method_summary,
            }
        )

    def _sort_key(item: Dict[str, Any]) -> Tuple[int, str]:
        value = item.get(key_name)
        if isinstance(value, (int, float)):
            return (0, str(int(value)))
        return (1, str(value))

    return sorted(result, key=_sort_key)


class ScaleAnalyzer:
    def analyze(self, graph_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_node_count = _group_by(
            graph_rows,
            key_name="nodeCount",
            key_builder=lambda row: int((row.get("stats") or {}).get("n", 0)),
        )
        by_edge_count = _group_by(
            graph_rows,
            key_name="edgeCount",
            key_builder=lambda row: int((row.get("stats") or {}).get("m", 0)),
        )
        by_scale_key = _group_by(
            graph_rows,
            key_name="scale",
            key_builder=lambda row: (
                f"n{int((row.get('scale') or {}).get('n') or 0)}_m"
                f"{int((row.get('scale') or {}).get('m') or 0)}"
            ),
        )
        return {
            "byNodeCount": by_node_count,
            "byEdgeCount": by_edge_count,
            "byScale": by_scale_key,
        }
