import React from "react";
import clsx from "clsx";
import { Loader2, TrendingUp } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatNumber } from "../../utils/format";
import MathBlock from "../common/MathBlock";

const panel = "rounded-[26px] border border-[var(--border)] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] p-5 shadow-[var(--shadow)] backdrop-blur-[18px] backdrop-saturate-[135%]";

export default function BenchmarkPanel({
  benchmarkSeries,
  benchmarkRows,
  benchmarkMethods,
  benchmarkRunning,
  chartTheme,
}) {
  return (
    <section className={clsx(panel, "reveal delay-5 min-w-0")}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-bold tracking-tight">Density Benchmark</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">Performance on five synthetic instances from sparse to denser graphs.</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-2 text-sm font-semibold text-[var(--text-dim)]">
          n = 16
        </span>
      </div>

      {benchmarkRunning && (
        <div className="mb-4 flex items-center gap-2 rounded-[12px] border border-dashed border-[color-mix(in_srgb,var(--accent)_50%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] px-4 py-3 text-sm font-semibold text-[var(--accent)]">
          <Loader2 size={16} className="animate-spin" />
          Benchmark is running...
        </div>
      )}

      {benchmarkSeries.length ? (
        <>
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] p-3">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={benchmarkSeries} margin={{ top: 8, right: 10, left: -14, bottom: 6 }}>
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                <XAxis dataKey="instance" tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} width={52} />
                <Tooltip
                  contentStyle={{
                    background: chartTheme.tooltipBg,
                    border: `1px solid ${chartTheme.tooltipBorder}`,
                    borderRadius: 12,
                  }}
                />
                <Legend />
                {benchmarkMethods.map((method) => (
                  <Line
                    key={method.key}
                    type="monotone"
                    dataKey={method.key}
                    stroke={method.color}
                    strokeWidth={2.3}
                    dot={{ r: 3.5, fill: method.color }}
                    activeDot={{ r: 5.5 }}
                    name={method.label}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-4 flex flex-wrap gap-2.5">
            {benchmarkRows.map((row) => (
              <div
                key={row.id}
                className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-2.5 text-sm font-semibold text-[var(--text-dim)]"
              >
                {row.id}
                <span className="text-[var(--text-muted)]">
                  <MathBlock tex="\rho" /> {formatNumber(row.density, 2)}
                </span>
                {row.capacityK !== null && <span className="text-[var(--text-muted)]">K {row.capacityK}</span>}
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-[14px] border border-dashed border-[color-mix(in_srgb,var(--border-strong)_75%,transparent)] bg-[color-mix(in_srgb,var(--panel-strong)_85%,transparent)] px-6 py-10 text-center">
          <TrendingUp size={32} className="mb-3 text-[var(--text-muted)] opacity-40" />
          <p className="text-sm text-[var(--text-muted)]">Run Density Benchmark to populate comparison curves and K results.</p>
        </div>
      )}
    </section>
  );
}
