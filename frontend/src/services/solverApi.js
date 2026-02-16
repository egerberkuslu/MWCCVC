import { API_BASE } from "../constants/ui";

async function postSolve(payload, contextLabel, endpoint = "/solve") {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `${contextLabel} API returned ${response.status}`);
  }

  return response.json();
}

export async function solveGraph(payload) {
  return postSolve(payload, "Solve");
}

export async function solveBenchmarkGraph(payload) {
  return postSolve(payload, "Benchmark");
}

export async function runDagdevirenAnalysis(payload) {
  return postSolve(payload, "Dagdeviren Analysis", "/analysis/dagdeviren/run");
}

export async function runDagdevirenPresetTests(payload) {
  return postSolve(payload, "Dagdeviren Preset Tests", "/analysis/dagdeviren/preset-tests");
}
