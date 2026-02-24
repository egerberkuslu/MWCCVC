from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
import random
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple


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
        return len(cover_set) * capacity_k >= len(normalized_edges)

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
            return (
                a * degree
                - b * node.weight
                - c * ratio
                + d * red_bonus
                + e * gray_bonus
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

        while get_uncovered_edges(graph):
            mark_red_nodes(graph, cover_set, capacity_k)
            node = pick_next(graph, False)
            if node is None:
                break
            select_node(graph, node, edge_sorter, cover_set, False)

        if get_uncovered_edges(graph):
            force_cover_remaining(graph, cover_set, pick_next, edge_sorter)
        return repair_connectivity(graph, cover_set)

    def local_search(cover_set: Set[int], moves: int = 10) -> Set[int]:
        current = set(cover_set)
        sorted_nodes = sorted(
            current, key=lambda node_id: w_map.get(node_id, 0.0), reverse=True
        )
        applied = 0
        for node_id in sorted_nodes:
            if applied >= moves:
                break
            trial = set(current)
            trial.discard(node_id)
            if is_vertex_cover_set(trial) and is_conn(trial) and cap_feasible(trial):
                current = trial
                applied += 1
        return current

    def evaluate(theta: Sequence[float], keys: Dict[int, float]) -> Dict[str, Any]:
        cover_set = decode(theta, keys)
        if rnd.random() < 0.25:
            cover_set = local_search(cover_set)

        weight = cover_weight(cover_set)
        uncov = count_uncov(cover_set)
        conn = is_conn(cover_set)
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

    def seed_keys(cover_set: Set[int]) -> Dict[int, float]:
        keys: Dict[int, float] = {}
        for node_id in ids:
            if node_id in cover_set:
                keys[node_id] = rnd.random() * 0.3
            else:
                keys[node_id] = 0.7 + rnd.random() * 0.3
        return keys

    target_pop = max(2, int(pop_size))
    population: List[Dict[str, Any]] = []
    greedy_results = [
        solve_gccvc(vertex_data, normalized_edges, capacity_k, seed),
        solve_grccvc(vertex_data, normalized_edges, capacity_k, seed + 1),
        solve_gwccvc(vertex_data, normalized_edges, capacity_k, seed + 2),
    ]
    theta_seeds = [
        [1.0, 0.1, 0.0, 0.2, 0.05, 0.1],
        [0.5, 0.1, 1.0, 0.2, 0.05, 0.1],
        [0.5, 1.0, 0.0, 0.2, 0.05, 0.1],
    ]
    for idx, greedy_result in enumerate(greedy_results):
        if len(population) >= target_pop:
            break
        population.append(
            {
                "theta": list(theta_seeds[idx]),
                "keys": seed_keys(set(greedy_result["cover"])),
            }
        )

    while len(population) < target_pop:
        theta = [rnd.random() * 3.0 for _ in range(6)]
        keys = {node_id: rnd.random() for node_id in ids}
        population.append({"theta": theta, "keys": keys})

    best_cover: Optional[Set[int]] = None
    best_cost = float("inf")

    for generation in range(max(1, int(generations))):
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

        if evaluations and evaluations[0]["cost"] < best_cost:
            best_cost = evaluations[0]["cost"]
            best_cover = set(evaluations[0]["cover"])

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
            }
        )

        elite_count = min(2, len(evaluations))
        new_population = [
            {
                "theta": list(evaluations[i]["theta"]),
                "keys": dict(evaluations[i]["keys"]),
            }
            for i in range(elite_count)
        ]

        def tournament_pick() -> Dict[str, Any]:
            best_individual: Optional[Dict[str, Any]] = None
            for _ in range(3):
                candidate = evaluations[rnd.randrange(len(evaluations))]
                if best_individual is None or candidate["cost"] < best_individual["cost"]:
                    best_individual = candidate
            return best_individual if best_individual is not None else evaluations[0]

        while len(new_population) < target_pop:
            parent_a = tournament_pick()
            parent_b = tournament_pick()
            child_theta: List[float] = []
            for idx, value in enumerate(parent_a["theta"]):
                gamma = rnd.random()
                child_theta.append(gamma * value + (1.0 - gamma) * parent_b["theta"][idx])

            child_keys: Dict[int, float] = {}
            for node_id in ids:
                if rnd.random() < 0.5:
                    child_keys[node_id] = parent_a["keys"][node_id]
                else:
                    child_keys[node_id] = parent_b["keys"][node_id]

            for idx in range(6):
                if rnd.random() < 0.2:
                    child_theta[idx] = max(
                        0.0,
                        min(3.0, child_theta[idx] + (rnd.random() - 0.5) * 0.4),
                    )

            for node_id in ids:
                if rnd.random() < 0.02:
                    child_keys[node_id] = rnd.random()

            new_population.append({"theta": child_theta, "keys": child_keys})

        population = new_population

    return {
        "cover": best_cover or set(),
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "HGA-CCVC",
        "history": history,
    }


def solve_exact(
    vertex_data: Sequence[Dict[str, Any]],
    edge_data: Sequence[Tuple[int, int]],
    capacity_k: int,
    max_n: int = 18,
) -> Optional[Dict[str, Any]]:
    if len(vertex_data) > max_n:
        return None

    t0 = time.perf_counter()
    ids = [int(v["id"]) for v in vertex_data]
    n = len(ids)
    w_map = {int(v["id"]): float(v["weight"]) for v in vertex_data}
    normalized_edges = [(int(u), int(v)) for u, v in edge_data]
    edge_count = len(normalized_edges)

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

    upper_bound = solve_gccvc(vertex_data, normalized_edges, capacity_k)
    best_w = sum(w_map.get(node_id, 0.0) for node_id in upper_bound["cover"]) + 1e-3
    best_sol = set(upper_bound["cover"])
    explored = 0

    def dfs(idx: int, current: Set[int], weight: float) -> None:
        nonlocal explored, best_w, best_sol
        explored += 1
        if weight >= best_w:
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

        node_id = ids[idx]
        current.add(node_id)
        dfs(idx + 1, current, weight + w_map.get(node_id, 0.0))
        current.remove(node_id)
        dfs(idx + 1, current, weight)

    dfs(0, set(), 0.0)

    return {
        "cover": best_sol,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
        "name": "Exact (B&B)",
        "explored": explored,
    }


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
