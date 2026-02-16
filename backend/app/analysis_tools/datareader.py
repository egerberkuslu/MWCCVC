from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_SCALE_PATTERN = re.compile(r"n(?P<n>\d+)_m(?P<m>\d+)_s(?P<s>\d+)\.txt$", re.IGNORECASE)
_NUMERIC_TOKEN_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def parse_scale_from_filename(name: str) -> Dict[str, Optional[int]]:
    match = _SCALE_PATTERN.search(name)
    if not match:
        return {"n": None, "m": None, "s": None}
    return {
        "n": int(match.group("n")),
        "m": int(match.group("m")),
        "s": int(match.group("s")),
    }


def _parse_integral_token(token: str) -> Optional[int]:
    value = str(token).strip()
    if not value or not _NUMERIC_TOKEN_PATTERN.fullmatch(value):
        return None
    parsed = float(value)
    if not parsed.is_integer():
        return None
    return int(parsed)


def _parse_header_counts(line: str) -> Optional[Tuple[int, int]]:
    parts = line.split()
    if len(parts) < 2:
        return None
    declared_n = _parse_integral_token(parts[0])
    declared_m = _parse_integral_token(parts[1])
    if declared_n is None or declared_m is None:
        return None
    return declared_n, declared_m


def normalize_edges(
    vertex_data: Sequence[Dict[str, Any]],
    raw_edges: Sequence[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    node_ids = {int(vertex["id"]) for vertex in vertex_data}
    seen = set()
    normalized: List[Tuple[int, int]] = []
    for raw_u, raw_v in raw_edges:
        u = int(raw_u)
        v = int(raw_v)
        if u == v or u not in node_ids or v not in node_ids:
            continue
        edge = (u, v) if u < v else (v, u)
        if edge in seen:
            continue
        seen.add(edge)
        normalized.append(edge)
    return normalized


def read_graph_from_lines(lines: Sequence[str], source_name: str) -> Dict[str, Any]:
    filtered = [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not filtered:
        raise ValueError(f"{source_name}: file is empty.")

    source_basename = Path(source_name).name
    scale = parse_scale_from_filename(source_basename)
    header_counts = _parse_header_counts(filtered[0])

    if header_counts is not None:
        declared_n, declared_m = header_counts
        body_lines = filtered[1:]
    elif scale.get("n") is not None and scale.get("m") is not None:
        declared_n = int(scale["n"])
        declared_m = int(scale["m"])
        body_lines = filtered
    else:
        raise ValueError(
            f"{source_name}: first line must include node_count/edge_count or filename must match n*_m*_s*.txt."
        )

    if declared_n <= 0:
        raise ValueError(f"{source_name}: node_count must be positive.")
    if declared_m < 0:
        raise ValueError(f"{source_name}: edge_count cannot be negative.")

    if len(body_lines) < declared_n:
        raise ValueError(
            f"{source_name}: expected at least {declared_n} vertex lines, got {len(body_lines)}."
        )

    vertices: List[Dict[str, Any]] = []
    for index in range(declared_n):
        line = body_lines[index]
        parts = line.split()
        if len(parts) < 2:
            raise ValueError(f"{source_name}: malformed vertex line {index + 1}: '{line}'.")
        node_id = int(float(parts[0]))
        weight = float(parts[1])
        vertices.append({"id": node_id, "weight": weight})

    raw_edges: List[Tuple[int, int]] = []
    edge_lines = body_lines[declared_n:]
    for index, line in enumerate(edge_lines, start=declared_n + 1):
        parts = line.split()
        if len(parts) < 2:
            continue
        raw_edges.append((int(float(parts[0])), int(float(parts[1]))))
        if len(raw_edges) >= declared_m:
            break

    normalized_edges = normalize_edges(vertices, raw_edges)
    return {
        "name": source_basename,
        "vertices": vertices,
        "edges": normalized_edges,
        "declaredNodeCount": declared_n,
        "declaredEdgeCount": declared_m,
        "parsedNodeCount": len(vertices),
        "parsedEdgeCount": len(normalized_edges),
        "scale": scale,
    }


def read_graph_from_file(path: Path) -> Dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8")
    return read_graph_from_lines(raw_text.splitlines(), source_name=path.name)


def list_dataset_files(
    dataset_dir: Path,
    *,
    files: Optional[Sequence[str]] = None,
    filename_contains: Optional[str] = None,
    max_files: int = 50,
) -> List[Path]:
    max_files = max(1, int(max_files))

    if files is not None:
        selected: List[Path] = []
        for name in files:
            filename = Path(str(name)).name
            path = dataset_dir / filename
            if path.is_file() and path.suffix.lower() == ".txt":
                selected.append(path)
        return sorted(selected, key=lambda p: p.name)[:max_files]

    filter_token = str(filename_contains or "").strip().lower()
    candidates = sorted(dataset_dir.glob("*.txt"), key=lambda p: p.name)
    if filter_token:
        candidates = [path for path in candidates if filter_token in path.name.lower()]
    return candidates[:max_files]
