from __future__ import annotations

from typing import Any, Dict, List


def _collect_method_names(groups: List[Dict[str, Any]]) -> List[str]:
    methods = set()
    for group in groups:
        methods.update((group.get("methods") or {}).keys())
    return sorted(methods)


def _build_chart(groups: List[Dict[str, Any]], x_key: str, metric_key: str) -> List[Dict[str, Any]]:
    method_names = _collect_method_names(groups)
    chart_rows: List[Dict[str, Any]] = []
    for group in groups:
        row: Dict[str, Any] = {
            x_key: group.get(x_key),
            "graphCount": group.get("graphCount", 0),
            "avgDensity": group.get("avgDensity", 0.0),
        }
        for method in method_names:
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


class ScaleVisualizer:
    def build(self, scale_analysis: Dict[str, Any]) -> Dict[str, Any]:
        by_node_count = list(scale_analysis.get("byNodeCount") or [])
        by_edge_count = list(scale_analysis.get("byEdgeCount") or [])
        return {
            "nodeWeightChart": _build_chart(by_node_count, "nodeCount", "avgWeight"),
            "nodeTimeChart": _build_chart(by_node_count, "nodeCount", "avgTimeMs"),
            "nodeValidRateChart": _build_chart(by_node_count, "nodeCount", "validRate"),
            "nodeKChart": _build_capacity_chart(by_node_count, "nodeCount"),
            "edgeWeightChart": _build_chart(by_edge_count, "edgeCount", "avgWeight"),
            "edgeTimeChart": _build_chart(by_edge_count, "edgeCount", "avgTimeMs"),
            "edgeValidRateChart": _build_chart(by_edge_count, "edgeCount", "validRate"),
            "edgeKChart": _build_capacity_chart(by_edge_count, "edgeCount"),
        }
