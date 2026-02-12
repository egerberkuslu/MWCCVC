import { clamp } from "./format";

export function rng(seed) {
  let state = seed | 0;
  return () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function buildEmbeddedGraph(count = 100, seed = 42) {
  const random = rng(seed);

  const vertices = Array.from({ length: count }, (_, id) => ({
    id,
    weight: 12 + random() * 108,
  }));

  const edges = [];
  const seen = new Set();

  const addEdge = (u, v) => {
    if (u === v) return;
    const a = Math.min(u, v);
    const b = Math.max(u, v);
    const key = `${a}-${b}`;
    if (seen.has(key)) return;
    seen.add(key);
    edges.push([a, b]);
  };

  for (let i = 0; i < count - 1; i++) addEdge(i, i + 1);

  for (let i = 0; i < count; i++) {
    for (let j = i + 2; j < count; j++) {
      if (random() < 0.045) addEdge(i, j);
    }
  }

  return { vertices, edges };
}

export function buildDensityBenchmarkGraph({ n = 16, density = 0.2, seed = 1234 }) {
  const random = rng(seed);

  const vertices = Array.from({ length: n }, (_, id) => ({
    id,
    weight: 10 + random() * 60,
  }));

  const edges = [];
  const seen = new Set();

  const addEdge = (u, v) => {
    if (u === v) return;
    const a = Math.min(u, v);
    const b = Math.max(u, v);
    const key = `${a}-${b}`;
    if (seen.has(key)) return;
    seen.add(key);
    edges.push([a, b]);
  };

  for (let i = 0; i < n - 1; i++) addEdge(i, i + 1);

  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (random() < density) addEdge(i, j);
    }
  }

  return { vertices, edges };
}

export function parseGraphData(text) {
  const lines = String(text)
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));

  const vertices = [];
  const edges = [];
  let mode = "vertices";

  for (const line of lines) {
    const parts = line.split(/\s+/);
    if (parts.length !== 2) continue;

    const a = Number(parts[0]);
    const b = Number(parts[1]);
    if (Number.isNaN(a) || Number.isNaN(b)) continue;

    if (mode === "vertices" && Number.isInteger(a) && !Number.isInteger(b)) {
      vertices.push({ id: a, weight: b });
      continue;
    }

    if (Number.isInteger(a) && Number.isInteger(b)) {
      mode = "edges";
      edges.push([a, b]);
    }
  }

  return { vertices, edges };
}

export function layoutGraph(vertices, edges, width, height) {
  const n = vertices.length;
  if (!n) return [];

  const points = vertices.map((_, i) => ({
    x: width * 0.5 + Math.cos((2 * Math.PI * i) / n) * width * 0.36,
    y: height * 0.5 + Math.sin((2 * Math.PI * i) / n) * height * 0.36,
  }));

  const idIndex = new Map(vertices.map((v, i) => [v.id, i]));
  const k = Math.sqrt((width * height) / n) * 0.76;

  for (let iter = 0; iter < 250; iter++) {
    const force = points.map(() => ({ x: 0, y: 0 }));

    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = points[i].x - points[j].x;
        let dy = points[i].y - points[j].y;
        const distance = Math.max(0.1, Math.hypot(dx, dy));
        const repulse = (k * k) / distance;

        dx /= distance;
        dy /= distance;

        force[i].x += dx * repulse;
        force[i].y += dy * repulse;
        force[j].x -= dx * repulse;
        force[j].y -= dy * repulse;
      }
    }

    for (const [u, v] of edges) {
      const iu = idIndex.get(u);
      const iv = idIndex.get(v);
      if (iu === undefined || iv === undefined) continue;

      let dx = points[iu].x - points[iv].x;
      let dy = points[iu].y - points[iv].y;
      const distance = Math.max(0.1, Math.hypot(dx, dy));
      const attract = ((distance * distance) / k) * 0.65;

      dx /= distance;
      dy /= distance;

      force[iu].x -= dx * attract;
      force[iu].y -= dy * attract;
      force[iv].x += dx * attract;
      force[iv].y += dy * attract;
    }

    const temperature = Math.max(0.22, 14 * (1 - iter / 250));

    for (let i = 0; i < n; i++) {
      force[i].x += (width * 0.5 - points[i].x) * 0.01;
      force[i].y += (height * 0.5 - points[i].y) * 0.01;

      const magnitude = Math.max(1, Math.hypot(force[i].x, force[i].y));
      points[i].x += (force[i].x / magnitude) * Math.min(magnitude, temperature);
      points[i].y += (force[i].y / magnitude) * Math.min(magnitude, temperature);

      points[i].x = clamp(points[i].x, 18, width - 18);
      points[i].y = clamp(points[i].y, 18, height - 18);
    }
  }

  return vertices.map((vertex, i) => ({ ...vertex, x: points[i].x, y: points[i].y }));
}

export function buildAdjacency(graph) {
  const adjacency = new Map(graph.vertices.map((v) => [v.id, new Set()]));
  for (const [u, v] of graph.edges) {
    if (!adjacency.has(u) || !adjacency.has(v)) continue;
    adjacency.get(u).add(v);
    adjacency.get(v).add(u);
  }
  return adjacency;
}

export function countComponents(graph) {
  const adj = buildAdjacency(graph);
  const visited = new Set();
  let components = 0;

  for (const vertex of graph.vertices) {
    if (visited.has(vertex.id)) continue;
    components += 1;

    const stack = [vertex.id];
    visited.add(vertex.id);

    while (stack.length) {
      const u = stack.pop();
      for (const w of adj.get(u) || []) {
        if (!visited.has(w)) {
          visited.add(w);
          stack.push(w);
        }
      }
    }
  }

  return components;
}

export function computeGraphStats(graph) {
  if (!graph) return null;

  const n = graph.vertices.length;
  const m = graph.edges.length;
  const totalWeight = graph.vertices.reduce((sum, v) => sum + Number(v.weight || 0), 0);

  const degreeMap = new Map(graph.vertices.map((v) => [v.id, 0]));
  for (const [u, v] of graph.edges) {
    if (degreeMap.has(u)) degreeMap.set(u, degreeMap.get(u) + 1);
    if (degreeMap.has(v)) degreeMap.set(v, degreeMap.get(v) + 1);
  }

  const degreeValues = [...degreeMap.values()];
  const avgDegree = degreeValues.length
    ? degreeValues.reduce((sum, d) => sum + d, 0) / degreeValues.length
    : 0;

  return {
    n,
    m,
    totalWeight,
    avgWeight: n ? totalWeight / n : 0,
    density: n > 1 ? (2 * m) / (n * (n - 1)) : 0,
    avgDegree,
    components: countComponents(graph),
  };
}
