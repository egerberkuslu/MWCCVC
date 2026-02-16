from __future__ import annotations

import math
from statistics import mean
from typing import Any, Dict, List


def _method_metrics(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {
            "attempted": 0,
            "validRuns": 0,
            "validRate": 0.0,
            "avgWeight": None,
            "avgTimeMs": None,
            "avgCoverRatio": None,
        }

    attempted = len(items)
    valid = [item for item in items if bool((item.get("verification") or {}).get("isValid"))]

    times = [float(item.get("time", float("nan"))) for item in items]
    times = [value for value in times if math.isfinite(value)]
    weights = [
        float((item.get("verification") or {}).get("totalWeight", float("nan")))
        for item in valid
    ]
    weights = [value for value in weights if math.isfinite(value)]
    cover_ratios = []
    for item in valid:
        verification = item.get("verification") or {}
        cover_size = float(verification.get("coverSize", float("nan")))
        node_count = float(verification.get("nodeCount", float("nan")))
        if math.isfinite(cover_size) and math.isfinite(node_count) and node_count > 0:
            cover_ratios.append(cover_size / node_count)

    return {
        "attempted": attempted,
        "validRuns": len(valid),
        "validRate": round(float(len(valid) / attempted), 6) if attempted else 0.0,
        "avgWeight": round(float(mean(weights)), 6) if weights else None,
        "avgTimeMs": round(float(mean(times)), 6) if times else None,
        "avgCoverRatio": round(float(mean(cover_ratios)), 6) if cover_ratios else None,
    }


class ConnectivityRatioVisualizer:
    def build(
        self,
        graph_rows: List[Dict[str, Any]],
        *,
        precision: int = 2,
    ) -> Dict[str, Any]:
        grouped: Dict[float, List[Dict[str, Any]]] = {}
        for row in graph_rows:
            density = float((row.get("stats") or {}).get("density", 0.0))
            ratio_key = round(density, int(precision))
            grouped.setdefault(ratio_key, []).append(row)

        bins: List[Dict[str, Any]] = []
        weight_chart: List[Dict[str, Any]] = []
        time_chart: List[Dict[str, Any]] = []
        valid_rate_chart: List[Dict[str, Any]] = []
        k_chart: List[Dict[str, Any]] = []

        for ratio in sorted(grouped):
            rows = grouped[ratio]
            method_names = sorted({method for row in rows for method in (row.get("results") or {}).keys()})
            methods_payload: Dict[str, Any] = {}
            weight_row: Dict[str, Any] = {"connectivityRatio": ratio, "graphCount": len(rows)}
            time_row: Dict[str, Any] = {"connectivityRatio": ratio, "graphCount": len(rows)}
            valid_row: Dict[str, Any] = {"connectivityRatio": ratio, "graphCount": len(rows)}
            capacity_values: List[float] = []
            for row in rows:
                try:
                    value = float(row.get("capacityK", float("nan")))
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    capacity_values.append(value)

            for method in method_names:
                method_items = []
                for row in rows:
                    row_results = row.get("results") or {}
                    if method in row_results:
                        method_items.append(row_results.get(method) or {})

                metrics = _method_metrics(method_items)
                methods_payload[method] = metrics
                if metrics["avgWeight"] is not None:
                    weight_row[method] = metrics["avgWeight"]
                if metrics["avgTimeMs"] is not None:
                    time_row[method] = metrics["avgTimeMs"]
                valid_row[method] = metrics["validRate"]

            bins.append(
                {
                    "connectivityRatio": ratio,
                    "graphCount": len(rows),
                    "methods": methods_payload,
                }
            )
            weight_chart.append(weight_row)
            time_chart.append(time_row)
            valid_rate_chart.append(valid_row)
            k_chart.append(
                {
                    "connectivityRatio": ratio,
                    "graphCount": len(rows),
                    "avgCapacityK": round(float(mean(capacity_values)), 6) if capacity_values else None,
                    "minCapacityK": int(min(capacity_values)) if capacity_values else None,
                    "maxCapacityK": int(max(capacity_values)) if capacity_values else None,
                }
            )

        return {
            "ratioKey": "density",
            "precision": precision,
            "bins": bins,
            "weightChart": weight_chart,
            "timeChart": time_chart,
            "validRateChart": valid_rate_chart,
            "kChart": k_chart,
        }
