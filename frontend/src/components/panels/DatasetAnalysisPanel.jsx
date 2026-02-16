import React, { useMemo } from "react";
import clsx from "clsx";
import { Database, Loader2 } from "lucide-react";
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
import { METHODS } from "../../constants/ui";
import { formatMs, formatNumber, formatPercent } from "../../utils/format";

const panel =
  "rounded-[26px] border border-[var(--border)] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] p-5 shadow-[var(--shadow)] backdrop-blur-[18px] backdrop-saturate-[135%]";

const fallbackMethodColors = ["#0f766e", "#0e7490", "#0369a1", "#4338ca", "#be123c", "#a16207"];

function methodColor(methodKey, index) {
  const known = METHODS.find((method) => method.key === methodKey);
  return known?.color || fallbackMethodColors[index % fallbackMethodColors.length];
}

export default function DatasetAnalysisPanel({
  datasetAnalysis,
  datasetRunning,
  datasetErr,
  chartTheme,
}) {
  const graphRows = datasetAnalysis?.graphAnalysis?.graphs || [];
  const methodSummary = datasetAnalysis?.graphAnalysis?.summary?.methodSummary || {};
  const connectivityWeightChart =
    datasetAnalysis?.connectivityRatioVisualization?.weightChart || [];
  const connectivityKChart =
    datasetAnalysis?.connectivityRatioVisualization?.kChart || [];
  const nodeRuntimeChart = datasetAnalysis?.scaleVisualization?.nodeTimeChart || [];
  const nodeKChart = datasetAnalysis?.scaleVisualization?.nodeKChart || [];
  const methodKeys = useMemo(() => {
    const keys = Object.keys(methodSummary);
    const rank = new Map(METHODS.map((method, index) => [method.key, index]));
    return keys.sort((a, b) => (rank.get(a) ?? 999) - (rank.get(b) ?? 999));
  }, [methodSummary]);
  const scaleBadges = useMemo(() => {
    const counter = new Map();
    graphRows.forEach((row) => {
      const n = row?.scale?.n ?? row?.stats?.n ?? "-";
      const m = row?.scale?.m ?? row?.stats?.m ?? "-";
      const key = `n${n} / m${m}`;
      counter.set(key, (counter.get(key) || 0) + 1);
    });
    return [...counter.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(0, 12)
      .map(([label, count]) => ({ label, count }));
  }, [graphRows]);
  const totalRows = graphRows.length;
  const shownRows = Math.min(40, totalRows);
  const bestAvgMethod = useMemo(() => {
    const candidates = methodKeys
      .map((methodKey) => ({ methodKey, row: methodSummary[methodKey] || {} }))
      .filter(({ row }) => (row.validRuns || 0) > 0);
    if (!candidates.length) return "-";
    candidates.sort((a, b) => {
      const validA = Number(a.row.validRate || 0);
      const validB = Number(b.row.validRate || 0);
      if (validB !== validA) return validB - validA;
      const weightA = Number.isFinite(a.row.avgWeight) ? Number(a.row.avgWeight) : Number.POSITIVE_INFINITY;
      const weightB = Number.isFinite(b.row.avgWeight) ? Number(b.row.avgWeight) : Number.POSITIVE_INFINITY;
      return weightA - weightB;
    });
    return candidates[0].methodKey.toUpperCase();
  }, [methodKeys, methodSummary]);
  const rawDatasetJson = useMemo(
    () => JSON.stringify(datasetAnalysis, null, 2),
    [datasetAnalysis]
  );

  return (
    <section className={clsx(panel, "reveal delay-6 min-w-0")}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-bold tracking-tight">Dagdeviren Dataset Analysis</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Connectivity-ratio and scale analysis without importing external simulators.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-2 text-sm font-semibold text-[var(--text-dim)]">
          <Database size={15} />
          {datasetAnalysis?.meta?.graphCount || 0} graphs
        </span>
      </div>

      {datasetRunning && (
        <div className="mb-4 flex items-center gap-2 rounded-[12px] border border-dashed border-[color-mix(in_srgb,var(--accent)_50%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] px-4 py-3 text-sm font-semibold text-[var(--accent)]">
          <Loader2 size={16} className="animate-spin" />
          Dagdeviren analysis is running...
        </div>
      )}

      {datasetErr && <p className="mb-4 text-sm font-semibold text-[var(--danger)]">{datasetErr}</p>}

      {datasetAnalysis ? (
        <div className="grid gap-4">
          <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
            <QuickStat
              label="Processed Graphs"
              value={datasetAnalysis?.meta?.graphCount ?? 0}
            />
            <QuickStat
              label="Displayed Rows"
              value={`${shownRows}/${totalRows}`}
            />
            <QuickStat
              label="Ratio Count"
              value={datasetAnalysis?.meta?.ratios?.length ?? 0}
            />
            <QuickStat
              label="Best Avg Method"
              value={bestAvgMethod}
            />
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-3.5">
            <p className="m-0 text-sm font-semibold text-[var(--text-dim)]">Dataset Scope</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Filename filter:{" "}
              <strong className="text-[var(--text-dim)]">
                {datasetAnalysis?.meta?.filenameContains || "All files"}
              </strong>{" "}
              | Max files: <strong className="text-[var(--text-dim)]">{datasetAnalysis?.meta?.maxFiles}</strong>
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Ratios:{" "}
              <strong className="text-[var(--text-dim)]">
                {datasetAnalysis?.meta?.ratios?.length
                  ? datasetAnalysis.meta.ratios.join(", ")
                  : "Auto-discovered"}
              </strong>
              {" | "}
              Scale groups:{" "}
              <strong className="text-[var(--text-dim)]">
                small[{(datasetAnalysis?.meta?.smallScales || []).join(",") || "-"}], medium[
                {(datasetAnalysis?.meta?.mediumScales || []).join(",") || "-"}], large[
                {(datasetAnalysis?.meta?.largeScales || []).join(",") || "-"}]
              </strong>
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Capacity by scale:{" "}
              <strong className="text-[var(--text-dim)]">
                small={datasetAnalysis?.meta?.capacityByScale?.small ?? "-"}, medium=
                {datasetAnalysis?.meta?.capacityByScale?.medium ?? "-"}, large=
                {datasetAnalysis?.meta?.capacityByScale?.large ?? "-"}
              </strong>
            </p>
            {scaleBadges.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {scaleBadges.map((item) => (
                  <span
                    key={`${item.label}-${item.count}`}
                    className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel)_88%,var(--panel-strong))] px-3 py-1.5 text-xs font-semibold text-[var(--text-dim)]"
                  >
                    {item.label}
                    <span className="text-[var(--text-muted)]">({item.count})</span>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
            {methodKeys.map((methodKey, index) => {
              const row = methodSummary[methodKey] || {};
              return (
                <div
                  key={methodKey}
                  className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-3.5"
                >
                  <p className="m-0 text-sm font-bold" style={{ color: methodColor(methodKey, index) }}>
                    {methodKey.toUpperCase()}
                  </p>
                  <p className="mt-2 text-xs text-[var(--text-muted)]">
                    Valid: {row.validRuns || 0}/{row.attempted || 0} ({formatPercent((row.validRate || 0) * 100)})
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Avg W: {row.avgWeight !== null ? formatNumber(row.avgWeight, 3) : "-"}
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Avg T: {row.avgTimeMs !== null ? formatMs(row.avgTimeMs) : "-"}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="overflow-x-auto rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] p-3">
            <p className="mb-1 text-sm font-semibold text-[var(--text-dim)]">
              Per-File Dagdeviren Summary (n, m, s)
            </p>
            <p className="mb-2 text-xs text-[var(--text-muted)]">
              Showing first {shownRows} rows of {totalRows}. Use filters in the control panel to narrow scope.
            </p>
            <table className="w-full min-w-[820px] border-separate border-spacing-y-1.5 text-sm">
              <thead>
                <tr className="text-left text-[var(--text-muted)]">
                  <th className="px-2 py-1 font-semibold">File</th>
                  <th className="px-2 py-1 font-semibold">n</th>
                  <th className="px-2 py-1 font-semibold">m</th>
                  <th className="px-2 py-1 font-semibold">s</th>
                  <th className="px-2 py-1 font-semibold">m/n</th>
                  <th className="px-2 py-1 font-semibold">Scale</th>
                  <th className="px-2 py-1 font-semibold">|V|</th>
                  <th className="px-2 py-1 font-semibold">|E|</th>
                  <th className="px-2 py-1 font-semibold">K</th>
                  <th className="px-2 py-1 font-semibold">Best</th>
                </tr>
              </thead>
              <tbody>
                {graphRows.slice(0, 40).map((row) => (
                  <tr
                    key={row.file}
                    className="rounded-[10px] bg-[color-mix(in_srgb,var(--panel)_88%,var(--panel-strong))] text-[var(--text-dim)]"
                  >
                    <td className="px-2 py-1.5 font-semibold">{row.file}</td>
                    <td className="px-2 py-1.5">{row?.scale?.n ?? "-"}</td>
                    <td className="px-2 py-1.5">{row?.scale?.m ?? "-"}</td>
                    <td className="px-2 py-1.5">{row?.scale?.s ?? "-"}</td>
                    <td className="px-2 py-1.5">
                      {row?.ratio !== null && row?.ratio !== undefined ? formatNumber(row.ratio, 3) : "-"}
                    </td>
                    <td className="px-2 py-1.5">{row?.scaleBucket || "-"}</td>
                    <td className="px-2 py-1.5">{row?.stats?.n ?? "-"}</td>
                    <td className="px-2 py-1.5">{row?.stats?.m ?? "-"}</td>
                    <td className="px-2 py-1.5">{row?.capacityK ?? "-"}</td>
                    <td className="px-2 py-1.5">{row?.bestValidMethod?.toUpperCase() || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] p-3">
            <p className="mb-2 text-sm font-semibold text-[var(--text-dim)]">
              Connectivity Ratio vs Avg Weight
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={connectivityWeightChart} margin={{ top: 8, right: 10, left: -12, bottom: 6 }}>
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                <XAxis dataKey="connectivityRatio" tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} width={58} />
                <Tooltip
                  contentStyle={{
                    background: chartTheme.tooltipBg,
                    border: `1px solid ${chartTheme.tooltipBorder}`,
                    borderRadius: 12,
                  }}
                />
                <Legend />
                {methodKeys.map((methodKey, index) => (
                  <Line
                    key={methodKey}
                    type="monotone"
                    dataKey={methodKey}
                    stroke={methodColor(methodKey, index)}
                    strokeWidth={2.2}
                    dot={{ r: 3.4 }}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] p-3">
            <p className="mb-2 text-sm font-semibold text-[var(--text-dim)]">
              Node Count vs Avg Runtime
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={nodeRuntimeChart} margin={{ top: 8, right: 10, left: -12, bottom: 6 }}>
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                <XAxis dataKey="nodeCount" tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} width={58} />
                <Tooltip
                  contentStyle={{
                    background: chartTheme.tooltipBg,
                    border: `1px solid ${chartTheme.tooltipBorder}`,
                    borderRadius: 12,
                  }}
                />
                <Legend />
                {methodKeys.map((methodKey, index) => (
                  <Line
                    key={methodKey}
                    type="monotone"
                    dataKey={methodKey}
                    stroke={methodColor(methodKey, index)}
                    strokeWidth={2.2}
                    dot={{ r: 3.4 }}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] p-3">
            <p className="mb-2 text-sm font-semibold text-[var(--text-dim)]">
              Node Count vs Capacity K
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={nodeKChart} margin={{ top: 8, right: 10, left: -12, bottom: 6 }}>
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                <XAxis dataKey="nodeCount" tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} width={58} />
                <Tooltip
                  contentStyle={{
                    background: chartTheme.tooltipBg,
                    border: `1px solid ${chartTheme.tooltipBorder}`,
                    borderRadius: 12,
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avgCapacityK"
                  name="Avg K"
                  stroke="#d97706"
                  strokeWidth={2.4}
                  dot={{ r: 3.4 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="minCapacityK"
                  name="Min K"
                  stroke="#0ea5e9"
                  strokeWidth={1.8}
                  dot={{ r: 2.8 }}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="maxCapacityK"
                  name="Max K"
                  stroke="#ef4444"
                  strokeWidth={1.8}
                  dot={{ r: 2.8 }}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] p-3">
            <p className="mb-2 text-sm font-semibold text-[var(--text-dim)]">
              Connectivity Ratio vs Capacity K
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={connectivityKChart} margin={{ top: 8, right: 10, left: -12, bottom: 6 }}>
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                <XAxis dataKey="connectivityRatio" tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} width={58} />
                <Tooltip
                  contentStyle={{
                    background: chartTheme.tooltipBg,
                    border: `1px solid ${chartTheme.tooltipBorder}`,
                    borderRadius: 12,
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avgCapacityK"
                  name="Avg K"
                  stroke="#d97706"
                  strokeWidth={2.4}
                  dot={{ r: 3.4 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="minCapacityK"
                  name="Min K"
                  stroke="#0ea5e9"
                  strokeWidth={1.8}
                  dot={{ r: 2.8 }}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="maxCapacityK"
                  name="Max K"
                  stroke="#ef4444"
                  strokeWidth={1.8}
                  dot={{ r: 2.8 }}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-3">
            <p className="m-0 text-sm font-semibold text-[var(--text-dim)]">Raw JSON</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Complete dataset-analysis response payload used to render tables and charts.
            </p>
            <pre className="mt-2 max-h-[360px] overflow-auto rounded-[10px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_98%,transparent)] p-3 font-mono text-xs leading-relaxed text-[var(--text-dim)]">
              {rawDatasetJson}
            </pre>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-[14px] border border-dashed border-[color-mix(in_srgb,var(--border-strong)_75%,transparent)] bg-[color-mix(in_srgb,var(--panel-strong)_85%,transparent)] px-6 py-10 text-center">
          <Database size={32} className="mb-3 text-[var(--text-muted)] opacity-40" />
          <p className="text-sm text-[var(--text-muted)]">
            Run Dagdeviren dataset analysis from the control panel to populate charts.
          </p>
        </div>
      )}
    </section>
  );
}

function QuickStat({ label, value }) {
  return (
    <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3.5 py-3">
      <p className="m-0 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 text-base font-bold text-[var(--text-dim)]">{value}</p>
    </div>
  );
}
