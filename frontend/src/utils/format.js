export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function parseManualK(input) {
  const parsed = Number(input);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 1) return null;
  return parsed;
}

export function formatNumber(value, digits = 1) {
  if (!Number.isFinite(value)) return "-";
  return value.toFixed(digits);
}

export function formatPercent(value) {
  if (!Number.isFinite(value)) return "-";
  return `${value.toFixed(1)}%`;
}

export function formatMs(value) {
  if (!Number.isFinite(value)) return "-";
  if (value < 1) return `${value.toFixed(2)}ms`;
  return `${value.toFixed(0)}ms`;
}
