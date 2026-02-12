import React from "react";

export default function StatRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[11px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-3 text-sm text-[var(--text-dim)]">
      <span className="text-[var(--text-muted)]">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
