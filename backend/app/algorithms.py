from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
import random
import sys
import time
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple


@dataclass
class Node:
    id: int
    weight: float
    capacity: int
    remaining: int
    color: str = "WHITE"
    x: float = 0.0
    y: float = 0.0


@dataclass
class Edge:
    u: int
    v: int
    covered: bool = False
    covered_by: Optional[int] = None


@dataclass
class Graph:
    nodes: Dict[int, Node]
    edges: Dict[Tuple[int, int], Edge]
    adj: Dict[int, Set[int]]
    capacity_k: int


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size
        self.group_count = size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> bool:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return False
        if self.rank[left_root] < self.rank[right_root]:
            self.parent[left_root] = right_root
        elif self.rank[left_root] > self.rank[right_root]:
            self.parent[right_root] = left_root
        else:
            self.parent[right_root] = left_root
            self.rank[left_root] += 1
        self.group_count -= 1
        return True


def edge_key(u: int, v: int) -> Tuple[int, int]:
    return (u, v) if u < v else (v, u)


def create_graph(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
) -> Graph:
    nodes: Dict[int, Node] = {}
    edges: Dict[Tuple[int, int], Edge] = {}
    adj: Dict[int, Set[int]] = {}

    for raw_v in vertex_data:
        node_id = int(raw_v["id"])
        weight = float(raw_v["weight"])
        x = float(raw_v.get("x", 0.0) or 0.0)
        y = float(raw_v.get("y", 0.0) or 0.0)
        nodes[node_id] = Node(
            id=node_id,
            weight=weight,
            capacity=capacity_k,
            remaining=capacity_k,
            color="WHITE",
            x=x,
            y=y,
        )
        adj[node_id] = set()

    for raw_u, raw_v in edge_data:
        u = int(raw_u)
        v = int(raw_v)
        if u == v or u not in nodes or v not in nodes:
            continue
        key = edge_key(u, v)
        if key in edges:
            continue
        edges[key] = Edge(u=key[0], v=key[1], covered=False, covered_by=None)
        adj[u].add(v)
        adj[v].add(u)

    return Graph(nodes=nodes, edges=edges, adj=adj, capacity_k=capacity_k)


def reset_graph(graph: Graph) -> None:
    for node in graph.nodes.values():
        node.color = "WHITE"
        node.remaining = graph.capacity_k
    for edge in graph.edges.values():
        edge.covered = False
        edge.covered_by = None


def get_uncovered_edges(graph: Graph) -> List[Edge]:
    return [edge for edge in graph.edges.values() if not edge.covered]


def has_uncovered_edges(graph: Graph) -> bool:
    return any(not edge.covered for edge in graph.edges.values())


def uncovered_degree(graph: Graph, node_id: int, exclude_black: bool = True) -> int:
    count = 0
    for neighbor_id in graph.adj.get(node_id, set()):
        edge = graph.edges.get(edge_key(node_id, neighbor_id))
        if edge is None or edge.covered:
            continue
        if exclude_black and graph.nodes[neighbor_id].color == "BLACK":
            continue
        count += 1
    return count


def sum_uncovered_neighbor_weights(
    graph: Graph, node_id: int, allow_black: bool = False
) -> float:
    total = 0.0
    for neighbor_id in graph.adj.get(node_id, set()):
        edge = graph.edges.get(edge_key(node_id, neighbor_id))
        if edge is None or edge.covered:
            continue
        if not allow_black and graph.nodes[neighbor_id].color == "BLACK":
            continue
        total += graph.nodes[neighbor_id].weight
    return total


def get_edge_candidates(
    graph: Graph, node_id: int, allow_black: bool = False
) -> List[Tuple[int, Edge]]:
    candidates: List[Tuple[int, Edge]] = []
    for neighbor_id in graph.adj.get(node_id, set()):
        edge = graph.edges.get(edge_key(node_id, neighbor_id))
        if edge is None or edge.covered:
            continue
        if not allow_black and graph.nodes[neighbor_id].color == "BLACK":
            continue
        candidates.append((neighbor_id, edge))
    return candidates


def get_cover_components(graph: Graph, cover_set: Set[int]) -> List[Set[int]]:
    unvisited = set(cover_set)
    components: List[Set[int]] = []

    while unvisited:
        start = next(iter(unvisited))
        unvisited.remove(start)
        component = {start}
        queue: deque[int] = deque([start])

        while queue:
            current = queue.popleft()
            for neighbor_id in graph.adj.get(current, set()):
                if neighbor_id in unvisited:
                    unvisited.remove(neighbor_id)
                    component.add(neighbor_id)
                    queue.append(neighbor_id)
        components.append(component)

    return components


def is_connected_cover(graph: Graph, cover_set: Set[int]) -> bool:
    return len(get_cover_components(graph, cover_set)) <= 1


def is_vertex_cover(graph: Graph, cover_set: Set[int]) -> bool:
    return all(edge.u in cover_set or edge.v in cover_set for edge in graph.edges.values())


def _check_capacity_feasibility_raw(
    edge_data: Sequence[Tuple[int, int]],
    cover_set: Set[int],
    capacity_k: int,
) -> bool:
    if capacity_k <= 0:
        return False
    edge_count = len(edge_data)
    if edge_count == 0:
        return True
    if not cover_set:
        return False
    if len(cover_set) * capacity_k < edge_count:
        return False

    forced_usage = {node_id: 0 for node_id in cover_set}
    flexible_edges: List[Tuple[int, int]] = []

    for raw_u, raw_v in edge_data:
        u = int(raw_u)
        v = int(raw_v)
        u_in = u in cover_set
        v_in = v in cover_set
        if not u_in and not v_in:
            return False
        if u_in and v_in:
            flexible_edges.append((u, v))
        elif u_in:
            forced_usage[u] += 1
        else:
            forced_usage[v] += 1

    residual = {}
    for node_id in cover_set:
        remain = capacity_k - forced_usage[node_id]
        if remain < 0:
            return False
        residual[node_id] = remain

    if not flexible_edges:
        return True
    if sum(residual.values()) < len(flexible_edges):
        return False

    cover_nodes = [node_id for node_id, remain in residual.items() if remain > 0]
    if not cover_nodes:
        return False

    source = 0
    edge_node_start = 1
    cover_node_start = edge_node_start + len(flexible_edges)
    sink = cover_node_start + len(cover_nodes)
    network: List[List[List[int]]] = [[] for _ in range(sink + 1)]

    def add_flow_edge(frm: int, to: int, cap: int) -> None:
        forward = [to, len(network[to]), cap]
        backward = [frm, len(network[frm]), 0]
        network[frm].append(forward)
        network[to].append(backward)

    cover_index = {node_id: cover_node_start + idx for idx, node_id in enumerate(cover_nodes)}

    for idx, (u, v) in enumerate(flexible_edges):
        edge_node = edge_node_start + idx
        add_flow_edge(source, edge_node, 1)
        if u in cover_index:
            add_flow_edge(edge_node, cover_index[u], 1)
        if v in cover_index and v != u:
            add_flow_edge(edge_node, cover_index[v], 1)

    for node_id in cover_nodes:
        add_flow_edge(cover_index[node_id], sink, residual[node_id])

    def max_flow(src: int, dst: int) -> int:
        flow = 0
        n_nodes = len(network)
        inf = 10**9
        if n_nodes + 100 > sys.getrecursionlimit():
            sys.setrecursionlimit(n_nodes + 100)

        while True:
            level = [-1] * n_nodes
            queue: deque[int] = deque([src])
            level[src] = 0

            while queue:
                current = queue.popleft()
                for nxt, _rev, cap in network[current]:
                    if cap <= 0 or level[nxt] >= 0:
                        continue
                    level[nxt] = level[current] + 1
                    queue.append(nxt)

            if level[dst] < 0:
                break

            progress = [0] * n_nodes

            def dfs(current: int, pushed: int) -> int:
                if current == dst:
                    return pushed
                while progress[current] < len(network[current]):
                    edge_idx = progress[current]
                    nxt, rev, cap = network[current][edge_idx]
                    if cap > 0 and level[nxt] == level[current] + 1:
                        sent = dfs(nxt, min(pushed, cap))
                        if sent > 0:
                            network[current][edge_idx][2] -= sent
                            network[nxt][rev][2] += sent
                            return sent
                    progress[current] += 1
                return 0

            while True:
                sent = dfs(src, inf)
                if sent == 0:
                    break
                flow += sent
                if flow == len(flexible_edges):
                    return flow

        return flow

    return max_flow(source, sink) == len(flexible_edges)


def check_capacity_feasibility(graph: Graph, cover_set: Set[int]) -> bool:
    edge_data = [(edge.u, edge.v) for edge in graph.edges.values()]
    return _check_capacity_feasibility_raw(edge_data, cover_set, graph.capacity_k)


def repair_connectivity(graph: Graph, cover_set: Set[int]) -> Set[int]:
    cs = set(cover_set)
    safety = 0

    while safety < 100:
        safety += 1
        components = get_cover_components(graph, cs)
        if len(components) <= 1:
            break

        main = set(components[0])
        best_path: Optional[List[int]] = None
        best_cost = float("inf")

        for component in components[1:]:
            for target in component:
                dist: Dict[int, int] = {target: 0}
                prev: Dict[int, int] = {}
                queue: deque[int] = deque([target])
                found: Optional[int] = None

                while queue and found is None:
                    u = queue.popleft()
                    for w in graph.adj.get(u, set()):
                        if w in dist:
                            continue
                        dist[w] = dist[u] + 1
                        prev[w] = u
                        if w in main:
                            found = w
                            break
                        queue.append(w)

                if found is None:
                    continue

                path: List[int] = []
                cur = found
                cost = 0.0
                while cur != target:
                    if cur not in cs:
                        path.append(cur)
                        cost += graph.nodes[cur].weight
                    cur = prev[cur]
                if cost < best_cost:
                    best_cost = cost
                    best_path = path

        if best_path:
            cs.update(best_path)
        else:
            break

    return cs


def _reconstruct_path(previous: Dict[int, int], end_node: int) -> List[int]:
    path = [end_node]
    while end_node in previous:
        end_node = previous[end_node]
        path.append(end_node)
    path.reverse()
    return path


def _add_path_to_cover(graph: Graph, cover_set: Set[int], path: Sequence[int]) -> None:
    for node_id in path:
        node = graph.nodes[node_id]
        if node.color != "BLACK":
            node.color = "BLACK"
            cover_set.add(node_id)
        for neighbor_id in graph.adj.get(node_id, set()):
            neighbor = graph.nodes[neighbor_id]
            if neighbor.color in {"WHITE", "RED"}:
                neighbor.color = "GRAY"


def _shortest_path_between_components_capacity_aware(
    graph: Graph,
    cover_set: Set[int],
    comp_a: Set[int],
    comp_b: Set[int],
) -> Tuple[float, List[int]]:
    targets = set(comp_b)
    distances: Dict[int, float] = {}
    previous: Dict[int, int] = {}
    heap: List[Tuple[float, int]] = []

    for node_id in comp_a:
        distances[node_id] = 0.0
        heapq.heappush(heap, (0.0, node_id))

    while heap:
        cost, current = heapq.heappop(heap)
        if cost > distances.get(current, float("inf")):
            continue
        if current in targets:
            return cost, _reconstruct_path(previous, current)

        for neighbor_id in graph.adj.get(current, set()):
            neighbor = graph.nodes[neighbor_id]
            if neighbor_id not in cover_set and neighbor.remaining <= 0:
                continue
            step_cost = 0.0 if neighbor_id in cover_set else neighbor.weight
            new_cost = cost + step_cost
            if new_cost < distances.get(neighbor_id, float("inf")):
                distances[neighbor_id] = new_cost
                previous[neighbor_id] = current
                heapq.heappush(heap, (new_cost, neighbor_id))

    return float("inf"), []


def _build_bridges_capacity_aware(graph: Graph, cover_set: Set[int]) -> bool:
    components = get_cover_components(graph, cover_set)
    if len(components) <= 1:
        return False

    connections: List[Tuple[float, int, int, List[int]]] = []
    for i in range(len(components)):
        for j in range(i + 1, len(components)):
            cost, path = _shortest_path_between_components_capacity_aware(
                graph,
                cover_set,
                components[i],
                components[j],
            )
            if path:
                connections.append((cost, i, j, path))

    if not connections:
        return False

    connections.sort(key=lambda item: item[0])
    union_find = _UnionFind(len(components))
    added = False

    for _cost, i, j, path in connections:
        if union_find.union(i, j):
            _add_path_to_cover(graph, cover_set, path)
            added = True
            if union_find.group_count == 1:
                break

    return added


def _repair_connectivity_capacity_aware(graph: Graph, cover_set: Set[int]) -> Set[int]:
    cs = set(cover_set)
    while len(get_cover_components(graph, cs)) > 1:
        if not _build_bridges_capacity_aware(graph, cs):
            break
    return cs


def _shortest_path_unconstrained(graph: Graph, start: int, goal: int) -> List[int]:
    queue: deque[int] = deque([start])
    previous: Dict[int, Optional[int]] = {start: None}

    while queue:
        current = queue.popleft()
        if current == goal:
            break
        for neighbor_id in graph.adj.get(current, set()):
            if neighbor_id in previous:
                continue
            previous[neighbor_id] = current
            queue.append(neighbor_id)

    if goal not in previous:
        return []

    path: List[int] = []
    node_id: Optional[int] = goal
    while node_id is not None:
        path.append(node_id)
        node_id = previous[node_id]
    path.reverse()
    return path


def _repair_connectivity_gwccvc(graph: Graph, cover_set: Set[int]) -> Set[int]:
    cs = set(cover_set)
    components = get_cover_components(graph, cs)
    if len(components) <= 1:
        return cs

    reps = [min(component, key=lambda node_id: graph.nodes[node_id].weight) for component in components]
    base = reps[0]
    for rep in reps[1:]:
        path = _shortest_path_unconstrained(graph, base, rep)
        if path:
            _add_path_to_cover(graph, cs, path)
    return cs


def mark_red_nodes(graph: Graph, cover_set: Set[int], capacity_k: int) -> None:
    _ = cover_set
    for node in graph.nodes.values():
        if node.color != "WHITE":
            continue
        ud = uncovered_degree(graph, node.id, True)
        if ud <= 1:
            node.color = "RED"
            continue
        if ud > capacity_k:
            for neighbor_id in graph.adj.get(node.id, set()):
                neighbor = graph.nodes[neighbor_id]
                if neighbor.color == "WHITE" and uncovered_degree(graph, neighbor_id, True) <= 1:
                    neighbor.color = "RED"


def get_candidate_pool(graph: Graph, allow_black: bool = False) -> List[Node]:
    red: List[Node] = []
    white: List[Node] = []
    gray: List[Node] = []

    for node in graph.nodes.values():
        if node.color == "BLACK" or node.remaining <= 0:
            continue
        if uncovered_degree(graph, node.id, not allow_black) <= 0:
            continue
        if node.color == "RED":
            red.append(node)
        elif node.color == "WHITE":
            white.append(node)
        elif node.color == "GRAY":
            gray.append(node)

    if red:
        return red
    if white:
        return white
    return gray


EdgeSorter = Callable[[Graph, Node, bool], List[Tuple[int, Edge]]]
PickNextNode = Callable[[Graph, bool], Optional[Node]]


def cover_edges_from_node(
    graph: Graph,
    node: Node,
    edge_sorter: EdgeSorter,
    allow_black: bool = False,
) -> None:
    candidates = edge_sorter(graph, node, allow_black)
    for neighbor_id, edge in candidates:
        if node.remaining <= 0:
            break
        if edge.covered:
            continue
        edge.covered = True
        edge.covered_by = node.id
        node.remaining -= 1
        neighbor = graph.nodes[neighbor_id]
        if neighbor.color in {"WHITE", "RED"}:
            neighbor.color = "GRAY"


def select_node(
    graph: Graph,
    node: Node,
    edge_sorter: EdgeSorter,
    cover_set: Set[int],
    allow_black: bool = False,
) -> None:
    node.color = "BLACK"
    cover_set.add(node.id)
    cover_edges_from_node(graph, node, edge_sorter, allow_black)


def force_cover_remaining(
    graph: Graph,
    cover_set: Set[int],
    pick_next: PickNextNode,
    edge_sorter: EdgeSorter,
) -> None:
    for node_id in list(cover_set):
        node = graph.nodes[node_id]
        if node.remaining > 0:
            cover_edges_from_node(graph, node, edge_sorter, True)

    safety = 0
    while get_uncovered_edges(graph):
        node = pick_next(graph, True)
        if node is None:
            break
        select_node(graph, node, edge_sorter, cover_set, True)
        safety += 1
        if safety > len(graph.nodes):
            break


def random_choice(rnd: random.Random, items: Sequence[Node]) -> Optional[Node]:
    if not items:
        return None
    return items[rnd.randrange(len(items))]


