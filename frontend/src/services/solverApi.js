import { API_BASE } from "../constants/ui";

async function postSolve(payload, contextLabel) {
  const response = await fetch(`${API_BASE}/solve`, {
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