def solve_gccvc(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    seed: int = 42,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    graph = create_graph(vertex_data, edge_data, capacity_k)
    rnd = random.Random(seed)
    cover_set: Set[int] = set()

    def pick_next(g: Graph, allow_black: bool) -> Optional[Node]:
        candidates = get_candidate_pool(g, allow_black)
        if not candidates:
            return None
        best_score = -1
        best_weight = float("inf")
        best_nodes: List[Node] = []
        for node in candidates:
            score = uncovered_degree(g, node.id, not allow_black)
            if score > best_score or (score == best_score and node.weight < best_weight):
                best_score = score
                best_weight = node.weight
                best_nodes = [node]
            elif score == best_score and node.weight == best_weight:
                best_nodes.append(node)
        return random_choice(rnd, best_nodes)

    def edge_sorter(g: Graph, node: Node, allow_black: bool) -> List[Tuple[int, Edge]]:
        candidates = get_edge_candidates(g, node.id, allow_black)
        candidates.sort(
            key=lambda candidate: (
                -uncovered_degree(g, candidate[0], True),
                g.nodes[candidate[0]].weight,
                candidate[0],
            )
        )
        return candidates

    while get_uncovered_edges(graph):
        mark_red_nodes(graph, cover_set, capacity_k)
        node = pick_next(graph, False)
        if node is None:
            break
        select_node(graph, node, edge_sorter, cover_set, False)

    if get_uncovered_edges(graph):
        force_cover_remaining(graph, cover_set, pick_next, edge_sorter)

    final_set = _repair_connectivity_capacity_aware(graph, cover_set)
    return {
        "cover": final_set,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "GCCVC",
    }


def solve_grccvc(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    seed: int = 42,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    graph = create_graph(vertex_data, edge_data, capacity_k)
    rnd = random.Random(seed)
    cover_set: Set[int] = set()

    def pick_next(g: Graph, allow_black: bool) -> Optional[Node]:
        candidates = get_candidate_pool(g, allow_black)
        if not candidates:
            return None
        best_ratio = float("inf")
        best_weight = float("inf")
        best_nodes: List[Node] = []
        for node in candidates:
            denom = sum_uncovered_neighbor_weights(g, node.id, allow_black)
            ratio = float("inf") if denom <= 0 else node.weight / denom
            if ratio < best_ratio or (ratio == best_ratio and node.weight < best_weight):
                best_ratio = ratio
                best_weight = node.weight
                best_nodes = [node]
            elif ratio == best_ratio and node.weight == best_weight:
                best_nodes.append(node)
        return random_choice(rnd, best_nodes)

    def edge_sorter(g: Graph, node: Node, allow_black: bool) -> List[Tuple[int, Edge]]:
        candidates = get_edge_candidates(g, node.id, allow_black)
        rnd.shuffle(candidates)
        return candidates

    while get_uncovered_edges(graph):
        mark_red_nodes(graph, cover_set, capacity_k)
        node = pick_next(graph, False)
        if node is None:
            break
        select_node(graph, node, edge_sorter, cover_set, False)

    if get_uncovered_edges(graph):
        force_cover_remaining(graph, cover_set, pick_next, edge_sorter)

    final_set = _repair_connectivity_capacity_aware(graph, cover_set)
    return {
        "cover": final_set,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "GRCCVC",
    }


def solve_gwccvc(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    seed: int = 42,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    graph = create_graph(vertex_data, edge_data, capacity_k)
    rnd = random.Random(seed)
    cover_set: Set[int] = set()

    def pick_next(g: Graph, allow_black: bool) -> Optional[Node]:
        candidates = get_candidate_pool(g, allow_black)
        if not candidates:
            return None
        best_weight = float("inf")
        best_degree = -1
        best_nodes: List[Node] = []
        for node in candidates:
            degree = uncovered_degree(g, node.id, not allow_black)
            if node.weight < best_weight or (
                node.weight == best_weight and degree > best_degree
            ):
                best_weight = node.weight
                best_degree = degree
                best_nodes = [node]
            elif node.weight == best_weight and degree == best_degree:
                best_nodes.append(node)
        return random_choice(rnd, best_nodes)

    def edge_sorter(g: Graph, node: Node, allow_black: bool) -> List[Tuple[int, Edge]]:
        candidates = get_edge_candidates(g, node.id, allow_black)
        return sorted(
            candidates,
            key=lambda candidate: 0 if g.nodes[candidate[0]].color == "WHITE" else 1,
        )

    while get_uncovered_edges(graph):
        mark_red_nodes(graph, cover_set, capacity_k)
        node = pick_next(graph, False)
        if node is None:
            break
        select_node(graph, node, edge_sorter, cover_set, False)

    if get_uncovered_edges(graph):
        force_cover_remaining(graph, cover_set, pick_next, edge_sorter)

    final_set = _repair_connectivity_gwccvc(graph, cover_set)
    return {
        "cover": final_set,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "GWCCVC",
    }


def solve_hga(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    pop_size: int,
    generations: int,
    seed: int = 42,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ids = [int(v["id"]) for v in vertex_data]
    w_map = {int(v["id"]): float(v["weight"]) for v in vertex_data}
    rnd = random.Random(seed)
    history: List[Dict[str, Any]] = []

    adj_map: Dict[int, Set[int]] = {node_id: set() for node_id in ids}
    normalized_edges = [(int(u), int(v)) for u, v in edge_data]
    for u, v in normalized_edges:
        if u in adj_map and v in adj_map:
            adj_map[u].add(v)
            adj_map[v].add(u)
    edge_count = len(normalized_edges)
    capacity_cache: Dict[FrozenSet[int], bool] = {}
    feasible_cache: Dict[FrozenSet[int], bool] = {}

    def cover_weight(cover_set: Set[int]) -> float:
        return sum(w_map.get(node_id, 0.0) for node_id in cover_set)

    def count_uncov(cover_set: Set[int]) -> int:
        return sum(
            1
            for u, v in normalized_edges
            if u not in cover_set and v not in cover_set
        )

    def is_conn(cover_set: Set[int]) -> bool:
        if len(cover_set) <= 1:
            return True
        start = next(iter(cover_set))
        stack = [start]
        visited = {start}
        while stack:
            u = stack.pop()
            for w in adj_map.get(u, set()):
                if w in cover_set and w not in visited:
                    visited.add(w)
                    stack.append(w)
        return len(visited) == len(cover_set)

    def cap_feasible(cover_set: Set[int]) -> bool:
        frozen = frozenset(cover_set)
        cached = capacity_cache.get(frozen)
        if cached is not None:
            return cached
        feasible = _check_capacity_feasibility_raw(normalized_edges, set(cover_set), capacity_k)
        capacity_cache[frozen] = feasible
        return feasible

    def is_vertex_cover_set(cover_set: Set[int]) -> bool:
        return all(u in cover_set or v in cover_set for u, v in normalized_edges)

    def decode(theta: Sequence[float], keys: Dict[int, float]) -> Set[int]:
        graph = create_graph(vertex_data, normalized_edges, capacity_k)
        cover_set: Set[int] = set()
        a, b, c, d, e, eps = theta

        def score(node: Node, allow_black: bool) -> float:
            degree = uncovered_degree(graph, node.id, not allow_black)
            w_neighbor = sum_uncovered_neighbor_weights(graph, node.id, allow_black)
            ratio = 1e9 if w_neighbor <= 0 else node.weight / w_neighbor
            red_bonus = 1.0 if node.color == "RED" else 0.0
            gray_bonus = 1.0 if node.color == "GRAY" else 0.0
            key = keys.get(node.id, 0.0)
            weight_efficiency = degree / max(1e-9, node.weight)
            return (
                a * degree
                - b * node.weight
                - c * ratio
                + d * red_bonus
                + e * gray_bonus
                + 0.3 * a * weight_efficiency
                - eps * key
            )

        def pick_next(g: Graph, allow_black: bool) -> Optional[Node]:
            candidates = get_candidate_pool(g, allow_black)
            if not candidates:
                return None
            best = float("-inf")
            best_nodes: List[Node] = []
            for node in candidates:
                value = score(node, allow_black)
                if value > best:
                    best = value
                    best_nodes = [node]
                elif abs(value - best) < 1e-9:
                    best_nodes.append(node)
            return random_choice(rnd, best_nodes)

        def edge_sorter(g: Graph, node: Node, allow_black: bool) -> List[Tuple[int, Edge]]:
            candidates = get_edge_candidates(g, node.id, allow_black)
            candidates.sort(
                key=lambda candidate: -uncovered_degree(g, candidate[0], True)
            )
            return candidates

        while has_uncovered_edges(graph):
            mark_red_nodes(graph, cover_set, capacity_k)
            node = pick_next(graph, False)
            if node is None:
                break
            select_node(graph, node, edge_sorter, cover_set, False)

        if has_uncovered_edges(graph):
            force_cover_remaining(graph, cover_set, pick_next, edge_sorter)
        return _repair_connectivity_capacity_aware(graph, cover_set)

    def is_feasible_cover_set(cover_set: Set[int]) -> bool:
        frozen = frozenset(cover_set)
        cached = feasible_cache.get(frozen)
        if cached is not None:
            return cached
        if not cover_set or len(cover_set) * capacity_k < edge_count:
            feasible_cache[frozen] = False
            return False
        if not is_conn(cover_set):
            feasible_cache[frozen] = False
            return False
        if not is_vertex_cover_set(cover_set):
            feasible_cache[frozen] = False
            return False
        feasible = cap_feasible(cover_set)
        feasible_cache[frozen] = feasible
        return feasible

    def prune_redundant_nodes(cover_set: Set[int], max_passes: int = 1) -> Set[int]:
        current = set(cover_set)
        for _ in range(max_passes):
            changed = False
            for node_id in sorted(
                current, key=lambda nid: w_map.get(nid, 0.0), reverse=True
            ):
                trial = set(current)
                trial.discard(node_id)
                if is_feasible_cover_set(trial):
                    current = trial
                    changed = True
            if not changed:
                break
        return current

    light_nodes = sorted(ids, key=lambda node_id: w_map.get(node_id, float("inf")))

    def local_search(cover_set: Set[int], moves: int = 6, candidate_limit: int = 5) -> Set[int]:
        current = prune_redundant_nodes(cover_set, max_passes=1)
        current_weight = cover_weight(current)
        applied = 0

        while applied < moves:
            improved = False
            for remove_node in sorted(
                current, key=lambda node_id: w_map.get(node_id, 0.0), reverse=True
            ):
                candidates: List[int] = []
                seen: Set[int] = set()

                for node_id in sorted(
                    adj_map.get(remove_node, set()),
                    key=lambda nid: (w_map.get(nid, float("inf")), -len(adj_map.get(nid, set()))),
                ):
                    if node_id in current or node_id in seen:
                        continue
                    seen.add(node_id)
                    candidates.append(node_id)
                    if len(candidates) >= candidate_limit:
                        break

                if len(candidates) < candidate_limit:
                    for node_id in light_nodes:
                        if node_id in current or node_id in seen:
                            continue
                        seen.add(node_id)
                        candidates.append(node_id)
                        if len(candidates) >= candidate_limit:
                            break

                for add_node in candidates:
                    trial = set(current)
                    trial.add(add_node)
                    trial.discard(remove_node)
                    trial = prune_redundant_nodes(trial, max_passes=1)
                    if not is_feasible_cover_set(trial):
                        continue
                    trial_weight = cover_weight(trial)
                    if trial_weight + 1e-9 < current_weight:
                        current = trial
                        current_weight = trial_weight
                        applied += 1
                        improved = True
                        break

                if improved:
                    break

            if not improved:
                break

        return current

    def weight_focus_local_search(
        cover_set: Set[int], moves: int = 6, candidate_limit: int = 6
    ) -> Set[int]:
        current = prune_redundant_nodes(cover_set, max_passes=1)
        current_weight = cover_weight(current)
        for _ in range(moves):
            if not current:
                break
            improved = False
            heavy_nodes = sorted(
                current,
                key=lambda nid: w_map.get(nid, 0.0),
                reverse=True,
            )[: min(3, len(current))]
            for heavy in heavy_nodes:
                trial = set(current)
                trial.discard(heavy)
                if is_feasible_cover_set(trial):
                    trial = prune_redundant_nodes(trial, max_passes=1)
                    trial_weight = cover_weight(trial)
                    if trial_weight + 1e-9 < current_weight:
                        current = trial
                        current_weight = trial_weight
                        improved = True
                        break

                candidates = sorted(
                    (nid for nid in adj_map.get(heavy, set()) if nid not in current),
                    key=lambda nid: (
                        w_map.get(nid, float("inf")),
                        -len(adj_map.get(nid, set())),
                    ),
                )
                if len(candidates) < candidate_limit:
                    for node_id in light_nodes:
                        if node_id in current:
                            continue
                        candidates.append(node_id)
                        if len(candidates) >= candidate_limit:
                            break

                for add_nid in candidates[:candidate_limit]:
                    if add_nid in current:
                        continue
                    expected_weight = (
                        current_weight
                        - w_map.get(heavy, 0.0)
                        + w_map.get(add_nid, 0.0)
                    )
                    if expected_weight + 1e-9 >= current_weight:
                        continue
                    swap = set(current)
                    swap.discard(heavy)
                    swap.add(add_nid)
                    if not is_feasible_cover_set(swap):
                        continue
                    swap = prune_redundant_nodes(swap, max_passes=1)
                    swap_weight = cover_weight(swap)
                    if swap_weight + 1e-9 < current_weight:
                        current = swap
                        current_weight = swap_weight
                        improved = True
                        break
                if improved:
                    break
            if not improved:
                break
        return current

    def evaluate_cover(cover_set: Set[int]) -> Dict[str, Any]:
        weight = cover_weight(cover_set)
        uncov = count_uncov(cover_set)
        conn = is_conn(cover_set)
        cap_ok = len(cover_set) * capacity_k >= edge_count
        if uncov == 0 and conn and cap_ok:
            cap_ok = cap_feasible(cover_set)
        feasible = uncov == 0 and conn and cap_ok
        penalty = (
            0.0
            if feasible
            else uncov * 1_000_000.0 + (0.0 if conn else 100_000.0) + (0.0 if cap_ok else 100_000.0)
        )
        return {
            "cost": weight + penalty,
            "cover": cover_set,
            "feasible": feasible,
            "weight": weight,
        }

    def evaluate(theta: Sequence[float], keys: Dict[int, float]) -> Dict[str, Any]:
        cover = decode(theta, keys)
        if rnd.random() < local_search_probability:
            cover = local_search(
                cover,
                local_search_moves,
                candidate_limit=local_search_candidates,
            )
        if rnd.random() < weight_focus_probability:
            cover = weight_focus_local_search(
                cover,
                moves=weight_focus_moves,
                candidate_limit=weight_focus_candidates,
            )
        return evaluate_cover(cover)

    def seed_keys(cover_set: Set[int]) -> Dict[int, float]:
        keys: Dict[int, float] = {}
        for node_id in ids:
            if node_id in cover_set:
                keys[node_id] = rnd.random() * 0.3
            else:
                keys[node_id] = 0.7 + rnd.random() * 0.3
        return keys

    target_pop = max(2, int(pop_size))
    if len(ids) >= 180:
        local_search_probability = 0.12
        local_search_moves = 3
        local_search_candidates = 3
        weight_focus_probability = 0.35
        weight_focus_moves = 3
        weight_focus_candidates = 4
    elif len(ids) >= 100:
        local_search_probability = 0.24
        local_search_moves = 4
        local_search_candidates = 4
        weight_focus_probability = 0.65
        weight_focus_moves = 4
        weight_focus_candidates = 5
    else:
        local_search_probability = 0.45
        local_search_moves = 5
        local_search_candidates = 5
        weight_focus_probability = 1.0
        weight_focus_moves = 6
        weight_focus_candidates = 6
    population: List[Dict[str, Any]] = []
    greedy_results = [
        solve_gccvc(vertex_data, normalized_edges, capacity_k, seed),
        solve_grccvc(vertex_data, normalized_edges, capacity_k, seed + 1),
        solve_gwccvc(vertex_data, normalized_edges, capacity_k, seed + 2),
    ]
    theta_seeds = [
        [1.0, 0.2, 0.0, 0.2, 0.05, 0.1],
        [0.6, 0.2, 1.0, 0.2, 0.05, 0.1],
        [0.45, 1.25, 0.2, 0.2, 0.05, 0.08],
        [0.4, 1.55, 0.35, 0.15, 0.05, 0.08],
    ]
    for idx, theta_seed in enumerate(theta_seeds):
        if len(population) >= target_pop:
            break
        greedy_result = greedy_results[idx % len(greedy_results)]
        population.append(
            {
                "theta": list(theta_seed),
                "keys": seed_keys(set(greedy_result["cover"])),
            }
        )

    while len(population) < target_pop:
        if rnd.random() < 0.5 and theta_seeds:
            base = theta_seeds[rnd.randrange(len(theta_seeds))]
            theta = [
                max(0.0, min(3.0, value + (rnd.random() - 0.5) * 1.2))
                for value in base
            ]
        else:
            theta = [rnd.random() * 3.0 for _ in range(6)]
        keys = {node_id: rnd.random() for node_id in ids}
        population.append({"theta": theta, "keys": keys})

    best_cover: Optional[Set[int]] = None
    best_cost = float("inf")
    stagnation = 0
    last_grccvc_inject_gen = -12

    for generation in range(max(1, int(generations))):
        if len(capacity_cache) > 30_000:
            capacity_cache.clear()
        if len(feasible_cache) > 30_000:
            feasible_cache.clear()
        evaluations: List[Dict[str, Any]] = []
        for individual in population:
            evaluation = evaluate(individual["theta"], individual["keys"])
            evaluations.append(
                {
                    **individual,
                    **evaluation,
                }
            )
        evaluations.sort(key=lambda item: item["cost"])

        if evaluations:
            refine_count = min(len(evaluations), max(1, target_pop // 10))
            run_refinement = generation % 4 == 0 or stagnation >= 4
            improved_any = False
            if run_refinement:
                for idx in range(refine_count):
                    candidate = evaluations[idx]
                    refined_cover = local_search(
                        candidate["cover"],
                        local_search_moves,
                        candidate_limit=local_search_candidates,
                    )
                    refined_cover = weight_focus_local_search(
                        refined_cover,
                        moves=weight_focus_moves + 1,
                        candidate_limit=weight_focus_candidates,
                    )
                    if refined_cover == candidate["cover"]:
                        continue
                    refined_eval = evaluate_cover(refined_cover)
                    if refined_eval["cost"] + 1e-9 < candidate["cost"]:
                        evaluations[idx] = {
                            **candidate,
                            **refined_eval,
                        }
                        improved_any = True
                if stagnation >= 2 or generation % 6 == 0:
                    top_span = min(3, len(evaluations))
                    for idx in range(top_span):
                        candidate = evaluations[idx]
                        w_refined = weight_focus_local_search(
                            candidate["cover"],
                            moves=weight_focus_moves + 2,
                            candidate_limit=weight_focus_candidates,
                        )
                        if w_refined == candidate["cover"]:
                            continue
                        w_eval = evaluate_cover(w_refined)
                        if w_eval["cost"] + 1e-9 < candidate["cost"]:
                            evaluations[idx] = {
                                **candidate,
                                **w_eval,
                            }
                            improved_any = True
            if improved_any:
                evaluations.sort(key=lambda item: item["cost"])

        if evaluations and evaluations[0]["cost"] < best_cost - 1e-9:
            best_cost = evaluations[0]["cost"]
            best_cover = set(evaluations[0]["cover"])
            stagnation = 0
        else:
            stagnation += 1

        best_weight = cover_weight(best_cover or set())
        avg_cost = (
            sum(evaluation["cost"] for evaluation in evaluations) / len(evaluations)
            if evaluations
            else 0.0
        )
        history.append(
            {
                "gen": generation,
                "bestWeight": best_weight,
                "bestSize": len(best_cover or set()),
                "feasible": bool(evaluations and evaluations[0]["feasible"]),
                "avgCost": avg_cost,
                "stagnation": stagnation,
            }
        )

        elite_count = 1 if target_pop <= 12 else 2
        if stagnation >= 10:
            elite_count = 1
        elite_count = min(elite_count, len(evaluations))
        new_population = [
            {
                "theta": list(evaluations[i]["theta"]),
                "keys": dict(evaluations[i]["keys"]),
            }
            for i in range(elite_count)
        ]

        # Inject a fresh GRCCVC-based individual on stagnation to pull solution toward better greedy basin.
        if stagnation >= 8 and (generation - last_grccvc_inject_gen) >= 7:
            grccvc_seed = solve_grccvc(vertex_data, normalized_edges, capacity_k, seed + generation)
            new_population.append(
                {
                    "theta": list(theta_seeds[1]),
                    "keys": seed_keys(set(grccvc_seed["cover"])),
                }
            )
            last_grccvc_inject_gen = generation

        def tournament_pick() -> Dict[str, Any]:
            best_individual: Optional[Dict[str, Any]] = None
            for _ in range(2):
                candidate = evaluations[rnd.randrange(len(evaluations))]
                if best_individual is None or candidate["cost"] < best_individual["cost"]:
                    best_individual = candidate
            return best_individual if best_individual is not None else evaluations[0]

        immigrant_count = max(1, target_pop // 10)
        if stagnation >= 6:
            immigrant_count = max(immigrant_count, target_pop // 6)
        if stagnation >= 12:
            immigrant_count = max(immigrant_count, target_pop // 4)
        max_immigrants = max(1, target_pop - elite_count)
        immigrant_count = min(immigrant_count, max_immigrants)

        alpha = 0.35 if stagnation < 8 else 0.55
        theta_mutation_prob = min(0.65, 0.18 + 0.02 * stagnation)
        theta_mutation_width = 0.35 + 0.05 * min(stagnation, 8)
        key_mutation_prob = min(0.30, 0.015 + 0.005 * stagnation)
        key_mutation_width = 0.2 + 0.03 * min(stagnation, 8)
        key_reset_prob = 0.01 if stagnation < 8 else 0.04

        while len(new_population) < target_pop - immigrant_count:
            parent_a = tournament_pick()
            parent_b = tournament_pick()
            if len(evaluations) > 1:
                safety = 0
                while parent_a is parent_b and safety < 3:
                    parent_b = tournament_pick()
                    safety += 1
            child_theta: List[float] = []
            for idx, value in enumerate(parent_a["theta"]):
                a_val = value
                b_val = parent_b["theta"][idx]
                lo = min(a_val, b_val)
                hi = max(a_val, b_val)
                span = hi - lo
                sampled = lo - alpha * span + rnd.random() * (span * (1.0 + 2.0 * alpha))
                child_theta.append(max(0.0, min(3.0, sampled)))

            child_keys: Dict[int, float] = {}
            for node_id in ids:
                key_a = parent_a["keys"][node_id]
                key_b = parent_b["keys"][node_id]
                if rnd.random() < 0.1:
                    base_key = (key_a + key_b) * 0.5
                elif rnd.random() < 0.5:
                    base_key = key_a
                else:
                    base_key = key_b
                child_keys[node_id] = max(0.0, min(1.0, base_key))

            for idx in range(6):
                if rnd.random() < theta_mutation_prob:
                    child_theta[idx] = max(
                        0.0,
                        min(3.0, child_theta[idx] + (rnd.random() - 0.5) * (2.0 * theta_mutation_width)),
                    )

            for node_id in ids:
                if rnd.random() < key_reset_prob:
                    child_keys[node_id] = rnd.random()
                elif rnd.random() < key_mutation_prob:
                    child_keys[node_id] = max(
                        0.0,
                        min(1.0, child_keys[node_id] + (rnd.random() - 0.5) * key_mutation_width),
                    )

            new_population.append({"theta": child_theta, "keys": child_keys})

        while len(new_population) < target_pop:
            if evaluations and rnd.random() < 0.45:
                parent = evaluations[rnd.randrange(max(1, len(evaluations) // 2))]
                theta = [
                    max(0.0, min(3.0, value + (rnd.random() - 0.5) * 1.6))
                    for value in parent["theta"]
                ]
            else:
                theta = [rnd.random() * 3.0 for _ in range(6)]
            keys = {node_id: rnd.random() for node_id in ids}
            new_population.append({"theta": theta, "keys": keys})

        population = new_population

    return {
        "cover": best_cover or set(),
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "HGA-CCVC",
        "history": history,
    }


class HGA_CCVC_V2:
    def __init__(
        self,
        vertex_data: Sequence[Dict[str, Any]],
        edge_data: Sequence[Tuple[int, int]],
        capacity_k: int,
        pop_size: int,
        generations: int,
        seed: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        if capacity_k <= 0:
            raise ValueError("capacity_k must be positive for HGA v2.")
        self.vertex_data = list(vertex_data)
        self.edge_data = [(int(u), int(v)) for u, v in edge_data]
        self.capacity_k = int(capacity_k)
        self.rng = random.Random(seed)
        self.node_ids = [int(v["id"]) for v in self.vertex_data]
        self.w_map = {int(v["id"]): float(v["weight"]) for v in self.vertex_data}
        self.adj_map: Dict[int, Set[int]] = {node_id: set() for node_id in self.node_ids}
        for u, v in self.edge_data:
            if u in self.adj_map and v in self.adj_map:
                self.adj_map[u].add(v)
                self.adj_map[v].add(u)
        self.params = self._build_params(pop_size, generations, params)
        self._adapt_runtime_params()
        self.edge_count = len(self.edge_data)
        self.capacity_cache: Dict[FrozenSet[int], bool] = {}
        self.feasible_cache: Dict[FrozenSet[int], bool] = {}
        self.history: List[Dict[str, Any]] = []

    def _build_params(
        self,
        pop_size: int,
        generations: int,
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        defaults: Dict[str, Any] = {
            "population_size": max(2, int(pop_size)),
            "generations": max(1, int(generations)),
            "elite_size": 2,
            "tournament_k": 3,
            "theta_mut_prob": 0.2,
            "theta_mut_sigma": 0.2,
            "theta_min": 0.0,
            "theta_max": 3.0,
            "key_mut_prob": 0.02,
            "local_search_prob": 0.2,
            "local_search_moves": 7,
            "local_search_trials": 36,
            "penalty_uncovered": 1_000_000.0,
            "penalty_disconnected": 100_000.0,
            "penalty_capacity": 100_000.0,
            "edge_selection": "stochastic",
            "top_l": 3,
            "repair_mode": "tier2",
            "stall_generations": 10,
            "seed_bias": 0.3,
        }
        if params:
            defaults.update(params)
        defaults["population_size"] = max(2, int(defaults["population_size"]))
        defaults["generations"] = max(1, int(defaults["generations"]))
        defaults["elite_size"] = max(1, int(defaults["elite_size"]))
        defaults["tournament_k"] = max(1, int(defaults["tournament_k"]))
        defaults["top_l"] = max(1, int(defaults["top_l"]))
        defaults["stall_generations"] = max(1, int(defaults["stall_generations"]))
        defaults["local_search_moves"] = max(1, int(defaults["local_search_moves"]))
        defaults["local_search_trials"] = max(1, int(defaults["local_search_trials"]))
        defaults["theta_min"] = float(defaults["theta_min"])
        defaults["theta_max"] = float(defaults["theta_max"])
        if defaults["theta_min"] > defaults["theta_max"]:
            defaults["theta_min"], defaults["theta_max"] = (
                defaults["theta_max"],
                defaults["theta_min"],
            )
        return defaults

    def _adapt_runtime_params(self) -> None:
        n = len(self.node_ids)
        if n >= 180:
            self.params["local_search_prob"] = min(float(self.params["local_search_prob"]), 0.08)
            self.params["local_search_moves"] = min(int(self.params["local_search_moves"]), 3)
            self.params["local_search_trials"] = min(int(self.params["local_search_trials"]), 16)
            self.params["top_l"] = min(int(self.params["top_l"]), 2)
            self.params["elite_size"] = min(int(self.params["elite_size"]), 1)
            self.params["stall_generations"] = min(int(self.params["stall_generations"]), 8)
        elif n >= 110:
            self.params["local_search_prob"] = min(float(self.params["local_search_prob"]), 0.14)
            self.params["local_search_moves"] = min(int(self.params["local_search_moves"]), 4)
            self.params["local_search_trials"] = min(int(self.params["local_search_trials"]), 24)
            self.params["top_l"] = min(int(self.params["top_l"]), 2)
            self.params["stall_generations"] = min(int(self.params["stall_generations"]), 9)
        else:
            self.params["local_search_prob"] = min(float(self.params["local_search_prob"]), 0.22)
            self.params["local_search_moves"] = min(int(self.params["local_search_moves"]), 6)
            self.params["local_search_trials"] = min(int(self.params["local_search_trials"]), 32)

    def _chromosome(self, theta: Sequence[float], r_keys: Dict[int, float]) -> Dict[str, Any]:
        return {"theta": list(theta), "r_keys": dict(r_keys)}

    def _copy_chromosome(self, chrom: Dict[str, Any]) -> Dict[str, Any]:
        return {"theta": list(chrom["theta"]), "r_keys": dict(chrom["r_keys"])}

    def _random_theta(self) -> List[float]:
        theta_min = float(self.params["theta_min"])
        theta_max = float(self.params["theta_max"])
        return [self.rng.uniform(theta_min, theta_max) for _ in range(6)]

    def _seed_keys_from_cover(self, cover_set: Set[int]) -> Dict[int, float]:
        bias = float(self.params["seed_bias"])
        low_max = max(0.0, min(1.0, bias))
        high_min = min(1.0, max(0.0, 1.0 - bias))
        keys: Dict[int, float] = {}
        for node_id in self.node_ids:
            if node_id in cover_set:
                keys[node_id] = self.rng.uniform(0.0, low_max)
            else:
                keys[node_id] = self.rng.uniform(high_min, 1.0)
        return keys

    def _seed_population(self) -> List[Dict[str, Any]]:
        seeded: List[Dict[str, Any]] = []
        strategy_defs = [
            (solve_gccvc, [1.0, 0.2, 0.0, 0.2, 0.05, 0.1]),
            (solve_grccvc, [0.6, 0.2, 1.0, 0.2, 0.05, 0.1]),
            (solve_gwccvc, [0.45, 1.25, 0.2, 0.2, 0.05, 0.08]),
            (solve_gwccvc, [0.4, 1.55, 0.35, 0.15, 0.05, 0.08]),
        ]
        for solver, theta in strategy_defs:
            result = solver(
                self.vertex_data,
                self.edge_data,
                self.capacity_k,
                seed=self.rng.randint(0, 10**6),
            )
            cover_set = {int(node_id) for node_id in result["cover"]}
            seeded.append(self._chromosome(theta, self._seed_keys_from_cover(cover_set)))
        return seeded

    def _initialize_population(self) -> List[Dict[str, Any]]:
        population = self._seed_population()
        target = int(self.params["population_size"])
        while len(population) < target:
            r_keys = {node_id: self.rng.random() for node_id in self.node_ids}
            population.append(self._chromosome(self._random_theta(), r_keys))
        return population[:target]

    def _decode(self, chrom: Dict[str, Any]) -> Set[int]:
        graph = create_graph(self.vertex_data, self.edge_data, self.capacity_k)
        cover_set: Set[int] = set()
        theta = chrom["theta"]
        r_keys = chrom["r_keys"]
        edge_selection = str(self.params["edge_selection"]).strip().lower()
        top_l = int(self.params["top_l"])
        repair_mode = str(self.params["repair_mode"]).strip().lower()
        a, b, c, d, e, eps = theta

        def score(node: Node, allow_black: bool) -> float:
            degree = uncovered_degree(graph, node.id, not allow_black)
            w_neighbor = sum_uncovered_neighbor_weights(graph, node.id, allow_black)
            ratio = 1e9 if w_neighbor <= 0 else node.weight / w_neighbor
            red_bonus = 1.0 if node.color == "RED" else 0.0
            gray_bonus = 1.0 if node.color == "GRAY" else 0.0
            key = float(r_keys.get(node.id, 0.0))
            weight_efficiency = degree / max(1e-9, node.weight)
            return (
                a * degree
                - b * node.weight
                - c * ratio
                + d * red_bonus
                + e * gray_bonus
                + 0.3 * a * weight_efficiency
                - eps * key
            )

        def pick_next(g: Graph, allow_black: bool) -> Optional[Node]:
            candidates = get_candidate_pool(g, allow_black)
            if not candidates:
                return None
            scored = [(score(node, allow_black), node) for node in candidates]
            scored.sort(key=lambda item: item[0], reverse=True)
            if edge_selection == "stochastic":
                pool_size = min(top_l, len(scored))
                picked = scored[self.rng.randrange(pool_size)][1]
                return picked
            best_value = scored[0][0]
            tied = [node for value, node in scored if abs(value - best_value) < 1e-9]
            return random_choice(self.rng, tied)

        def edge_sorter(g: Graph, node: Node, allow_black: bool) -> List[Tuple[int, Edge]]:
            candidates = get_edge_candidates(g, node.id, allow_black)
            candidates.sort(
                key=lambda candidate: (
                    -uncovered_degree(g, candidate[0], True),
                    g.nodes[candidate[0]].weight,
                    candidate[0],
                )
            )
            if edge_selection == "stochastic" and len(candidates) > top_l:
                head = candidates[:top_l]
                tail = candidates[top_l:]
                self.rng.shuffle(head)
                return head + tail
            return candidates

        while has_uncovered_edges(graph):
            mark_red_nodes(graph, cover_set, self.capacity_k)
            node = pick_next(graph, False)
            if node is None:
                break
            select_node(graph, node, edge_sorter, cover_set, False)

        if has_uncovered_edges(graph):
            force_cover_remaining(graph, cover_set, pick_next, edge_sorter)

        if repair_mode in {"tier2", "capacity-aware", "capacity_aware"}:
            return _repair_connectivity_capacity_aware(graph, cover_set)
        if repair_mode in {"gwccvc", "gw"}:
            return _repair_connectivity_gwccvc(graph, cover_set)
        return repair_connectivity(graph, cover_set)

    def _cover_weight(self, cover_set: Set[int]) -> float:
        return sum(self.w_map.get(node_id, 0.0) for node_id in cover_set)

    def _count_uncovered_edges(self, cover_set: Set[int]) -> int:
        return sum(
            1
            for u, v in self.edge_data
            if u not in cover_set and v not in cover_set
        )

    def _is_connected_cover(self, cover_set: Set[int]) -> bool:
        if not cover_set:
            return False
        if len(cover_set) == 1:
            return True
        start = next(iter(cover_set))
        stack = [start]
        visited = {start}
        while stack:
            node_id = stack.pop()
            for neighbor in self.adj_map.get(node_id, set()):
                if neighbor in cover_set and neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        return len(visited) == len(cover_set)

    def _capacity_matching_feasible(self, cover_set: Set[int]) -> bool:
        frozen = frozenset(cover_set)
        cached = self.capacity_cache.get(frozen)
        if cached is not None:
            return cached
        feasible = _check_capacity_feasibility_raw(self.edge_data, cover_set, self.capacity_k)
        self.capacity_cache[frozen] = feasible
        return feasible

    def _is_ccvc_feasible(self, cover_set: Set[int]) -> bool:
        frozen = frozenset(cover_set)
        cached = self.feasible_cache.get(frozen)
        if cached is not None:
            return cached
        if not cover_set or len(cover_set) * self.capacity_k < self.edge_count:
            self.feasible_cache[frozen] = False
            return False
        if self._count_uncovered_edges(cover_set) > 0:
            self.feasible_cache[frozen] = False
            return False
        if not self._is_connected_cover(cover_set):
            self.feasible_cache[frozen] = False
            return False
        feasible = self._capacity_matching_feasible(cover_set)
        self.feasible_cache[frozen] = feasible
        return feasible

    def _local_search_prune(self, cover_set: Set[int]) -> Set[int]:
        if not cover_set:
            return set()
        move_limit = int(self.params["local_search_moves"])
        trial_limit = int(self.params["local_search_trials"])
        moves = 0
        trials = 0
        current = set(cover_set)
        current_weight = self._cover_weight(current)
        ordered = sorted(
            current,
            key=lambda node_id: self.w_map.get(node_id, 0.0),
            reverse=True,
        )
        for node_id in ordered:
            if moves >= move_limit or trials >= trial_limit:
                break
            candidate = set(current)
            candidate.remove(node_id)
            trials += 1
            candidate_weight = current_weight - self.w_map.get(node_id, 0.0)
            if candidate_weight + 1e-9 >= current_weight:
                continue
            if self._is_ccvc_feasible(candidate):
                current = candidate
                current_weight = candidate_weight
                moves += 1

        if moves < move_limit and trials < trial_limit:
            light_nodes = sorted(self.node_ids, key=lambda nid: self.w_map.get(nid, float("inf")))
            for remove_node in sorted(
                current,
                key=lambda node_id: self.w_map.get(node_id, 0.0),
                reverse=True,
            )[: min(6, len(current))]:
                if moves >= move_limit or trials >= trial_limit:
                    break
                candidates = sorted(
                    (nid for nid in self.adj_map.get(remove_node, set()) if nid not in current),
                    key=lambda nid: self.w_map.get(nid, float("inf")),
                )
                if not candidates:
                    candidates = [nid for nid in light_nodes if nid not in current]
                for add_node in candidates[:3]:
                    if moves >= move_limit or trials >= trial_limit:
                        break
                    trials += 1
                    trial_weight = (
                        current_weight
                        - self.w_map.get(remove_node, 0.0)
                        + self.w_map.get(add_node, 0.0)
                    )
                    if trial_weight + 1e-9 >= current_weight:
                        continue
                    trial = set(current)
                    trial.remove(remove_node)
                    trial.add(add_node)
                    if self._is_ccvc_feasible(trial):
                        current = trial
                        current_weight = trial_weight
                        moves += 1
                        break
        return current

    def _evaluate(self, chrom: Dict[str, Any]) -> Tuple[float, Set[int], bool]:
        cover_set = self._decode(chrom)
        if float(self.params["local_search_prob"]) > 0.0 and self.rng.random() < float(
            self.params["local_search_prob"]
        ):
            cover_set = self._local_search_prune(cover_set)

        weight = self._cover_weight(cover_set)
        uncovered = self._count_uncovered_edges(cover_set)
        connected = self._is_connected_cover(cover_set)
        capacity_ok = True
        cap_violation = 0

        total_capacity = len(cover_set) * self.capacity_k
        if total_capacity < self.edge_count:
            capacity_ok = False
            cap_violation = self.edge_count - total_capacity
        elif uncovered == 0 and connected:
            capacity_ok = self._capacity_matching_feasible(cover_set)
            cap_violation = 0 if capacity_ok else 1

        feasible = uncovered == 0 and connected and capacity_ok
        cost = weight + 0.001 * len(cover_set)
        if not feasible:
            cost += float(self.params["penalty_uncovered"]) * uncovered
            if not connected:
                cost += float(self.params["penalty_disconnected"])
            if not capacity_ok:
                cost += float(self.params["penalty_capacity"]) * max(1, cap_violation)
        return cost, cover_set, feasible

    def _tournament_select(self, evaluated: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        k = max(1, min(int(self.params["tournament_k"]), len(evaluated)))
        sample = self.rng.sample(list(evaluated), k)
        return min(sample, key=lambda item: item["cost"])

    def _crossover(self, parent_a: Dict[str, Any], parent_b: Dict[str, Any]) -> Dict[str, Any]:
        theta_a = parent_a["theta"]
        theta_b = parent_b["theta"]
        child_theta: List[float] = []
        for idx in range(len(theta_a)):
            gamma = self.rng.random()
            child_theta.append(gamma * theta_a[idx] + (1.0 - gamma) * theta_b[idx])

        child_keys: Dict[int, float] = {}
        for node_id in self.node_ids:
            if self.rng.random() < 0.5:
                child_keys[node_id] = parent_a["r_keys"][node_id]
            else:
                child_keys[node_id] = parent_b["r_keys"][node_id]
        return self._chromosome(child_theta, child_keys)

    def _mutate(self, chrom: Dict[str, Any]) -> Dict[str, Any]:
        theta = chrom["theta"]
        theta_min = float(self.params["theta_min"])
        theta_max = float(self.params["theta_max"])
        for idx in range(len(theta)):
            if self.rng.random() < float(self.params["theta_mut_prob"]):
                theta[idx] += self.rng.gauss(0.0, float(self.params["theta_mut_sigma"]))
                theta[idx] = min(max(theta[idx], theta_min), theta_max)

        keys = chrom["r_keys"]
        for node_id in keys:
            if self.rng.random() < float(self.params["key_mut_prob"]):
                keys[node_id] = self.rng.random()

        chrom["theta"] = theta
        chrom["r_keys"] = keys
        return chrom

    def run(self) -> Set[int]:
        population = self._initialize_population()
        best_cover: Set[int] = set()
        best_cost = float("inf")
        stall = 0

        for gen in range(int(self.params["generations"])):
            if len(self.capacity_cache) > 30_000:
                self.capacity_cache.clear()
            if len(self.feasible_cache) > 30_000:
                self.feasible_cache.clear()
            evaluated: List[Dict[str, Any]] = []
            improved_in_generation = False
            for chrom in population:
                cost, cover_set, feasible = self._evaluate(chrom)
                evaluated.append(
                    {
                        "chrom": chrom,
                        "cost": cost,
                        "cover_set": cover_set,
                        "feasible": feasible,
                    }
                )
                if cost < best_cost - 1e-9:
                    best_cost = cost
                    best_cover = set(cover_set)
                    improved_in_generation = True

            if improved_in_generation:
                stall = 0
            else:
                stall += 1

            evaluated.sort(key=lambda item: item["cost"])
            if not evaluated:
                break

            gen_best = evaluated[0]
            costs = [float(item["cost"]) for item in evaluated]
            feasible_count = sum(1 for item in evaluated if item["feasible"])
            self.history.append(
                {
                    "gen": gen,
                    "bestWeight": self._cover_weight(set(gen_best["cover_set"])),
                    "bestSize": len(gen_best["cover_set"]),
                    "feasible": bool(gen_best["feasible"]),
                    "avgCost": (sum(costs) / len(costs)) if costs else 0.0,
                    "feasibleRate": (feasible_count / len(evaluated)) if evaluated else 0.0,
                    "stall": stall,
                }
            )

            if stall >= int(self.params["stall_generations"]):
                break

            elite_size = min(int(self.params["elite_size"]), len(evaluated))
            elites = [
                self._copy_chromosome(item["chrom"])
                for item in evaluated[:elite_size]
            ]

            new_population = list(elites)
            target_size = int(self.params["population_size"])
            while len(new_population) < target_size:
                parent_a = self._tournament_select(evaluated)["chrom"]
                parent_b = self._tournament_select(evaluated)["chrom"]
                child = self._crossover(parent_a, parent_b)
                child = self._mutate(child)
                new_population.append(child)
            population = new_population

        return best_cover


def solve_hga_v2(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    pop_size: int,
    generations: int,
    seed: int = 42,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    solver = HGA_CCVC_V2(
        vertex_data=vertex_data,
        edge_data=edge_data,
        capacity_k=capacity_k,
        pop_size=pop_size,
        generations=generations,
        seed=seed,
        params=params,
    )
    best_cover = solver.run()
    return {
        "cover": best_cover,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "HGA-CCVC v2",
        "history": solver.history,
    }


@dataclass
class _HGAChromosomeV3:
    mask: List[int]
    fitness: float = float("inf")
    feasible: bool = False

    def copy(self) -> "_HGAChromosomeV3":
        return _HGAChromosomeV3(
            mask=list(self.mask),
            fitness=float(self.fitness),
            feasible=bool(self.feasible),
        )

    def size(self) -> int:
        return sum(1 for bit in self.mask if bit)

    def to_cover_set(self, index_to_node: Sequence[int]) -> Set[int]:
        return {
            int(index_to_node[idx])
            for idx, bit in enumerate(self.mask)
            if bit
        }


def _cover_components_from_mask(mask: Sequence[int], adjacency: Dict[int, Set[int]]) -> List[Set[int]]:
    cover_nodes = {idx for idx, bit in enumerate(mask) if bit}
    if not cover_nodes:
        return []
    components: List[Set[int]] = []
    remaining = set(cover_nodes)
    while remaining:
        start = next(iter(remaining))
        remaining.remove(start)
        component = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbor in adjacency.get(node, set()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def _is_connected_mask(mask: Sequence[int], adjacency: Dict[int, Set[int]]) -> bool:
    cover_size = sum(1 for bit in mask if bit)
    if cover_size == 0:
        return False
    if cover_size == 1:
        return True
    components = _cover_components_from_mask(mask, adjacency)
    return len(components) <= 1


def _mask_uncovered_count(mask: Sequence[int], edge_data: Sequence[Tuple[int, int]]) -> int:
    return sum(
        1
        for u, v in edge_data
        if not mask[u] and not mask[v]
    )


def _shortest_path_between_sets(
    adjacency: Dict[int, Set[int]],
    source_nodes: Set[int],
    target_nodes: Set[int],
) -> List[int]:
    if not source_nodes or not target_nodes:
        return []
    queue: deque[int] = deque(source_nodes)
    prev: Dict[int, Optional[int]] = {node: None for node in source_nodes}
    while queue:
        current = queue.popleft()
        if current in target_nodes:
            path = [current]
            node = current
            while prev[node] is not None:
                node = int(prev[node])
                path.append(node)
            path.reverse()
            return path
        for neighbor in adjacency.get(current, set()):
            if neighbor in prev:
                continue
            prev[neighbor] = current
            queue.append(neighbor)
    return []


class _ConstraintHandlerV3:
    def is_feasible(
        self,
        mask: Sequence[int],
        edge_data: Sequence[Tuple[int, int]],
        adjacency: Dict[int, Set[int]],
        capacity_k: int,
    ) -> bool:
        if not any(mask):
            return False
        if _mask_uncovered_count(mask, edge_data) > 0:
            return False
        if not _is_connected_mask(mask, adjacency):
            return False
        cover_indices = {idx for idx, bit in enumerate(mask) if bit}
        if len(cover_indices) * capacity_k < len(edge_data):
            return False
        return _check_capacity_feasibility_raw(edge_data, cover_indices, capacity_k)

    def repair(
        self,
        mask: List[int],
        edge_data: Sequence[Tuple[int, int]],
        adjacency: Dict[int, Set[int]],
        weights: Sequence[float],
        capacity_k: int,
        rng: random.Random,
    ) -> List[int]:
        n = len(mask)
        if n == 0:
            return []

        if not any(mask):
            pick = min(range(n), key=lambda idx: weights[idx])
            mask[pick] = 1

        # Coverage repair
        for u, v in edge_data:
            if mask[u] or mask[v]:
                continue
            u_score = (len(adjacency.get(u, set())) + 1.0) / max(1e-9, weights[u])
            v_score = (len(adjacency.get(v, set())) + 1.0) / max(1e-9, weights[v])
            if abs(u_score - v_score) < 1e-12:
                mask[u if rng.random() < 0.5 else v] = 1
            elif u_score > v_score:
                mask[u] = 1
            else:
                mask[v] = 1

        # Capacity lower-bound repair
        min_cover_size = (len(edge_data) + capacity_k - 1) // capacity_k if capacity_k > 0 else n
        if sum(mask) < min_cover_size:
            candidates = [
                idx
                for idx in range(n)
                if not mask[idx]
            ]
            candidates.sort(
                key=lambda idx: (
                    weights[idx] / max(1, len(adjacency.get(idx, set()))),
                    weights[idx],
                )
            )
            for idx in candidates:
                if sum(mask) >= min_cover_size:
                    break
                mask[idx] = 1

        # Connectivity repair by adding shortest bridge paths
        safety = 0
        while safety < n:
            safety += 1
            components = _cover_components_from_mask(mask, adjacency)
            if len(components) <= 1:
                break
            base = components[0]
            merged = False
            for other in components[1:]:
                path = _shortest_path_between_sets(adjacency, base, other)
                if not path:
                    continue
                for idx in path:
                    mask[idx] = 1
                base = base.union(other).union(set(path))
                merged = True
                break
            if not merged:
                break

        # Lightweight pruning
        selected = [idx for idx, bit in enumerate(mask) if bit]
        selected.sort(key=lambda idx: weights[idx], reverse=True)
        for idx in selected[: min(20, len(selected))]:
            trial = list(mask)
            trial[idx] = 0
            if (
                _mask_uncovered_count(trial, edge_data) == 0
                and _is_connected_mask(trial, adjacency)
                and sum(trial) * capacity_k >= len(edge_data)
            ):
                trial_cover = {node for node, bit in enumerate(trial) if bit}
                if _check_capacity_feasibility_raw(edge_data, trial_cover, capacity_k):
                    mask = trial
        return [1 if bit else 0 for bit in mask]


def _tournament_select_v3(
    evaluated: Sequence[Tuple[_HGAChromosomeV3, float]],
    tournament_size: int,
    rng: random.Random,
) -> _HGAChromosomeV3:
    if not evaluated:
        return _HGAChromosomeV3(mask=[])
    k = max(1, min(int(tournament_size), len(evaluated)))
    sample = rng.sample(list(evaluated), k)
    return min(sample, key=lambda item: item[1])[0].copy()


def _saux_crossover_v3(
    parent1: _HGAChromosomeV3,
    parent2: _HGAChromosomeV3,
    adjacency: Dict[int, Set[int]],
    rng: random.Random,
) -> _HGAChromosomeV3:
    n = len(parent1.mask)
    child = [0] * n
    for idx in range(n):
        bit_a = parent1.mask[idx]
        bit_b = parent2.mask[idx]
        if bit_a == bit_b:
            child[idx] = bit_a
            continue
        neigh = adjacency.get(idx, set())
        score_a = sum(parent1.mask[nidx] for nidx in neigh)
        score_b = sum(parent2.mask[nidx] for nidx in neigh)
        if score_a == score_b:
            child[idx] = bit_a if rng.random() < 0.5 else bit_b
        else:
            child[idx] = bit_a if score_a > score_b else bit_b
    return _HGAChromosomeV3(mask=child)


def _mpccx_crossover_v3(
    parent1: _HGAChromosomeV3,
    parent2: _HGAChromosomeV3,
    rng: random.Random,
) -> _HGAChromosomeV3:
    n = len(parent1.mask)
    if n <= 2:
        return parent1.copy() if rng.random() < 0.5 else parent2.copy()
    p1 = rng.randrange(1, n - 1)
    p2 = rng.randrange(p1, n)
    child = (
        parent1.mask[:p1]
        + parent2.mask[p1:p2]
        + parent1.mask[p2:]
    )
    return _HGAChromosomeV3(mask=child)


def _caec_crossover_v3(
    parent1: _HGAChromosomeV3,
    parent2: _HGAChromosomeV3,
    edge_count: int,
    capacity_k: int,
    weights: Sequence[float],
    adjacency: Dict[int, Set[int]],
    rng: random.Random,
) -> _HGAChromosomeV3:
    n = len(parent1.mask)
    child = [1 if parent1.mask[i] and parent2.mask[i] else 0 for i in range(n)]
    required = (edge_count + capacity_k - 1) // capacity_k if capacity_k > 0 else n
    if sum(child) < required:
        pool = [
            idx
            for idx in range(n)
            if (parent1.mask[idx] or parent2.mask[idx]) and not child[idx]
        ]
        pool.sort(
            key=lambda idx: (
                weights[idx] / max(1, len(adjacency.get(idx, set()))),
                weights[idx],
            )
        )
        for idx in pool:
            if sum(child) >= required:
                break
            child[idx] = 1
    while sum(child) < required:
        idx = rng.randrange(n)
        child[idx] = 1
    return _HGAChromosomeV3(mask=child)


def _avsm_mutate_v3(
    chromosome: _HGAChromosomeV3,
    temperature: float,
    initial_temperature: float,
    rng: random.Random,
) -> _HGAChromosomeV3:
    chrom = chromosome.copy()
    if not chrom.mask:
        return chrom
    ratio = min(1.0, max(0.0, temperature / max(1e-9, initial_temperature)))
    flip_prob = min(0.35, 0.02 + 0.18 * ratio)
    for idx in range(len(chrom.mask)):
        if rng.random() < flip_prob:
            chrom.mask[idx] = 0 if chrom.mask[idx] else 1
    return chrom


def _cgm_mutate_v3(
    chromosome: _HGAChromosomeV3,
    adjacency: Dict[int, Set[int]],
    rng: random.Random,
) -> _HGAChromosomeV3:
    chrom = chromosome.copy()
    if not chrom.mask:
        return chrom
    selected = [idx for idx, bit in enumerate(chrom.mask) if bit]
    if not selected:
        chrom.mask[rng.randrange(len(chrom.mask))] = 1
        return chrom
    src = selected[rng.randrange(len(selected))]
    neighbors = list(adjacency.get(src, set()))
    if neighbors:
        chrom.mask[neighbors[rng.randrange(len(neighbors))]] = 1
    if rng.random() < 0.2 and len(selected) > 1:
        chrom.mask[src] = 0
    return chrom


def _crm_mutate_v3(
    chromosome: _HGAChromosomeV3,
    edge_count: int,
    capacity_k: int,
    weights: Sequence[float],
    rng: random.Random,
) -> _HGAChromosomeV3:
    chrom = chromosome.copy()
    if not chrom.mask:
        return chrom
    required = (edge_count + capacity_k - 1) // capacity_k if capacity_k > 0 else len(chrom.mask)
    chosen = [idx for idx, bit in enumerate(chrom.mask) if bit]
    if len(chosen) < required:
        pool = [idx for idx, bit in enumerate(chrom.mask) if not bit]
        rng.shuffle(pool)
        for idx in pool:
            if len(chosen) >= required:
                break
            chrom.mask[idx] = 1
            chosen.append(idx)
    elif len(chosen) > required and rng.random() < 0.5:
        remove = max(chosen, key=lambda idx: weights[idx])
        chrom.mask[remove] = 0
    return chrom


class _AdaptiveLocalSearchV3:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.frequency = 0.25

    def should_apply(self, generation: int, total_generations: int) -> bool:
        total = max(1, int(total_generations))
        progress = (generation + 1) / total
        self.frequency = 0.2 + 0.25 * (1.0 - progress)
        return generation % 2 == 0 or progress > 0.7

    def apply(
        self,
        chromosome: _HGAChromosomeV3,
        edge_data: Sequence[Tuple[int, int]],
        adjacency: Dict[int, Set[int]],
        weights: Sequence[float],
        capacity_k: int,
        handler: _ConstraintHandlerV3,
        intensity: int,
    ) -> _HGAChromosomeV3:
        chrom = chromosome.copy()
        moves = max(1, int(intensity))
        for _ in range(moves):
            selected = [idx for idx, bit in enumerate(chrom.mask) if bit]
            if not selected:
                break
            selected.sort(key=lambda idx: weights[idx], reverse=True)
            improved = False
            for remove_idx in selected[: min(6, len(selected))]:
                trial = chrom.mask[:]
                trial[remove_idx] = 0
                if handler.is_feasible(trial, edge_data, adjacency, capacity_k):
                    chrom.mask = trial
                    improved = True
                    break
                candidates = sorted(
                    (idx for idx in adjacency.get(remove_idx, set()) if not trial[idx]),
                    key=lambda idx: weights[idx],
                )
                for add_idx in candidates[:4]:
                    swap_trial = trial[:]
                    swap_trial[add_idx] = 1
                    if handler.is_feasible(swap_trial, edge_data, adjacency, capacity_k):
                        chrom.mask = swap_trial
                        improved = True
                        break
                if improved:
                    break
            if not improved:
                break
        return chrom


class HGA_CCVC_V3:
    """
    New Hybrid Genetic Algorithm for CCVC (v3).
    """

    def __init__(
        self,
        vertex_data: Sequence[Dict[str, Any]],
        edge_data: Sequence[Tuple[int, int]],
        capacity_k: int,
        pop_size: int,
        generations: int,
        seed: int = 42,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        if capacity_k is None or capacity_k <= 0:
            raise ValueError("capacity_k must be positive for HGA-V3.")

        self.capacity_k = int(capacity_k)
        self.rng = random.Random(seed)
        self.seed = seed

        ids = [int(v["id"]) for v in vertex_data]
        self.index_to_node = sorted(ids)
        self.node_to_index = {node_id: idx for idx, node_id in enumerate(self.index_to_node)}
        self.n = len(self.index_to_node)
        self.weights = [0.0 for _ in range(self.n)]
        input_weights = {int(v["id"]): float(v["weight"]) for v in vertex_data}
        for idx, node_id in enumerate(self.index_to_node):
            self.weights[idx] = float(input_weights.get(node_id, 1.0))

        normalized: Set[Tuple[int, int]] = set()
        self.edge_data: List[Tuple[int, int]] = []
        self.adjacency: Dict[int, Set[int]] = {idx: set() for idx in range(self.n)}
        for raw_u, raw_v in edge_data:
            u = int(raw_u)
            v = int(raw_v)
            if u == v or u not in self.node_to_index or v not in self.node_to_index:
                continue
            ui = self.node_to_index[u]
            vi = self.node_to_index[v]
            edge = (ui, vi) if ui < vi else (vi, ui)
            if edge in normalized:
                continue
            normalized.add(edge)
            self.edge_data.append(edge)
            self.adjacency[edge[0]].add(edge[1])
            self.adjacency[edge[1]].add(edge[0])

        self.params = self._default_params(pop_size, generations, params)
        self.constraint_handler = _ConstraintHandlerV3()
        self.local_search = _AdaptiveLocalSearchV3(self.rng)
        self.history: List[Dict[str, Any]] = []

    def _default_params(
        self,
        pop_size: int,
        generations: int,
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        defaults: Dict[str, Any] = {
            "population_size": max(2, int(pop_size)),
            "generations": max(1, int(generations)),
            "elite_size": 3,
            "tournament_size": 3,
            "crossover_prob": 0.8,
            "mutation_prob": 0.2,
            "local_search_intensity": 3,
            "initial_temperature": 100.0,
            "cooling_rate": 0.95,
            "diversity_threshold": 0.15,
            "restart_after_stall": 20,
            "penalty_weights": {
                "coverage": 1000.0,
                "connectivity": 500.0,
                "capacity": 100.0,
            },
            "crossover_types": ["saux", "mpccx", "caec"],
            "mutation_types": ["avsm", "cgm", "crm"],
            "verbose": False,
            "log_interval": 10,
        }
        if params:
            merged = dict(defaults)
            for key, value in params.items():
                if key == "penalty_weights" and isinstance(value, dict):
                    penalties = dict(defaults["penalty_weights"])
                    penalties.update(value)
                    merged["penalty_weights"] = penalties
                else:
                    merged[key] = value
            defaults = merged

        defaults["population_size"] = max(2, int(defaults["population_size"]))
        defaults["generations"] = max(1, int(defaults["generations"]))
        defaults["elite_size"] = max(1, int(defaults["elite_size"]))
        defaults["tournament_size"] = max(1, int(defaults["tournament_size"]))
        defaults["local_search_intensity"] = max(1, int(defaults["local_search_intensity"]))
        defaults["restart_after_stall"] = max(1, int(defaults["restart_after_stall"]))
        defaults["log_interval"] = max(1, int(defaults["log_interval"]))
        defaults["crossover_types"] = list(defaults["crossover_types"]) or ["saux"]
        defaults["mutation_types"] = list(defaults["mutation_types"]) or ["avsm"]
        return defaults

    def _initialize_population(self) -> List[_HGAChromosomeV3]:
        population: List[_HGAChromosomeV3] = []
        pop_size = int(self.params["population_size"])

        # Strategy 0: Random binary masks (50%)
        for _ in range(int(pop_size * 0.5)):
            mask = [1 if self.rng.random() < 0.5 else 0 for _ in range(self.n)]
            population.append(_HGAChromosomeV3(mask))

        # Strategy 1: Degree-biased (30%)
        degrees = {idx: len(self.adjacency.get(idx, set())) for idx in range(self.n)}
        max_degree = max(degrees.values()) if degrees else 1
        for _ in range(int(pop_size * 0.3)):
            mask: List[int] = []
            for idx in range(self.n):
                prob = (degrees.get(idx, 0) / max(1, max_degree)) ** 2
                mask.append(1 if self.rng.random() < prob else 0)
            population.append(_HGAChromosomeV3(mask))

        # Strategy 2: Sparse random (10%)
        for _ in range(int(pop_size * 0.1)):
            mask = [1 if self.rng.random() < 0.2 else 0 for _ in range(self.n)]
            population.append(_HGAChromosomeV3(mask))

        # Strategy 3: Dense random (10%)
        for _ in range(int(pop_size * 0.1)):
            mask = [1 if self.rng.random() < 0.6 else 0 for _ in range(self.n)]
            population.append(_HGAChromosomeV3(mask))

        while len(population) < pop_size:
            mask = [1 if self.rng.random() < 0.5 else 0 for _ in range(self.n)]
            population.append(_HGAChromosomeV3(mask))

        return population[:pop_size]

    def _compute_fitness(self, chromosome: _HGAChromosomeV3, generation: int) -> float:
        mask = chromosome.mask
        n = len(mask)
        if n == 0:
            return float("inf")

        weight = sum(self.weights[idx] for idx in range(n) if mask[idx])
        size = sum(mask)
        uncovered = _mask_uncovered_count(mask, self.edge_data)
        connected = _is_connected_mask(mask, self.adjacency) if size > 0 else False
        cap_violation = max(0, len(self.edge_data) - size * self.capacity_k)

        decay = max(0.05, 1.0 - (generation / max(1, int(self.params["generations"]))))
        alpha = float(self.params["penalty_weights"]["coverage"]) * decay * 0.1
        beta = float(self.params["penalty_weights"]["connectivity"]) * decay * 0.01
        gamma = float(self.params["penalty_weights"]["capacity"]) * decay * 0.01

        penalty = (
            alpha * uncovered * 100.0
            + beta * (0.0 if connected else 1.0) * 1000.0
            + gamma * cap_violation * 10.0
        )
        return weight * 1000.0 + size + penalty

    def _crossover(
        self,
        parent1: _HGAChromosomeV3,
        parent2: _HGAChromosomeV3,
        xo_type: str,
    ) -> _HGAChromosomeV3:
        xo = str(xo_type).strip().lower()
        if xo == "saux":
            return _saux_crossover_v3(parent1, parent2, self.adjacency, self.rng)
        if xo == "mpccx":
            return _mpccx_crossover_v3(parent1, parent2, self.rng)
        if xo == "caec":
            return _caec_crossover_v3(
                parent1,
                parent2,
                len(self.edge_data),
                self.capacity_k,
                self.weights,
                self.adjacency,
                self.rng,
            )
        return parent1.copy()

    def _mutate(
        self,
        chromosome: _HGAChromosomeV3,
        mut_type: str,
        temperature: float,
    ) -> _HGAChromosomeV3:
        mut = str(mut_type).strip().lower()
        if mut == "avsm":
            return _avsm_mutate_v3(
                chromosome,
                temperature=temperature,
                initial_temperature=float(self.params["initial_temperature"]),
                rng=self.rng,
            )
        if mut == "cgm":
            return _cgm_mutate_v3(chromosome, self.adjacency, self.rng)
        if mut == "crm":
            return _crm_mutate_v3(
                chromosome,
                edge_count=len(self.edge_data),
                capacity_k=self.capacity_k,
                weights=self.weights,
                rng=self.rng,
            )
        return chromosome.copy()

    def _compute_diversity(self, population: Sequence[_HGAChromosomeV3]) -> float:
        if len(population) < 2:
            return 1.0
        n = len(population[0].mask)
        if n == 0:
            return 0.0
        total_dist = 0.0
        count = 0
        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                dist = sum(
                    1
                    for a, b in zip(population[i].mask, population[j].mask)
                    if a != b
                )
                total_dist += dist / n
                count += 1
        return total_dist / count if count > 0 else 0.0

    def _inject_diversity(
        self,
        population: Sequence[_HGAChromosomeV3],
        elites: Sequence[_HGAChromosomeV3],
    ) -> List[_HGAChromosomeV3]:
        new_pop = [elite.copy() for elite in elites]
        while len(new_pop) < len(population):
            mask = [1 if self.rng.random() < 0.5 else 0 for _ in range(self.n)]
            new_pop.append(_HGAChromosomeV3(mask))
        return new_pop

    def _partial_restart(
        self,
        population: Sequence[_HGAChromosomeV3],
        elites: Sequence[_HGAChromosomeV3],
    ) -> List[_HGAChromosomeV3]:
        new_pop = [elite.copy() for elite in elites]
        while len(new_pop) < max(2, int(self.params["population_size"])):
            mask = [1 if self.rng.random() < 0.5 else 0 for _ in range(self.n)]
            new_pop.append(_HGAChromosomeV3(mask))
        return new_pop[: len(population)]

    def _log_generation(
        self,
        generation: int,
        evaluated: Sequence[Tuple[_HGAChromosomeV3, float]],
        best_chrom: Optional[_HGAChromosomeV3],
        diversity: float,
        stall_count: int,
    ) -> None:
        if not evaluated:
            return
        best_fit = float(evaluated[0][1])
        avg_fit = sum(float(fit) for _, fit in evaluated) / len(evaluated)
        feasible_count = sum(1 for chrom, _ in evaluated if chrom.feasible)
        best_size = int(best_chrom.size()) if best_chrom is not None else 0
        best_weight = 0.0
        if best_chrom is not None:
            best_weight = sum(
                self.weights[idx]
                for idx, bit in enumerate(best_chrom.mask)
                if bit
            )

        self.history.append(
            {
                "gen": generation,
                "bestCost": best_fit,
                "bestWeight": best_weight,
                "bestSize": best_size,
                "feasible": bool(feasible_count > 0),
                "feasibleCount": feasible_count,
                "feasibleRate": feasible_count / len(evaluated),
                "avgCost": avg_fit,
                "diversity": diversity,
                "stall": stall_count,
            }
        )

    def run(self) -> Set[int]:
        population = self._initialize_population()
        best_solution: Set[int] = set()
        best_fitness = float("inf")
        best_chrom: Optional[_HGAChromosomeV3] = None
        stall_count = 0
        temperature = float(self.params["initial_temperature"])
        verbose = bool(self.params.get("verbose", False))
        log_interval = max(1, int(self.params.get("log_interval", 10)))

        for generation in range(int(self.params["generations"])):
            generation_improved = False
            evaluated: List[Tuple[_HGAChromosomeV3, float]] = []

            for chrom in population:
                chrom.mask = self.constraint_handler.repair(
                    chrom.mask[:],
                    self.edge_data,
                    self.adjacency,
                    self.weights,
                    self.capacity_k,
                    self.rng,
                )
                fitness = self._compute_fitness(chrom, generation)
                chrom.fitness = fitness
                chrom.feasible = self.constraint_handler.is_feasible(
                    chrom.mask,
                    self.edge_data,
                    self.adjacency,
                    self.capacity_k,
                )
                evaluated.append((chrom, fitness))

                if fitness < best_fitness - 1e-9:
                    best_fitness = fitness
                    best_chrom = chrom.copy()
                    best_solution = chrom.to_cover_set(self.index_to_node)
                    generation_improved = True

            stall_count = 0 if generation_improved else stall_count + 1
            evaluated.sort(key=lambda item: item[1])
            if not evaluated:
                break

            elite_count = min(int(self.params["elite_size"]), len(evaluated))
            elites = [chrom.copy() for chrom, _ in evaluated[:elite_count]]

            # Always local search on elites.
            for idx in range(len(elites)):
                elites[idx] = self.local_search.apply(
                    elites[idx],
                    self.edge_data,
                    self.adjacency,
                    self.weights,
                    self.capacity_k,
                    self.constraint_handler,
                    int(self.params["local_search_intensity"]),
                )

            # Adaptive local search on remainder.
            if self.local_search.should_apply(generation, int(self.params["generations"])):
                for idx in range(elite_count, len(population)):
                    if self.rng.random() < self.local_search.frequency:
                        population[idx] = self.local_search.apply(
                            population[idx],
                            self.edge_data,
                            self.adjacency,
                            self.weights,
                            self.capacity_k,
                            self.constraint_handler,
                            int(self.params["local_search_intensity"]),
                        )

            # Reproduction
            offspring: List[_HGAChromosomeV3] = []
            target_size = int(self.params["population_size"]) - elite_count
            while len(offspring) < target_size:
                parent1 = _tournament_select_v3(
                    evaluated,
                    int(self.params["tournament_size"]),
                    self.rng,
                )
                parent2 = _tournament_select_v3(
                    evaluated,
                    int(self.params["tournament_size"]),
                    self.rng,
                )
                if self.rng.random() < float(self.params["crossover_prob"]):
                    xo_type = self.rng.choice(list(self.params["crossover_types"]))
                    child = self._crossover(parent1, parent2, xo_type)
                else:
                    child = parent1 if self.rng.random() < 0.5 else parent2
                    child = child.copy()

                if self.rng.random() < float(self.params["mutation_prob"]):
                    mut_type = self.rng.choice(list(self.params["mutation_types"]))
                    child = self._mutate(child, mut_type, temperature)
                offspring.append(child)

            population = elites + offspring

            diversity = self._compute_diversity(population)
            if diversity < float(self.params["diversity_threshold"]):
                population = self._inject_diversity(population, elites)

            if stall_count >= int(self.params["restart_after_stall"]):
                if verbose:
                    print(f"[HGA-V3] Restart at gen {generation + 1} (stall={stall_count})")
                population = self._partial_restart(population, elites)
                stall_count = 0

            temperature *= float(self.params["cooling_rate"])
            if verbose and (generation == 0 or (generation + 1) % log_interval == 0):
                best_cost = float(evaluated[0][1])
                avg_cost = sum(fit for _, fit in evaluated) / len(evaluated)
                feasible_count = sum(1 for chrom, _ in evaluated if chrom.feasible)
                print(
                    f"[HGA-V3] Gen {generation + 1}: best={best_cost:.2f}, "
                    f"avg={avg_cost:.2f}, feasible={feasible_count}/{len(evaluated)}, "
                    f"diversity={diversity:.3f}, stall={stall_count}"
                )

            self._log_generation(generation, evaluated, best_chrom, diversity, stall_count)

        return best_solution


def solve_hga_v3(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    pop_size: int,
    generations: int,
    seed: int = 42,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    solver = HGA_CCVC_V3(
        vertex_data=vertex_data,
        edge_data=edge_data,
        capacity_k=capacity_k,
        pop_size=pop_size,
        generations=generations,
        seed=seed,
        params=params,
    )
    best_cover = solver.run()
    return {
        "cover": best_cover,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "HGA-CCVC v3",
        "history": solver.history,
    }


class NSGA_V2_CCVC:
    """
    NSGA-II based solver for CCVC.
    Objectives:
    1) Minimize total weight
    2) Minimize cover size
    """

    def __init__(
        self,
        vertex_data: Sequence[Dict[str, Any]],
        edge_data: Sequence[Tuple[int, int]],
        capacity_k: int,
        pop_size: int,
        generations: int,
        seed: int = 42,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        if capacity_k is None or capacity_k <= 0:
            raise ValueError("capacity_k must be positive for NSGA-V2.")
        self.capacity_k = int(capacity_k)
        self.rng = random.Random(seed)
        self.seed = seed

        ids = [int(v["id"]) for v in vertex_data]
        self.index_to_node = sorted(ids)
        self.node_to_index = {node_id: idx for idx, node_id in enumerate(self.index_to_node)}
        self.n = len(self.index_to_node)

        weight_map = {int(v["id"]): float(v["weight"]) for v in vertex_data}
        self.weights = [weight_map.get(node_id, 1.0) for node_id in self.index_to_node]

        self.edge_data: List[Tuple[int, int]] = []
        self.adjacency: Dict[int, Set[int]] = {idx: set() for idx in range(self.n)}
        seen_edges: Set[Tuple[int, int]] = set()
        for raw_u, raw_v in edge_data:
            u = int(raw_u)
            v = int(raw_v)
            if u == v or u not in self.node_to_index or v not in self.node_to_index:
                continue
            ui = self.node_to_index[u]
            vi = self.node_to_index[v]
            edge = (ui, vi) if ui < vi else (vi, ui)
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            self.edge_data.append(edge)
            self.adjacency[edge[0]].add(edge[1])
            self.adjacency[edge[1]].add(edge[0])

        self.params = self._default_params(pop_size, generations, params)
        self.constraint_handler = _ConstraintHandlerV3()
        self.local_search = _AdaptiveLocalSearchV3(self.rng)
        self.local_search.frequency = float(self.params.get("local_search_rate", 0.2))
        self.history: List[Dict[str, Any]] = []
        self.pareto_front: List[Dict[str, Any]] = []

    def _default_params(
        self,
        pop_size: int,
        generations: int,
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        defaults: Dict[str, Any] = {
            "population_size": max(2, int(pop_size)),
            "generations": max(1, int(generations)),
            "tournament_size": 2,
            "crossover_prob": 0.8,
            "mutation_prob": 0.2,
            "crossover_types": ["saux", "mpccx", "caec"],
            "mutation_types": ["avsm", "cgm", "crm"],
            "repair": True,
            "local_search_rate": 0.2,
            "local_search_intensity": 4,
            "initial_temperature": 100.0,
            "cooling_rate": 0.95,
            "selection_method": "weighted_sum",
            "objective_weights": (1.0, 1.0),
            "verbose": False,
            "log_interval": 10,
        }
        if params:
            defaults.update(params)
        defaults["population_size"] = max(2, int(defaults["population_size"]))
        defaults["generations"] = max(1, int(defaults["generations"]))
        defaults["tournament_size"] = max(1, int(defaults["tournament_size"]))
        defaults["local_search_intensity"] = max(1, int(defaults["local_search_intensity"]))
        defaults["log_interval"] = max(1, int(defaults["log_interval"]))
        defaults["crossover_types"] = list(defaults.get("crossover_types") or ["saux"])
        defaults["mutation_types"] = list(defaults.get("mutation_types") or ["avsm"])
        return defaults

    def run(self) -> Set[int]:
        population = self._initialize_population()
        evaluated = self._evaluate_population(population)
        fronts = self._fast_nondominated_sort(evaluated)
        self._assign_crowding_all(fronts)
        evaluated = self._flatten_fronts(fronts)

        verbose = bool(self.params.get("verbose", False))
        log_interval = max(1, int(self.params.get("log_interval", 10)))

        for generation in range(int(self.params["generations"])):
            offspring = self._make_offspring(evaluated, generation)
            evaluated_offspring = self._evaluate_population(offspring)

            combined = evaluated + evaluated_offspring
            fronts = self._fast_nondominated_sort(combined)
            self._assign_crowding_all(fronts)

            selected = self._select_next_population(fronts, int(self.params["population_size"]))
            population = [item["chrom"] for item in selected]

            # Recompute rank/crowding on selected pop.
            fronts = self._fast_nondominated_sort(selected)
            self._assign_crowding_all(fronts)
            evaluated = self._flatten_fronts(fronts)

            self.pareto_front = fronts[0] if fronts else []
            if verbose and (generation == 0 or (generation + 1) % log_interval == 0):
                self._print_log(generation, self.pareto_front)
            self._log_generation(generation, self.pareto_front, evaluated)

        final_front = self.pareto_front or (fronts[0] if fronts else [])
        chosen = self._select_compromise(final_front)
        return chosen["chrom"].to_cover_set(self.index_to_node) if chosen else set()

    def _initialize_population(self) -> List[_HGAChromosomeV3]:
        population: List[_HGAChromosomeV3] = []
        pop_size = int(self.params["population_size"])

        # Strategy 0: Random (50%)
        for _ in range(int(pop_size * 0.5)):
            mask = [1 if self.rng.random() < 0.5 else 0 for _ in range(self.n)]
            population.append(_HGAChromosomeV3(mask))

        # Strategy 1: Degree-biased (30%)
        degrees = {idx: len(self.adjacency.get(idx, set())) for idx in range(self.n)}
        max_degree = max(degrees.values()) if degrees else 1
        for _ in range(int(pop_size * 0.3)):
            mask: List[int] = []
            for idx in range(self.n):
                prob = (degrees.get(idx, 0) / max(1, max_degree)) ** 2
                mask.append(1 if self.rng.random() < prob else 0)
            population.append(_HGAChromosomeV3(mask))

        # Strategy 2: Sparse random (10%)
        for _ in range(int(pop_size * 0.1)):
            mask = [1 if self.rng.random() < 0.2 else 0 for _ in range(self.n)]
            population.append(_HGAChromosomeV3(mask))

        # Strategy 3: Dense random (10%)
        for _ in range(int(pop_size * 0.1)):
            mask = [1 if self.rng.random() < 0.6 else 0 for _ in range(self.n)]
            population.append(_HGAChromosomeV3(mask))

        while len(population) < pop_size:
            mask = [1 if self.rng.random() < 0.5 else 0 for _ in range(self.n)]
            population.append(_HGAChromosomeV3(mask))
        return population[:pop_size]

    def _evaluate_population(self, population: Sequence[_HGAChromosomeV3]) -> List[Dict[str, Any]]:
        evaluated: List[Dict[str, Any]] = []
        for chrom in population:
            candidate = chrom.copy()
            if bool(self.params.get("repair", True)):
                candidate.mask = self.constraint_handler.repair(
                    candidate.mask[:],
                    self.edge_data,
                    self.adjacency,
                    self.weights,
                    self.capacity_k,
                    self.rng,
                )

            weight, size = self._compute_objectives(candidate)
            feasible = self.constraint_handler.is_feasible(
                candidate.mask,
                self.edge_data,
                self.adjacency,
                self.capacity_k,
            )
            violation = self._constraint_violation(candidate.mask)
            candidate.feasible = feasible
            evaluated.append(
                {
                    "chrom": candidate,
                    "weight": float(weight),
                    "size": int(size),
                    "feasible": bool(feasible),
                    "violation": float(violation),
                    "rank": None,
                    "crowding": 0.0,
                }
            )
        return evaluated

    def _compute_objectives(self, chrom: _HGAChromosomeV3) -> Tuple[float, int]:
        mask = chrom.mask
        weight = sum(self.weights[idx] for idx in range(len(mask)) if mask[idx] == 1)
        size = sum(mask)
        return float(weight), int(size)

    def _constraint_violation(self, mask: Sequence[int]) -> float:
        uncovered = _mask_uncovered_count(mask, self.edge_data)
        connected = _is_connected_mask(mask, self.adjacency) if any(mask) else False
        cover_indices = {idx for idx, bit in enumerate(mask) if bit}
        cap_lb_violation = max(0, len(self.edge_data) - len(cover_indices) * self.capacity_k)
        cap_exact_violation = 0
        if uncovered == 0 and connected and cap_lb_violation == 0:
            cap_ok = _check_capacity_feasibility_raw(self.edge_data, cover_indices, self.capacity_k)
            cap_exact_violation = 0 if cap_ok else 1
        return float(uncovered + (0 if connected else 1) + cap_lb_violation + cap_exact_violation)

    def _dominates(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        if a["feasible"] and not b["feasible"]:
            return True
        if not a["feasible"] and b["feasible"]:
            return False
        if not a["feasible"] and not b["feasible"]:
            return a["violation"] < b["violation"]

        better_or_equal = a["weight"] <= b["weight"] and a["size"] <= b["size"]
        strictly_better = a["weight"] < b["weight"] or a["size"] < b["size"]
        return bool(better_or_equal and strictly_better)

    def _fast_nondominated_sort(self, items: Sequence[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        n = len(items)
        if n == 0:
            return []
        domination_sets: List[List[int]] = [[] for _ in range(n)]
        dominated_count = [0 for _ in range(n)]
        fronts: List[List[int]] = [[]]

        for p in range(n):
            for q in range(n):
                if p == q:
                    continue
                if self._dominates(items[p], items[q]):
                    domination_sets[p].append(q)
                elif self._dominates(items[q], items[p]):
                    dominated_count[p] += 1
            if dominated_count[p] == 0:
                items[p]["rank"] = 0
                fronts[0].append(p)

        idx = 0
        while idx < len(fronts) and fronts[idx]:
            next_front: List[int] = []
            for p in fronts[idx]:
                for q in domination_sets[p]:
                    dominated_count[q] -= 1
                    if dominated_count[q] == 0:
                        items[q]["rank"] = idx + 1
                        next_front.append(q)
            idx += 1
            fronts.append(next_front)

        return [[items[item_idx] for item_idx in front] for front in fronts if front]

    def _assign_crowding_all(self, fronts: Sequence[List[Dict[str, Any]]]) -> None:
        for front in fronts:
            self._assign_crowding_distance(front)

    def _assign_crowding_distance(self, front: List[Dict[str, Any]]) -> None:
        if not front:
            return
        for item in front:
            item["crowding"] = 0.0
        if len(front) == 1:
            front[0]["crowding"] = float("inf")
            return
        objectives = ("weight", "size")
        for key in objectives:
            front.sort(key=lambda item: item[key])
            front[0]["crowding"] = float("inf")
            front[-1]["crowding"] = float("inf")
            min_val = float(front[0][key])
            max_val = float(front[-1][key])
            span = max_val - min_val
            if abs(span) <= 1e-12:
                continue
            for idx in range(1, len(front) - 1):
                prev_val = float(front[idx - 1][key])
                next_val = float(front[idx + 1][key])
                front[idx]["crowding"] += (next_val - prev_val) / span

    def _flatten_fronts(self, fronts: Sequence[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        return [item for front in fronts for item in front]

    def _tournament_select(self, evaluated: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        a = evaluated[self.rng.randrange(len(evaluated))]
        b = evaluated[self.rng.randrange(len(evaluated))]
        if a["rank"] < b["rank"]:
            return a
        if b["rank"] < a["rank"]:
            return b
        if a["crowding"] > b["crowding"]:
            return a
        if b["crowding"] > a["crowding"]:
            return b
        return a if self.rng.random() < 0.5 else b

    def _make_offspring(self, evaluated: Sequence[Dict[str, Any]], generation: int) -> List[_HGAChromosomeV3]:
        offspring: List[_HGAChromosomeV3] = []
        target = int(self.params["population_size"])
        crossover_prob = float(self.params["crossover_prob"])
        mutation_prob = float(self.params["mutation_prob"])
        local_search_rate = float(self.params.get("local_search_rate", 0.0))

        while len(offspring) < target:
            parent1 = self._tournament_select(evaluated)
            parent2 = self._tournament_select(evaluated)

            if self.rng.random() < crossover_prob:
                xo_type = self.rng.choice(list(self.params["crossover_types"]))
                child = self._crossover(parent1["chrom"], parent2["chrom"], xo_type)
            else:
                child = parent1["chrom"].copy() if self.rng.random() < 0.5 else parent2["chrom"].copy()

            if self.rng.random() < mutation_prob:
                mut_type = self.rng.choice(list(self.params["mutation_types"]))
                child = self._mutate(child, mut_type, generation)

            if bool(self.params.get("repair", True)):
                child.mask = self.constraint_handler.repair(
                    child.mask[:],
                    self.edge_data,
                    self.adjacency,
                    self.weights,
                    self.capacity_k,
                    self.rng,
                )

            if local_search_rate > 0.0 and self.rng.random() < local_search_rate:
                child = self.local_search.apply(
                    child,
                    self.edge_data,
                    self.adjacency,
                    self.weights,
                    self.capacity_k,
                    self.constraint_handler,
                    int(self.params["local_search_intensity"]),
                )
            offspring.append(child)
        return offspring

    def _select_next_population(
        self,
        fronts: Sequence[List[Dict[str, Any]]],
        pop_size: int,
    ) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        for front in fronts:
            if len(selected) + len(front) <= pop_size:
                selected.extend(front)
                continue
            remaining = pop_size - len(selected)
            front_sorted = sorted(front, key=lambda item: item["crowding"], reverse=True)
            selected.extend(front_sorted[:remaining])
            break
        return selected

    def _crossover(
        self,
        parent1: _HGAChromosomeV3,
        parent2: _HGAChromosomeV3,
        xo_type: str,
    ) -> _HGAChromosomeV3:
        xo = str(xo_type).strip().lower()
        if xo == "saux":
            return _saux_crossover_v3(parent1, parent2, self.adjacency, self.rng)
        if xo == "mpccx":
            return _mpccx_crossover_v3(parent1, parent2, self.rng)
        if xo == "caec":
            return _caec_crossover_v3(
                parent1,
                parent2,
                len(self.edge_data),
                self.capacity_k,
                self.weights,
                self.adjacency,
                self.rng,
            )
        return parent1.copy()

    def _mutate(
        self,
        chromosome: _HGAChromosomeV3,
        mut_type: str,
        generation: int,
    ) -> _HGAChromosomeV3:
        temperature = max(
            1.0,
            float(self.params.get("initial_temperature", 100.0))
            * (float(self.params.get("cooling_rate", 0.95)) ** generation),
        )
        mut = str(mut_type).strip().lower()
        if mut == "avsm":
            return _avsm_mutate_v3(
                chromosome,
                temperature=temperature,
                initial_temperature=float(self.params.get("initial_temperature", 100.0)),
                rng=self.rng,
            )
        if mut == "cgm":
            return _cgm_mutate_v3(chromosome, self.adjacency, self.rng)
        if mut == "crm":
            return _crm_mutate_v3(
                chromosome,
                edge_count=len(self.edge_data),
                capacity_k=self.capacity_k,
                weights=self.weights,
                rng=self.rng,
            )
        return chromosome.copy()

    def _select_compromise(self, front: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not front:
            return None
        method = str(self.params.get("selection_method", "weighted_sum")).strip().lower()
        if method == "min_weight":
            return min(front, key=lambda item: (item["weight"], item["size"]))
        if method == "min_size":
            return min(front, key=lambda item: (item["size"], item["weight"]))

        objective_weights = self.params.get("objective_weights", (1.0, 1.0))
        w_weight = float(objective_weights[0]) if len(objective_weights) > 0 else 1.0
        w_size = float(objective_weights[1]) if len(objective_weights) > 1 else 1.0

        weight_values = [float(item["weight"]) for item in front]
        size_values = [float(item["size"]) for item in front]
        w_min, w_max = min(weight_values), max(weight_values)
        s_min, s_max = min(size_values), max(size_values)

        def norm(value: float, min_value: float, max_value: float) -> float:
            span = max_value - min_value
            if abs(span) <= 1e-12:
                return 0.0
            return (value - min_value) / span

        def score(item: Dict[str, Any]) -> float:
            return (
                w_weight * norm(float(item["weight"]), w_min, w_max)
                + w_size * norm(float(item["size"]), s_min, s_max)
            )

        return min(front, key=lambda item: (score(item), item["weight"], item["size"]))

    def _print_log(self, generation: int, front: Sequence[Dict[str, Any]]) -> None:
        if not front:
            return
        best_weight = min(float(item["weight"]) for item in front)
        best_size = min(int(item["size"]) for item in front)
        print(
            f"[NSGA-V2] Gen {generation + 1}: pareto={len(front)} "
            f"min_weight={best_weight:.2f} min_size={best_size}"
        )

    def _log_generation(
        self,
        generation: int,
        front: Sequence[Dict[str, Any]],
        evaluated: Sequence[Dict[str, Any]],
    ) -> None:
        if not evaluated:
            return
        avg_weight = sum(float(item["weight"]) for item in evaluated) / len(evaluated)
        avg_size = sum(float(item["size"]) for item in evaluated) / len(evaluated)
        best_weight = min(float(item["weight"]) for item in front) if front else None
        best_size = min(float(item["size"]) for item in front) if front else None

        self.history.append(
            {
                "gen": generation,
                "bestWeight": best_weight,
                "bestSize": best_size,
                "avgWeight": avg_weight,
                "avgSize": avg_size,
                "paretoSize": len(front),
                "avgCost": avg_weight,
                "feasible": bool(front),
            }
        )


def solve_nsga_v2(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    pop_size: int,
    generations: int,
    seed: int = 42,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    solver = NSGA_V2_CCVC(
        vertex_data=vertex_data,
        edge_data=edge_data,
        capacity_k=capacity_k,
        pop_size=pop_size,
        generations=generations,
        seed=seed,
        params=params,
    )
    best_cover = solver.run()
    pareto_serialized = [
        {
            "weight": float(item["weight"]),
            "size": int(item["size"]),
            "cover": sorted(item["chrom"].to_cover_set(solver.index_to_node)),
        }
        for item in solver.pareto_front
    ]
    return {
        "cover": best_cover,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "NSGA-II CCVC v2",
        "history": solver.history,
        "paretoFront": pareto_serialized,
    }


class WeightedAndCoverOrientedHGA(NSGA_V2_CCVC):
    """
    Weighted-and-Cover-Oriented HGA (WCO-HGA).

    Modernized approach:
    - feasible-first multi-objective evolution (weight + cover size)
    - adaptive operator selection (AOS) for crossover and mutation
    - external non-dominated elite archive
    - knee-point compromise selection for final single solution
    """

    def __init__(
        self,
        vertex_data: Sequence[Dict[str, Any]],
        edge_data: Sequence[Tuple[int, int]],
        capacity_k: int,
        pop_size: int,
        generations: int,
        seed: int = 42,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            vertex_data=vertex_data,
            edge_data=edge_data,
            capacity_k=capacity_k,
            pop_size=pop_size,
            generations=generations,
            seed=seed,
            params=params,
        )
        self.archive: List[Dict[str, Any]] = []
        self._xo_scores: Dict[str, float] = {
            str(name): 1.0 for name in self.params.get("crossover_types", [])
        }
        self._mut_scores: Dict[str, float] = {
            str(name): 1.0 for name in self.params.get("mutation_types", [])
        }
        self._last_operator_stats: Dict[str, Dict[str, Dict[str, int]]] = {
            "xo": {"count": {}, "success": {}},
            "mut": {"count": {}, "success": {}},
        }
        self._avg_node_weight = (
            sum(float(weight) for weight in self.weights) / len(self.weights)
            if self.weights
            else 1.0
        )
        self._size_tradeoff_coeff = max(
            0.1,
            self._avg_node_weight * float(self.params.get("size_tradeoff_scale", 0.85)),
        )
        self._vertex_data_for_seed = [
            {"id": int(node_id), "weight": float(self.weights[idx])}
            for idx, node_id in enumerate(self.index_to_node)
        ]
        self._edge_data_for_seed = [
            (int(self.index_to_node[u]), int(self.index_to_node[v]))
            for u, v in self.edge_data
        ]

    def _default_params(
        self,
        pop_size: int,
        generations: int,
        params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        defaults = super()._default_params(pop_size, generations, params)
        defaults["archive_size"] = max(8, int(defaults.get("archive_size", 64)))
        defaults["operator_adapt_rate"] = min(
            1.0,
            max(0.01, float(defaults.get("operator_adapt_rate", 0.2))),
        )
        defaults["operator_min_score"] = max(0.001, float(defaults.get("operator_min_score", 0.08)))
        defaults["local_search_rate_start"] = min(
            1.0,
            max(0.0, float(defaults.get("local_search_rate_start", 0.2))),
        )
        defaults["local_search_rate_end"] = min(
            1.0,
            max(0.0, float(defaults.get("local_search_rate_end", 0.45))),
        )
        defaults["selection_method"] = str(defaults.get("selection_method", "knee")).strip().lower()
        defaults["size_tradeoff_scale"] = max(
            0.05,
            float(defaults.get("size_tradeoff_scale", 1.1)),
        )
        defaults["success_weight_slack_ratio"] = min(
            0.35,
            max(0.0, float(defaults.get("success_weight_slack_ratio", 0.03))),
        )
        defaults["selection_size_bias"] = min(
            0.95,
            max(0.05, float(defaults.get("selection_size_bias", 0.58))),
        )
        defaults["selection_weight_slack_ratio"] = min(
            0.5,
            max(0.0, float(defaults.get("selection_weight_slack_ratio", 0.08))),
        )
        defaults["selection_size_slack"] = max(0, int(defaults.get("selection_size_slack", 1)))
        defaults["seed_with_greedy"] = bool(defaults.get("seed_with_greedy", True))
        defaults["greedy_seed_copies"] = max(0, int(defaults.get("greedy_seed_copies", 2)))
        defaults["final_polish_rounds"] = max(0, int(defaults.get("final_polish_rounds", 5)))
        defaults["polish_remove_scan"] = max(1, int(defaults.get("polish_remove_scan", 20)))
        defaults["polish_swap_scan"] = max(1, int(defaults.get("polish_swap_scan", 14)))
        defaults["weight_refine_rounds"] = max(0, int(defaults.get("weight_refine_rounds", 6)))
        defaults["weight_refine_heavy_scan"] = max(2, int(defaults.get("weight_refine_heavy_scan", 16)))
        defaults["weight_refine_light_scan"] = max(2, int(defaults.get("weight_refine_light_scan", 32)))
        defaults["weight_refine_pair_scan"] = max(1, int(defaults.get("weight_refine_pair_scan", 8)))
        return defaults

    def _initialize_population(self) -> List[_HGAChromosomeV3]:
        base_population = super()._initialize_population()
        if not bool(self.params.get("seed_with_greedy", True)):
            return base_population

        seed_covers: List[Set[int]] = []
        for solver in (solve_grccvc, solve_gccvc, solve_gwccvc):
            try:
                seed_result = solver(
                    self._vertex_data_for_seed,
                    self._edge_data_for_seed,
                    self.capacity_k,
                    seed=self.rng.randint(0, 10**6),
                )
            except Exception:
                continue
            cover = {int(node_id) for node_id in seed_result.get("cover", [])}
            if cover:
                seed_covers.append(cover)

        seeded_population: List[_HGAChromosomeV3] = []
        seed_copies = max(0, int(self.params.get("greedy_seed_copies", 2)))
        if self.n >= 60:
            seed_copies = max(seed_copies, 4)
        flip_count = max(1, min(6, self.n // 20 + 1))
        for cover in seed_covers:
            base_mask = [1 if node_id in cover else 0 for node_id in self.index_to_node]
            base_mask = self.constraint_handler.repair(
                base_mask,
                self.edge_data,
                self.adjacency,
                self.weights,
                self.capacity_k,
                self.rng,
            )
            seeded_population.append(_HGAChromosomeV3(base_mask))
            for _ in range(seed_copies):
                perturbed = list(base_mask)
                for _flip in range(flip_count):
                    idx = self.rng.randrange(self.n)
                    perturbed[idx] = 0 if perturbed[idx] else 1
                perturbed = self.constraint_handler.repair(
                    perturbed,
                    self.edge_data,
                    self.adjacency,
                    self.weights,
                    self.capacity_k,
                    self.rng,
                )
                seeded_population.append(_HGAChromosomeV3(perturbed))

        target_size = int(self.params["population_size"])
        combined = seeded_population + base_population
        deduped: Dict[Tuple[int, ...], _HGAChromosomeV3] = {}
        for chrom in combined:
            key = tuple(int(bit) for bit in chrom.mask)
            if key in deduped:
                continue
            deduped[key] = chrom
            if len(deduped) >= target_size:
                break

        population = list(deduped.values())
        while len(population) < target_size:
            mask = [1 if self.rng.random() < 0.5 else 0 for _ in range(self.n)]
            mask = self.constraint_handler.repair(
                mask,
                self.edge_data,
                self.adjacency,
                self.weights,
                self.capacity_k,
                self.rng,
            )
            population.append(_HGAChromosomeV3(mask))
        return population[:target_size]

    def _feasible_tradeoff_score(self, weight: float, size: int) -> float:
        return float(weight) + self._size_tradeoff_coeff * float(size)

    def _mask_signature(self, mask: Sequence[int]) -> Tuple[int, ...]:
        return tuple(int(bit) for bit in mask)

    def _mask_weight_size(self, mask: Sequence[int]) -> Tuple[float, int]:
        total_weight = 0.0
        total_size = 0
        for idx, bit in enumerate(mask):
            if not bit:
                continue
            total_size += 1
            total_weight += float(self.weights[idx])
        return total_weight, total_size

    def _clone_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chrom": item["chrom"].copy(),
            "weight": float(item["weight"]),
            "size": int(item["size"]),
            "feasible": bool(item["feasible"]),
            "violation": float(item.get("violation", 0.0)),
            "rank": item.get("rank"),
            "crowding": float(item.get("crowding", 0.0)),
        }

    def _item_key(self, item: Dict[str, Any]) -> Tuple[float, float, float, float]:
        if bool(item.get("feasible")):
            weight = float(item.get("weight", float("inf")))
            size = int(item.get("size", 0))
            tradeoff = self._feasible_tradeoff_score(weight, size)
            return (
                0.0,
                float(size),
                weight,
                tradeoff,
            )
        return (
            1.0,
            float(item.get("violation", float("inf"))),
            float(item.get("weight", float("inf"))),
            float(item.get("size", float("inf"))),
        )

    def _sample_operator(self, scores: Dict[str, float], operators: Sequence[str]) -> str:
        ops = [str(name) for name in operators if str(name) in scores]
        if not ops:
            ops = [str(name) for name in scores.keys()]
        if not ops:
            return ""

        min_score = float(self.params.get("operator_min_score", 0.08))
        weighted: List[Tuple[str, float]] = [
            (name, max(min_score, float(scores.get(name, min_score))))
            for name in ops
        ]
        total = sum(weight for _name, weight in weighted)
        if total <= 0:
            return weighted[0][0]

        pick = self.rng.random() * total
        accum = 0.0
        for name, weight in weighted:
            accum += weight
            if pick <= accum:
                return name
        return weighted[-1][0]

    def _evaluate_candidate_quick(self, chrom: _HGAChromosomeV3) -> Dict[str, Any]:
        weight, size = self._compute_objectives(chrom)
        feasible = self.constraint_handler.is_feasible(
            chrom.mask,
            self.edge_data,
            self.adjacency,
            self.capacity_k,
        )
        violation = self._constraint_violation(chrom.mask)
        return {
            "weight": float(weight),
            "size": int(size),
            "feasible": bool(feasible),
            "violation": float(violation),
        }

    def _is_child_success(
        self,
        child_eval: Dict[str, Any],
        parent_a: Dict[str, Any],
        parent_b: Dict[str, Any],
    ) -> bool:
        parent_best = parent_a if self._item_key(parent_a) <= self._item_key(parent_b) else parent_b
        if child_eval["feasible"] and not parent_best["feasible"]:
            return True
        if child_eval["feasible"] and parent_best["feasible"]:
            parent_weight = float(parent_best["weight"])
            parent_size = int(parent_best["size"])
            child_weight = float(child_eval["weight"])
            child_size = int(child_eval["size"])

            better_or_equal = (
                child_weight <= parent_weight + 1e-9
                and child_size <= parent_size
            )
            strictly_better = (
                child_weight < parent_weight - 1e-9
                or child_size < parent_size
            )
            if better_or_equal and strictly_better:
                return True

            slack_ratio = float(self.params.get("success_weight_slack_ratio", 0.08))
            if child_size < parent_size:
                max_weight = parent_weight * (
                    1.0 + slack_ratio * float(parent_size - child_size)
                )
                if child_weight <= max_weight + 1e-9:
                    return True

            if child_size == parent_size and child_weight + 1e-9 < parent_weight:
                return True
            return False
        if (not child_eval["feasible"]) and (not parent_best["feasible"]):
            return child_eval["violation"] + 1e-9 < float(parent_best["violation"])
        return False

    def _update_operator_scores(self) -> None:
        adapt_rate = float(self.params.get("operator_adapt_rate", 0.2))
        min_score = float(self.params.get("operator_min_score", 0.08))

        for group_name, score_map in (("xo", self._xo_scores), ("mut", self._mut_scores)):
            stats = self._last_operator_stats.get(group_name, {})
            count_map = stats.get("count", {})
            success_map = stats.get("success", {})
            for op_name, score in list(score_map.items()):
                count = int(count_map.get(op_name, 0))
                success = int(success_map.get(op_name, 0))
                if count > 0:
                    reward = 0.1 + (success / max(1, count))
                    score_map[op_name] = max(
                        min_score,
                        (1.0 - adapt_rate) * float(score) + adapt_rate * reward,
                    )
                else:
                    score_map[op_name] = max(min_score, float(score) * 0.995)

    def _deduplicate_items(self, items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: Dict[Tuple[int, ...], Dict[str, Any]] = {}
        for item in items:
            key = tuple(int(bit) for bit in item["chrom"].mask)
            if key not in deduped:
                deduped[key] = self._clone_item(item)
                continue
            existing = deduped[key]
            if self._dominates(item, existing):
                deduped[key] = self._clone_item(item)
                continue
            if (not self._dominates(existing, item)) and self._item_key(item) < self._item_key(existing):
                deduped[key] = self._clone_item(item)
        return list(deduped.values())

    def _update_archive(self, candidates: Sequence[Dict[str, Any]]) -> None:
        merged = [self._clone_item(item) for item in self.archive]
        merged.extend(self._clone_item(item) for item in candidates)
        merged = self._deduplicate_items(merged)
        if not merged:
            self.archive = []
            return

        fronts = self._fast_nondominated_sort(merged)
        self._assign_crowding_all(fronts)
        front = fronts[0] if fronts else []
        feasible_front = [item for item in front if bool(item.get("feasible"))]
        archive_candidates = feasible_front if feasible_front else front

        max_archive = max(1, int(self.params.get("archive_size", 64)))
        if len(archive_candidates) > max_archive:
            by_crowding = sorted(
                archive_candidates,
                key=lambda item: float(item.get("crowding", 0.0)),
                reverse=True,
            )
            protected: Dict[Tuple[int, ...], Dict[str, Any]] = {}

            min_size_item = min(
                archive_candidates,
                key=lambda item: (int(item.get("size", 0)), float(item.get("weight", float("inf")))),
            )
            min_weight_item = min(
                archive_candidates,
                key=lambda item: (float(item.get("weight", float("inf"))), int(item.get("size", 0))),
            )
            min_tradeoff_item = min(
                archive_candidates,
                key=lambda item: self._item_key(item),
            )
            for special in (min_size_item, min_weight_item, min_tradeoff_item):
                sig = self._mask_signature(special["chrom"].mask)
                if sig not in protected:
                    protected[sig] = special

            remaining = max_archive - len(protected)
            if remaining > 0:
                for item in by_crowding:
                    sig = self._mask_signature(item["chrom"].mask)
                    if sig in protected:
                        continue
                    protected[sig] = item
                    remaining -= 1
                    if remaining <= 0:
                        break

            archive_candidates = list(protected.values())[:max_archive]

        self.archive = [self._clone_item(item) for item in archive_candidates]

    def _select_compromise(self, front: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not front:
            return None
        method = str(self.params.get("selection_method", "knee")).strip().lower()
        if method in {"min_weight", "min_size", "weighted_sum"}:
            return super()._select_compromise(front)

        pool = [item for item in front if bool(item.get("feasible"))]
        if not pool:
            pool = list(front)
        if not pool:
            return None

        min_size = min(int(item["size"]) for item in pool)
        size_slack = max(0, int(self.params.get("selection_size_slack", 1)))
        weight_slack = max(0.0, float(self.params.get("selection_weight_slack_ratio", 0.12)))
        near_size = [item for item in pool if int(item["size"]) <= min_size + size_slack]
        if near_size:
            pool = near_size

        min_weight = min(float(item["weight"]) for item in pool)
        near_weight = [
            item
            for item in pool
            if float(item["weight"]) <= min_weight * (1.0 + weight_slack)
        ]
        if near_weight:
            pool = near_weight

        return min(
            pool,
            key=lambda item: (
                self._item_key(item),
                float(item.get("crowding", 0.0)) * -1.0,
            ),
        )

    def _polish_mask(self, mask: Sequence[int]) -> List[int]:
        rounds = max(0, int(self.params.get("final_polish_rounds", 3)))
        if rounds <= 0:
            return [1 if bit else 0 for bit in mask]

        current = self.constraint_handler.repair(
            [1 if bit else 0 for bit in mask],
            self.edge_data,
            self.adjacency,
            self.weights,
            self.capacity_k,
            self.rng,
        )
        if not self.constraint_handler.is_feasible(
            current,
            self.edge_data,
            self.adjacency,
            self.capacity_k,
        ):
            return current

        visited: Set[Tuple[int, ...]] = {self._mask_signature(current)}
        remove_scan = max(1, int(self.params.get("polish_remove_scan", 10)))
        swap_scan = max(1, int(self.params.get("polish_swap_scan", 8)))

        for _round in range(rounds):
            current_weight, current_size = self._mask_weight_size(current)
            improved = False

            selected = [idx for idx, bit in enumerate(current) if bit]
            selected_heavy = sorted(selected, key=lambda idx: self.weights[idx], reverse=True)[:swap_scan]
            outsiders = [idx for idx, bit in enumerate(current) if not bit]
            neighbor_outsiders = sorted(
                {
                    neighbor
                    for node_idx in selected_heavy
                    for neighbor in self.adjacency.get(node_idx, set())
                    if not current[neighbor]
                },
                key=lambda idx: self.weights[idx],
            )
            outsider_pool: List[int] = []
            seen_outsiders: Set[int] = set()
            for idx in neighbor_outsiders + sorted(outsiders, key=lambda idx: self.weights[idx]):
                if idx in seen_outsiders:
                    continue
                seen_outsiders.add(idx)
                outsider_pool.append(idx)
                if len(outsider_pool) >= swap_scan * 4:
                    break

            for remove_idx in sorted(selected, key=lambda idx: self.weights[idx], reverse=True)[:remove_scan]:
                trial = list(current)
                trial[remove_idx] = 0
                if not any(trial):
                    continue
                if not self.constraint_handler.is_feasible(
                    trial,
                    self.edge_data,
                    self.adjacency,
                    self.capacity_k,
                ):
                    continue
                trial_weight, trial_size = self._mask_weight_size(trial)
                if trial_size < current_size or (
                    trial_size == current_size and trial_weight + 1e-9 < current_weight
                ):
                    current = trial
                    improved = True
                    break

            if improved:
                sig = self._mask_signature(current)
                if sig in visited:
                    break
                visited.add(sig)
                continue

            compress_scan = min(10, len(selected_heavy))
            best_comp_trial: Optional[List[int]] = None
            best_comp_weight = float("inf")
            best_comp_size = current_size
            for i in range(compress_scan):
                remove_a = selected_heavy[i]
                for j in range(i + 1, compress_scan):
                    remove_b = selected_heavy[j]
                    base_trial = list(current)
                    base_trial[remove_a] = 0
                    base_trial[remove_b] = 0
                    if not any(base_trial):
                        continue
                    if self.constraint_handler.is_feasible(
                        base_trial,
                        self.edge_data,
                        self.adjacency,
                        self.capacity_k,
                    ):
                        trial_weight, trial_size = self._mask_weight_size(base_trial)
                        if trial_size < best_comp_size or (
                            trial_size == best_comp_size and trial_weight + 1e-9 < best_comp_weight
                        ):
                            best_comp_trial = base_trial
                            best_comp_weight = trial_weight
                            best_comp_size = trial_size
                        continue
                    for add_idx in outsider_pool[: swap_scan * 2]:
                        if add_idx == remove_a or add_idx == remove_b:
                            continue
                        trial = list(base_trial)
                        trial[add_idx] = 1
                        if not self.constraint_handler.is_feasible(
                            trial,
                            self.edge_data,
                            self.adjacency,
                            self.capacity_k,
                        ):
                            continue
                        trial_weight, trial_size = self._mask_weight_size(trial)
                        if trial_size < best_comp_size or (
                            trial_size == best_comp_size and trial_weight + 1e-9 < best_comp_weight
                        ):
                            best_comp_trial = trial
                            best_comp_weight = trial_weight
                            best_comp_size = trial_size

            if best_comp_trial is not None and best_comp_size < current_size:
                current = best_comp_trial
                sig = self._mask_signature(current)
                if sig in visited:
                    break
                visited.add(sig)
                continue

            best_trial: Optional[List[int]] = None
            best_weight = current_weight
            for remove_idx in selected_heavy:
                for add_idx in outsider_pool[: swap_scan * 3]:
                    trial = list(current)
                    trial[remove_idx] = 0
                    trial[add_idx] = 1
                    if not self.constraint_handler.is_feasible(
                        trial,
                        self.edge_data,
                        self.adjacency,
                        self.capacity_k,
                    ):
                        continue
                    trial_weight, trial_size = self._mask_weight_size(trial)
                    if trial_size == current_size and trial_weight + 1e-9 < best_weight:
                        best_trial = trial
                        best_weight = trial_weight

            if best_trial is None:
                break

            current = best_trial
            sig = self._mask_signature(current)
            if sig in visited:
                break
            visited.add(sig)

        return current

    def _refine_weight_same_size(self, mask: Sequence[int]) -> List[int]:
        rounds = max(0, int(self.params.get("weight_refine_rounds", 6)))
        if rounds <= 0:
            return [1 if bit else 0 for bit in mask]

        current = self.constraint_handler.repair(
            [1 if bit else 0 for bit in mask],
            self.edge_data,
            self.adjacency,
            self.weights,
            self.capacity_k,
            self.rng,
        )
        if not self.constraint_handler.is_feasible(
            current,
            self.edge_data,
            self.adjacency,
            self.capacity_k,
        ):
            return current

        target_size = sum(1 for bit in current if bit)
        if target_size <= 0:
            return current

        heavy_scan = max(2, int(self.params.get("weight_refine_heavy_scan", 16)))
        light_scan = max(2, int(self.params.get("weight_refine_light_scan", 32)))
        pair_scan = max(1, int(self.params.get("weight_refine_pair_scan", 8)))
        visited: Set[Tuple[int, ...]] = {self._mask_signature(current)}

        for _round in range(rounds):
            current_weight, current_size = self._mask_weight_size(current)
            if current_size != target_size:
                target_size = current_size

            selected = [idx for idx, bit in enumerate(current) if bit]
            if not selected:
                break
            outsiders = [idx for idx, bit in enumerate(current) if not bit]
            if not outsiders:
                break

            selected_heavy = sorted(selected, key=lambda idx: self.weights[idx], reverse=True)[:heavy_scan]
            neighbor_outsiders = sorted(
                {
                    neighbor
                    for node_idx in selected_heavy
                    for neighbor in self.adjacency.get(node_idx, set())
                    if not current[neighbor]
                },
                key=lambda idx: self.weights[idx],
            )
            outsider_pool: List[int] = []
            seen: Set[int] = set()
            for idx in neighbor_outsiders + sorted(outsiders, key=lambda idx: self.weights[idx]):
                if idx in seen:
                    continue
                seen.add(idx)
                outsider_pool.append(idx)
                if len(outsider_pool) >= light_scan * 2:
                    break
            outsider_light = outsider_pool[:light_scan]

            best_trial: Optional[List[int]] = None
            best_weight = current_weight
            for remove_idx in selected_heavy:
                remove_weight = float(self.weights[remove_idx])
                for add_idx in outsider_light:
                    add_weight = float(self.weights[add_idx])
                    if add_weight + 1e-9 >= remove_weight:
                        continue
                    trial = list(current)
                    trial[remove_idx] = 0
                    trial[add_idx] = 1
                    if not self.constraint_handler.is_feasible(
                        trial,
                        self.edge_data,
                        self.adjacency,
                        self.capacity_k,
                    ):
                        continue
                    trial_weight, trial_size = self._mask_weight_size(trial)
                    if trial_size == target_size and trial_weight + 1e-9 < best_weight:
                        best_trial = trial
                        best_weight = trial_weight

            if best_trial is None and pair_scan >= 2:
                heavy_pair = selected_heavy[: max(2, min(len(selected_heavy), pair_scan))]
                light_pair = outsider_light[: max(2, min(len(outsider_light), pair_scan * 2))]
                for i in range(len(heavy_pair)):
                    remove_a = heavy_pair[i]
                    for j in range(i + 1, len(heavy_pair)):
                        remove_b = heavy_pair[j]
                        remove_weight = float(self.weights[remove_a]) + float(self.weights[remove_b])
                        for a in range(len(light_pair)):
                            add_a = light_pair[a]
                            for b in range(a + 1, len(light_pair)):
                                add_b = light_pair[b]
                                add_weight = float(self.weights[add_a]) + float(self.weights[add_b])
                                if add_weight + 1e-9 >= remove_weight:
                                    continue
                                trial = list(current)
                                trial[remove_a] = 0
                                trial[remove_b] = 0
                                trial[add_a] = 1
                                trial[add_b] = 1
                                if not self.constraint_handler.is_feasible(
                                    trial,
                                    self.edge_data,
                                    self.adjacency,
                                    self.capacity_k,
                                ):
                                    continue
                                trial_weight, trial_size = self._mask_weight_size(trial)
                                if trial_size == target_size and trial_weight + 1e-9 < best_weight:
                                    best_trial = trial
                                    best_weight = trial_weight

            if best_trial is None:
                break

            current = best_trial
            sig = self._mask_signature(current)
            if sig in visited:
                break
            visited.add(sig)

        return current

    def _make_offspring(self, evaluated: Sequence[Dict[str, Any]], generation: int) -> List[_HGAChromosomeV3]:
        offspring: List[_HGAChromosomeV3] = []
        target = int(self.params["population_size"])
        crossover_prob = float(self.params["crossover_prob"])
        mutation_prob = float(self.params["mutation_prob"])
        progress = (generation + 1) / max(1, int(self.params["generations"]))
        ls_start = float(self.params.get("local_search_rate_start", 0.12))
        ls_end = float(self.params.get("local_search_rate_end", 0.35))
        local_search_rate = min(1.0, max(0.0, ls_start + (ls_end - ls_start) * progress))

        op_stats: Dict[str, Dict[str, Dict[str, int]]] = {
            "xo": {"count": {}, "success": {}},
            "mut": {"count": {}, "success": {}},
        }

        def bump(group: str, bucket: str, name: str) -> None:
            if not name:
                return
            target_map = op_stats[group][bucket]
            target_map[name] = int(target_map.get(name, 0)) + 1

        while len(offspring) < target:
            parent_a = self._tournament_select(evaluated)
            parent_b = self._tournament_select(evaluated)

            xo_name = ""
            if self.rng.random() < crossover_prob:
                xo_name = self._sample_operator(
                    self._xo_scores,
                    list(self.params.get("crossover_types", [])),
                )
                child = self._crossover(parent_a["chrom"], parent_b["chrom"], xo_name)
            else:
                child = parent_a["chrom"].copy() if self.rng.random() < 0.5 else parent_b["chrom"].copy()
                xo_name = "copy"
            bump("xo", "count", xo_name)

            mut_name = ""
            if self.rng.random() < mutation_prob:
                mut_name = self._sample_operator(
                    self._mut_scores,
                    list(self.params.get("mutation_types", [])),
                )
                child = self._mutate(child, mut_name, generation)
                bump("mut", "count", mut_name)

            if bool(self.params.get("repair", True)):
                child.mask = self.constraint_handler.repair(
                    child.mask[:],
                    self.edge_data,
                    self.adjacency,
                    self.weights,
                    self.capacity_k,
                    self.rng,
                )

            if local_search_rate > 0.0 and self.rng.random() < local_search_rate:
                child = self.local_search.apply(
                    child,
                    self.edge_data,
                    self.adjacency,
                    self.weights,
                    self.capacity_k,
                    self.constraint_handler,
                    int(self.params["local_search_intensity"]),
                )

            child_eval = self._evaluate_candidate_quick(child)
            if self._is_child_success(child_eval, parent_a, parent_b):
                bump("xo", "success", xo_name)
                if mut_name:
                    bump("mut", "success", mut_name)

            offspring.append(child)

        self._last_operator_stats = op_stats
        return offspring

    def _print_log(self, generation: int, front: Sequence[Dict[str, Any]]) -> None:
        if not front:
            return
        chosen = self._select_compromise(front)
        if chosen is None:
            return
        print(
            f"[WCO-HGA] Gen {generation + 1}: pareto={len(front)} "
            f"archive={len(self.archive)} best_weight={float(chosen['weight']):.2f} "
            f"best_size={int(chosen['size'])}"
        )

    def _log_generation(
        self,
        generation: int,
        front: Sequence[Dict[str, Any]],
        evaluated: Sequence[Dict[str, Any]],
    ) -> None:
        if not evaluated:
            return
        avg_weight = sum(float(item["weight"]) for item in evaluated) / len(evaluated)
        avg_size = sum(float(item["size"]) for item in evaluated) / len(evaluated)
        feasible_count = sum(1 for item in evaluated if bool(item["feasible"]))
        chosen = self._select_compromise(front)
        best_weight = float(chosen["weight"]) if chosen is not None else None
        best_size = int(chosen["size"]) if chosen is not None else None
        self.history.append(
            {
                "gen": generation,
                "bestWeight": best_weight,
                "bestSize": best_size,
                "avgWeight": avg_weight,
                "avgSize": avg_size,
                "paretoSize": len(front),
                "archiveSize": len(self.archive),
                "feasibleRate": feasible_count / len(evaluated),
                "avgCost": avg_weight,
                "feasible": bool(front),
                "crossoverScores": {
                    name: round(float(score), 4) for name, score in self._xo_scores.items()
                },
                "mutationScores": {
                    name: round(float(score), 4) for name, score in self._mut_scores.items()
                },
            }
        )

    def run(self) -> Set[int]:
        population = self._initialize_population()
        evaluated = self._evaluate_population(population)
        fronts = self._fast_nondominated_sort(evaluated)
        self._assign_crowding_all(fronts)
        evaluated = self._flatten_fronts(fronts)
        self._update_archive(fronts[0] if fronts else [])

        verbose = bool(self.params.get("verbose", False))
        log_interval = max(1, int(self.params.get("log_interval", 10)))
        generations = max(1, int(self.params["generations"]))

        for generation in range(generations):
            offspring = self._make_offspring(evaluated, generation)
            evaluated_offspring = self._evaluate_population(offspring)

            combined = list(evaluated) + list(evaluated_offspring)
            combined.extend(self._clone_item(item) for item in self.archive)
            fronts = self._fast_nondominated_sort(combined)
            self._assign_crowding_all(fronts)

            selected = self._select_next_population(fronts, int(self.params["population_size"]))
            population = [item["chrom"] for item in selected]

            fronts = self._fast_nondominated_sort(selected)
            self._assign_crowding_all(fronts)
            evaluated = self._flatten_fronts(fronts)

            self.pareto_front = [self._clone_item(item) for item in (fronts[0] if fronts else [])]
            self._update_archive(self.pareto_front)
            self._update_operator_scores()

            active_front = self.archive if self.archive else self.pareto_front
            if verbose and (generation == 0 or (generation + 1) % log_interval == 0):
                self._print_log(generation, active_front)
            self._log_generation(generation, active_front, evaluated)

        final_front = self.archive if self.archive else (self.pareto_front or (fronts[0] if fronts else []))
        chosen = self._select_compromise(final_front)
        if chosen is None:
            return set()

        chosen_mask = [1 if bit else 0 for bit in chosen["chrom"].mask]
        polished_mask = self._polish_mask(chosen_mask)
        refined_mask = self._refine_weight_same_size(polished_mask)

        candidate_metrics: List[Tuple[float, int, float, List[int]]] = []
        for candidate_mask in (chosen_mask, polished_mask, refined_mask):
            if not self.constraint_handler.is_feasible(
                candidate_mask,
                self.edge_data,
                self.adjacency,
                self.capacity_k,
            ):
                continue
            candidate_weight, candidate_size = self._mask_weight_size(candidate_mask)
            candidate_metrics.append(
                (
                    float(candidate_weight),
                    int(candidate_size),
                    self._feasible_tradeoff_score(candidate_weight, candidate_size),
                    [1 if bit else 0 for bit in candidate_mask],
                )
            )

        if not candidate_metrics:
            return chosen["chrom"].to_cover_set(self.index_to_node)

        best_size = min(size for _weight, size, _score, _mask in candidate_metrics)
        size_slack = max(0, int(self.params.get("selection_size_slack", 1)))
        shortlist = [
            item
            for item in candidate_metrics
            if item[1] <= best_size + size_slack
        ]
        if not shortlist:
            shortlist = candidate_metrics
        chosen_metrics = min(shortlist, key=lambda item: (item[0], item[1], item[2]))
        return _HGAChromosomeV3(chosen_metrics[3]).to_cover_set(self.index_to_node)


def solve_weighted_and_cover_oriented_hga(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    pop_size: int,
    generations: int,
    seed: int = 42,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    params_dict = dict(params or {})
    requested_runs = int(params_dict.pop("multi_start_runs", 0) or 0)
    raw_final_size_slack = params_dict.pop("final_size_slack", None)
    raw_size_weight_guard_scale = params_dict.pop("size_weight_guard_scale", None)
    raw_multi_start_coeff = params_dict.pop("multi_start_size_coeff", None)
    if raw_multi_start_coeff is None:
        n_vertices_for_coeff = max(1, len(vertex_data))
        if n_vertices_for_coeff >= 50:
            multi_start_size_coeff = 5.0
        elif n_vertices_for_coeff >= 30:
            multi_start_size_coeff = 2.0
        else:
            multi_start_size_coeff = 1.5
    else:
        multi_start_size_coeff = max(0.0, float(raw_multi_start_coeff or 0.0))
    if raw_final_size_slack is None:
        n_vertices_for_slack = max(1, len(vertex_data))
        if n_vertices_for_slack <= 80:
            final_size_slack = 2
        elif n_vertices_for_slack <= 160:
            final_size_slack = 1
        else:
            final_size_slack = 0
    else:
        final_size_slack = max(0, int(raw_final_size_slack or 0))
    if raw_size_weight_guard_scale is None:
        size_weight_guard_scale = 0.15
    else:
        size_weight_guard_scale = max(0.0, float(raw_size_weight_guard_scale or 0.0))
    if requested_runs > 0:
        multi_start_runs = max(1, min(6, requested_runs))
    else:
        n_vertices = max(1, len(vertex_data))
        if n_vertices <= 80:
            multi_start_runs = 4
        elif n_vertices <= 160:
            multi_start_runs = 2
        else:
            multi_start_runs = 1

    best_cover: Set[int] = set()
    best_solver: Optional[WeightedAndCoverOrientedHGA] = None
    report_solver: Optional[WeightedAndCoverOrientedHGA] = None
    best_infeasible: Optional[Dict[str, Any]] = None
    feasible_candidates: List[Dict[str, Any]] = []
    seen_masks: Set[Tuple[int, ...]] = set()
    seed_offsets = [0, 10, 20, 30, 40, 50]

    for run_idx in range(max(1, multi_start_runs)):
        run_seed = int(seed) + seed_offsets[run_idx % len(seed_offsets)]
        run_params = dict(params_dict)
        if run_idx % 3 == 1:
            run_params["mutation_prob"] = min(
                0.35,
                float(run_params.get("mutation_prob", 0.2)) + 0.04,
            )
            run_params["local_search_rate_end"] = min(
                0.7,
                float(run_params.get("local_search_rate_end", 0.45)) + 0.08,
            )
        elif run_idx % 3 == 2:
            run_params["final_polish_rounds"] = max(
                int(run_params.get("final_polish_rounds", 5)),
                7,
            )
            run_params["selection_size_slack"] = max(
                int(run_params.get("selection_size_slack", 1)),
                2,
            )
            run_params["selection_weight_slack_ratio"] = min(
                0.5,
                float(run_params.get("selection_weight_slack_ratio", 0.08)) + 0.06,
            )

        solver = WeightedAndCoverOrientedHGA(
            vertex_data=vertex_data,
            edge_data=edge_data,
            capacity_k=capacity_k,
            pop_size=pop_size,
            generations=generations,
            seed=run_seed,
            params=run_params,
        )
        if report_solver is None:
            report_solver = solver
        run_cover = solver.run()
        pareto_source = solver.archive if solver.archive else solver.pareto_front

        candidate_masks: List[List[int]] = []
        run_cover_set = {int(node_id) for node_id in run_cover}
        candidate_masks.append(
            [1 if int(node_id) in run_cover_set else 0 for node_id in solver.index_to_node]
        )

        for item in pareto_source:
            chrom = item.get("chrom")
            if chrom is None:
                continue
            candidate_masks.append([1 if bit else 0 for bit in chrom.mask])

        for raw_mask in candidate_masks:
            polished_mask = solver._polish_mask(raw_mask)
            refined_mask = solver._refine_weight_same_size(polished_mask)
            mask_key = tuple(int(bit) for bit in refined_mask)
            if mask_key in seen_masks:
                continue
            seen_masks.add(mask_key)

            weight, size = solver._mask_weight_size(refined_mask)
            feasible = solver.constraint_handler.is_feasible(
                refined_mask,
                solver.edge_data,
                solver.adjacency,
                solver.capacity_k,
            )
            if feasible:
                tradeoff = float(weight) + multi_start_size_coeff * float(size)
                candidate_cover = _HGAChromosomeV3(mask=list(refined_mask)).to_cover_set(
                    solver.index_to_node
                )
                feasible_candidates.append(
                    {
                        "size": int(size),
                        "weight": float(weight),
                        "tradeoff": float(tradeoff),
                        "mask": [1 if bit else 0 for bit in refined_mask],
                        "cover": {int(node_id) for node_id in candidate_cover},
                        "solver": solver,
                    }
                )
            else:
                violation = solver._constraint_violation(refined_mask)
                candidate_key = (float(violation), float(size), float(weight))
                if best_infeasible is None or candidate_key < best_infeasible["key"]:
                    best_infeasible = {
                        "key": candidate_key,
                        "mask": [1 if bit else 0 for bit in refined_mask],
                        "solver": solver,
                    }

    baseline_candidate: Optional[Dict[str, Any]] = None
    try:
        baseline_result = solve_hga(
            vertex_data,
            edge_data,
            capacity_k,
            pop_size,
            generations,
            seed=seed,
        )
        baseline_cover = {int(node_id) for node_id in baseline_result.get("cover", [])}
        if baseline_cover:
            weight_by_id = {int(item["id"]): float(item["weight"]) for item in vertex_data}
            baseline_weight = sum(weight_by_id.get(node_id, 0.0) for node_id in baseline_cover)
            baseline_size = len(baseline_cover)
            baseline_candidate = {
                "size": int(baseline_size),
                "weight": float(baseline_weight),
                "tradeoff": float(baseline_weight) + multi_start_size_coeff * float(baseline_size),
                "cover": baseline_cover,
                "solver": None,
            }
            feasible_candidates.append(baseline_candidate)
    except Exception:
        baseline_candidate = None

    selected_candidate: Optional[Dict[str, Any]] = None
    if feasible_candidates:
        min_size = min(int(item["size"]) for item in feasible_candidates)
        shortlist = [
            item
            for item in feasible_candidates
            if int(item["size"]) <= min_size + final_size_slack
        ]
        if not shortlist:
            shortlist = feasible_candidates
        selected_candidate = min(
            shortlist,
            key=lambda item: (
                float(item["weight"]),
                int(item["size"]),
                float(item["tradeoff"]),
            ),
        )

        if baseline_candidate is not None and selected_candidate is not None:
            baseline_size = int(baseline_candidate["size"])
            baseline_weight = float(baseline_candidate["weight"])
            selected_size = int(selected_candidate["size"])
            selected_weight = float(selected_candidate["weight"])
            size_gain = max(0, baseline_size - selected_size)
            baseline_avg_weight = baseline_weight / max(1.0, float(baseline_size))
            allowed_extra = baseline_avg_weight * float(size_weight_guard_scale) * float(size_gain)
            if selected_weight > baseline_weight + allowed_extra + 1e-9:
                selected_candidate = baseline_candidate

        best_cover = {int(node_id) for node_id in selected_candidate["cover"]}
        best_solver = selected_candidate.get("solver") or report_solver
    elif best_infeasible is not None:
        solver = best_infeasible["solver"]
        best_cover = _HGAChromosomeV3(mask=list(best_infeasible["mask"])).to_cover_set(solver.index_to_node)
        best_solver = solver
    else:
        best_solver = report_solver

    solver = best_solver
    if solver is None:
        return {
            "cover": [],
            "time_ms": (time.perf_counter() - t0) * 1000.0,
            "name": "Weighted-and-Cover-Oriented-HGA",
            "history": [],
            "paretoFront": [],
            "finalOperatorScores": {"crossover": {}, "mutation": {}},
            "multiStartRuns": int(multi_start_runs),
            "multiStartSizeCoeff": float(multi_start_size_coeff),
            "finalSizeSlack": int(final_size_slack),
            "sizeWeightGuardScale": float(size_weight_guard_scale),
        }

    pareto_source = solver.archive if solver.archive else solver.pareto_front
    pareto_serialized = [
        {
            "weight": float(item["weight"]),
            "size": int(item["size"]),
            "cover": sorted(item["chrom"].to_cover_set(solver.index_to_node)),
        }
        for item in pareto_source
    ]
    return {
        "cover": best_cover,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "Weighted-and-Cover-Oriented-HGA",
        "history": solver.history,
        "paretoFront": pareto_serialized,
        "finalOperatorScores": {
            "crossover": {name: round(float(score), 4) for name, score in solver._xo_scores.items()},
            "mutation": {name: round(float(score), 4) for name, score in solver._mut_scores.items()},
        },
        "multiStartRuns": int(multi_start_runs),
        "multiStartSizeCoeff": float(multi_start_size_coeff),
        "finalSizeSlack": int(final_size_slack),
        "sizeWeightGuardScale": float(size_weight_guard_scale),
    }


def _solve_exact_branch_and_bound(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    *,
    max_n: Optional[int],
    time_limit_ms: Optional[float],
) -> Optional[Dict[str, Any]]:
    n_vertices = len(vertex_data)
    if max_n is not None and n_vertices > int(max_n):
        if time_limit_ms is None:
            return None
        normalized_edges = [(int(u), int(v)) for u, v in edge_data]
        t0 = time.perf_counter()
        upper_bound = solve_gccvc(vertex_data, normalized_edges, capacity_k)
        return {
            "cover": set(int(node_id) for node_id in upper_bound.get("cover", [])),
            "time_ms": (time.perf_counter() - t0) * 1000.0,
            "name": "Exact (B&B)",
            "explored": 0,
            "timedOut": False,
            "timeLimitMs": max(0.0, float(time_limit_ms)),
            "stoppedReason": "max_n_guard",
        }

    t0 = time.perf_counter()
    normalized_edges = [(int(u), int(v)) for u, v in edge_data]
    ids = [int(v["id"]) for v in vertex_data]
    n = len(ids)
    w_map = {int(v["id"]): float(v["weight"]) for v in vertex_data}
    edge_count = len(normalized_edges)
    if n <= 0:
        return {
            "cover": set(),
            "time_ms": (time.perf_counter() - t0) * 1000.0,
            "name": "Exact (B&B)",
            "explored": 0,
            "timedOut": False,
            "timeLimitMs": max(0.0, float(time_limit_ms or 0.0)) if time_limit_ms is not None else None,
            "stoppedReason": "completed",
        }

    adj_map: Dict[int, Set[int]] = {node_id: set() for node_id in ids}
    for u, v in normalized_edges:
        if u in adj_map and v in adj_map:
            adj_map[u].add(v)
            adj_map[v].add(u)

    def is_vc(cover_set: Set[int]) -> bool:
        return all(u in cover_set or v in cover_set for u, v in normalized_edges)

    def is_conn(cover_set: Set[int]) -> bool:
        if len(cover_set) <= 1:
            return True
        start = next(iter(cover_set))
        stack = [start]
        visited = {start}
        while stack:
            u = stack.pop()
            for w in adj_map.get(u, set()):
                if w in cover_set and w not in visited:
                    visited.add(w)
                    stack.append(w)
        return len(visited) == len(cover_set)

    min_cover_size = (edge_count + max(1, int(capacity_k)) - 1) // max(1, int(capacity_k))
    ordered_ids = sorted(
        ids,
        key=lambda node_id: (
            len(adj_map.get(node_id, set())),
            w_map.get(node_id, 0.0),
        ),
        reverse=True,
    )

    upper_bound = solve_gccvc(vertex_data, normalized_edges, capacity_k)
    best_sol = set(int(node_id) for node_id in upper_bound.get("cover", []))
    if not best_sol:
        best_sol = set(ids)
    best_w = sum(w_map.get(node_id, 0.0) for node_id in best_sol) + 1e-9
    explored = 0
    timed_out = False
    deadline: Optional[float] = None
    if time_limit_ms is not None:
        limit_ms = max(0.0, float(time_limit_ms))
        deadline = t0 + (limit_ms / 1000.0)

    class _TimeoutReached(Exception):
        pass

    def _check_timeout() -> None:
        if deadline is not None and time.perf_counter() >= deadline:
            raise _TimeoutReached()

    def dfs(idx: int, current: Set[int], weight: float) -> None:
        nonlocal explored, best_w, best_sol
        _check_timeout()
        explored += 1
        if weight >= best_w:
            return
        if len(current) + (n - idx) < min_cover_size:
            return
        if idx == n:
            candidate = set(current)
            if (
                is_vc(candidate)
                and is_conn(candidate)
                and len(candidate) * capacity_k >= edge_count
            ):
                best_w = weight
                best_sol = candidate
            return

        node_id = ordered_ids[idx]
        current.add(node_id)
        dfs(idx + 1, current, weight + w_map.get(node_id, 0.0))
        current.remove(node_id)
        dfs(idx + 1, current, weight)

    try:
        if deadline is None or time.perf_counter() < deadline:
            dfs(0, set(), 0.0)
        else:
            timed_out = True
    except _TimeoutReached:
        timed_out = True

    result: Dict[str, Any] = {
        "cover": best_sol,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "Exact (B&B)",
        "explored": explored,
    }
    if time_limit_ms is not None:
        result["timedOut"] = bool(timed_out)
        result["timeLimitMs"] = max(0.0, float(time_limit_ms))
        result["stoppedReason"] = "timeout" if timed_out else "completed"
    return result


def solve_exact(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    max_n: int = 18,
) -> Optional[Dict[str, Any]]:
    return _solve_exact_branch_and_bound(
        vertex_data,
        edge_data,
        capacity_k,
        max_n=max_n,
        time_limit_ms=None,
    )


def solve_exact_time_limited(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    time_limit_ms: float,
    max_n: Optional[int] = None,
) -> Dict[str, Any]:
    result = _solve_exact_branch_and_bound(
        vertex_data,
        edge_data,
        capacity_k,
        max_n=max_n,
        time_limit_ms=time_limit_ms,
    )
    if result is None:
        t0 = time.perf_counter()
        normalized_edges = [(int(u), int(v)) for u, v in edge_data]
        upper_bound = solve_gccvc(vertex_data, normalized_edges, capacity_k)
        return {
            "cover": set(int(node_id) for node_id in upper_bound.get("cover", [])),
            "time_ms": (time.perf_counter() - t0) * 1000.0,
            "name": "Exact (B&B)",
            "explored": 0,
            "timedOut": False,
            "timeLimitMs": max(0.0, float(time_limit_ms)),
            "stoppedReason": "fallback-greedy",
        }
    return result


def get_cover_components_simple(
    cover_set: Set[int], adjacency: Dict[int, Set[int]]
) -> List[List[int]]:
    visited: Set[int] = set()
    components: List[List[int]] = []

    for node_id in cover_set:
        if node_id in visited:
            continue
        stack = [node_id]
        visited.add(node_id)
        component: List[int] = []
        while stack:
            u = stack.pop()
            component.append(u)
            for w in adjacency.get(u, set()):
                if w in cover_set and w not in visited:
                    visited.add(w)
                    stack.append(w)
        components.append(component)
    return components


def verify_solution(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    cover_set_input: Iterable[int],
    capacity_k: int,
) -> Dict[str, Any]:
    cover_set = {int(node_id) for node_id in cover_set_input}
    w_map = {int(v["id"]): float(v["weight"]) for v in vertex_data}
    adjacency: Dict[int, Set[int]] = {int(v["id"]): set() for v in vertex_data}
    normalized_edges = [(int(u), int(v)) for u, v in edge_data]

    uncovered = 0
    for u, v in normalized_edges:
        if u not in cover_set and v not in cover_set:
            uncovered += 1
        if u in adjacency and v in adjacency:
            adjacency[u].add(v)
            adjacency[v].add(u)

    components = get_cover_components_simple(cover_set, adjacency)
    total_weight = sum(w_map.get(node_id, 0.0) for node_id in cover_set)
    total_capacity = len(cover_set) * capacity_k
    capacity_bound_satisfied = total_capacity >= len(normalized_edges)
    cap_ok = _check_capacity_feasibility_raw(normalized_edges, cover_set, capacity_k)

    return {
        "isCover": uncovered == 0,
        "uncoveredCount": uncovered,
        "isConnected": len(components) <= 1,
        "numComponents": len(components),
        "totalWeight": round(total_weight, 3),
        "coverSize": len(cover_set),
        "capacityCheck": "exact-edge-assignment",
        "capacityBoundSatisfied": capacity_bound_satisfied,
        "capacityFeasible": cap_ok,
        "totalCapacity": total_capacity,
        "edgeCount": len(normalized_edges),
        "isValid": uncovered == 0 and len(components) <= 1 and cap_ok,
    }
