import React, { useCallback, useMemo, useState } from "react";
import clsx from "clsx";
import { FlaskConical, Loader2 } from "lucide-react";
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
import { formatNumber, formatPercent } from "../../utils/format";
import { copyTextToClipboard } from "../../utils/clipboard";

const panel =
  "rounded-[26px] border border-[var(--border)] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] p-5 shadow-[var(--shadow)] backdrop-blur-[18px] backdrop-saturate-[135%]";

const SCALE_ORDER = ["small", "medium", "large"];
const SCALE_TITLES = {
  small: "Small Scale",
  medium: "Medium Scale",
  large: "Large Scale",
};
const fallbackMethodColors = ["#0f766e", "#0e7490", "#0369a1", "#4338ca", "#be123c", "#a16207"];

function methodColor(methodKey, index) {
  const known = METHODS.find((method) => method.key === methodKey);
  return known?.color || fallbackMethodColors[index % fallbackMethodColors.length];
}

function methodOrder(methodKeys) {
  const rank = new Map(METHODS.map((method, index) => [method.key, index]));
  return [...methodKeys].sort((a, b) => (rank.get(a) ?? 999) - (rank.get(b) ?? 999));
}

function formatList(values) {
  if (!Array.isArray(values) || !values.length) return "-";
  return values.join(", ");
}

function ChartCard({ title, data, xKey, methodKeys, chartTheme }) {
  return (
    <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] p-3">
      <p className="mb-2 text-sm font-semibold text-[var(--text-dim)]">{title}</p>
      {data.length ? (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 10, left: -12, bottom: 6 }}>
            <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
            <XAxis dataKey={xKey} tick={{ fill: chartTheme.axis, fontSize: 12 }} />
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
                dot={{ r: 3.2 }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-[280px] items-center justify-center rounded-[10px] border border-dashed border-[color-mix(in_srgb,var(--border-strong)_70%,transparent)] text-sm text-[var(--text-muted)]">
          No data in this scope.
        </div>
      )}
    </div>
  );
}

function KChartCard({ title, data, xKey, chartTheme }) {
  return (
    <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] p-3">
      <p className="mb-2 text-sm font-semibold text-[var(--text-dim)]">{title}</p>
      {data.length ? (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 10, left: -12, bottom: 6 }}>
            <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
            <XAxis dataKey={xKey} tick={{ fill: chartTheme.axis, fontSize: 12 }} />
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
              dot={{ r: 3.2 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-[280px] items-center justify-center rounded-[10px] border border-dashed border-[color-mix(in_srgb,var(--border-strong)_70%,transparent)] text-sm text-[var(--text-muted)]">
          No K data in this scope.
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3.5 py-3">
      <p className="m-0 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 text-base font-bold text-[var(--text-dim)]">{value}</p>
    </div>
  );
}

export default function PresetScaleTestsPanel({
  presetScaleTests,
  presetRunning,
  presetErr,
  chartTheme,
}) {
  const [activeScale, setActiveScale] = useState("small");
  const [rawJsonCopyStatus, setRawJsonCopyStatus] = useState("idle");
  const meta = presetScaleTests?.meta || {};
  const selection = presetScaleTests?.selection || {};
  const requestedScales = Array.isArray(meta.targetScales) && meta.targetScales.length
    ? SCALE_ORDER.filter((scaleKey) => meta.targetScales.includes(scaleKey))
    : SCALE_ORDER;
  const scaleBuckets = presetScaleTests?.presetScaleTests?.scaleBuckets || {};
  const availableScaleKeys = requestedScales.filter((key) => Object.prototype.hasOwnProperty.call(scaleBuckets, key));
  const selectedScaleKey = availableScaleKeys.includes(activeScale)
    ? activeScale
    : availableScaleKeys[0] || "small";
  const activeBucket = scaleBuckets[selectedScaleKey] || null;
  const activeSelection = selection[selectedScaleKey] || {};
  const activePairCoverage = activeSelection.pairCoverage || [];
  const methodKeys = useMemo(
    () => methodOrder(Object.keys(activeBucket?.methodSummary || {})),
    [activeBucket]
  );
  const totalGraphs = Number(meta?.graphCount || 0);
  const selectedNodePreset =
    selectedScaleKey === "small"
      ? meta.smallScales
      : selectedScaleKey === "medium"
        ? meta.mediumScales
        : meta.largeScales;
  const ratioPreset = meta.ratios || [];
  const analyzedNodeCounts = (activeBucket?.byNodeCount || []).map((row) => row.nodeCount);
  const analyzedRatios = (activeBucket?.byConnectivityRatio || []).map((row) => row.connectivityRatio);
  const missingNodeCounts = (selectedNodePreset || []).filter(
    (nodeCount) => !analyzedNodeCounts.includes(nodeCount)
  );
  const missingRatios = ratioPreset.filter(
    (ratioValue) => !analyzedRatios.includes(ratioValue)
  );
  const datasetCount = Number(selection.selectedCount || 0);
  const selectedPairCount = Number(selection.selectedPairCount || 0);
  const syntheticCount = Number(meta.syntheticGeneratedCount || 0);
  const syntheticEnabled = Boolean(meta.syntheticEnabled);
  const optimizeEnabled = Boolean(meta.optimizeK);
  const optimizeGoal = meta.optimizeGoal || "best-weight";
  const rawPresetJson = useMemo(
    () => JSON.stringify(presetScaleTests, null, 2),
    [presetScaleTests]
  );
  const copyRawPresetJson = useCallback(async () => {
    const copied = await copyTextToClipboard(rawPresetJson);
    setRawJsonCopyStatus(copied ? "copied" : "error");
    setTimeout(() => setRawJsonCopyStatus("idle"), 1800);
  }, [rawPresetJson]);

  return (
    <section className={clsx(panel, "reveal delay-6 min-w-0")}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-bold tracking-tight">Preset Scale Tests</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Small/medium/large preset evaluation with weight, cover-size, and K trends by node count and m/n ratio.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-2 text-sm font-semibold text-[var(--text-dim)]">
          <FlaskConical size={15} />
          {totalGraphs} graphs
        </span>
      </div>

      {presetRunning && (
        <div className="mb-4 flex items-center gap-2 rounded-[12px] border border-dashed border-[color-mix(in_srgb,var(--accent)_50%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] px-4 py-3 text-sm font-semibold text-[var(--accent)]">
          <Loader2 size={16} className="animate-spin" />
          Preset scale tests are running...
        </div>
      )}

      {presetErr && <p className="mb-4 text-sm font-semibold text-[var(--danger)]">{presetErr}</p>}

      {presetScaleTests ? (
        <div className="grid gap-4">
          <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Dataset Files" value={datasetCount} />
            <StatCard label="(n,m) Pairs" value={selectedPairCount} />
            <StatCard label="Synthetic Files" value={syntheticCount} />
            <StatCard label="Synthetic Fill" value={syntheticEnabled ? "Enabled" : "Disabled"} />
            <StatCard
              label="K Strategy"
              value={optimizeEnabled ? `Auto (${optimizeGoal})` : `Manual/Fixed (${meta.capacityK ?? "-"})`}
            />
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-3 text-sm text-[var(--text-muted)]">
            <p className="m-0">
              Dagdeviren preset (active scale): <strong className="text-[var(--text-dim)]">n = [{formatList(selectedNodePreset)}]</strong>
            </p>
            <p className="mt-1">
              Connectivity ratios: <strong className="text-[var(--text-dim)]">m/n = [{formatList(ratioPreset)}]</strong> and edge count is calculated as <strong className="text-[var(--text-dim)]">m = (m/n) * n</strong>.
            </p>
            <p className="mt-1">
              Run scope: <strong className="text-[var(--text-dim)]">[{formatList(requestedScales)}]</strong>
            </p>
            <p className="mt-1">
              Total analyzed graphs: <strong className="text-[var(--text-dim)]">{totalGraphs}</strong>
            </p>
            <p className="mt-1">
              Analyzed values: <strong className="text-[var(--text-dim)]">n = [{formatList(analyzedNodeCounts)}]</strong> and <strong className="text-[var(--text-dim)]">m/n = [{formatList(analyzedRatios)}]</strong>
            </p>
            {(missingNodeCounts.length > 0 || missingRatios.length > 0) && (
              <p className="mt-1 text-[color-mix(in_srgb,var(--danger)_88%,var(--text-muted))]">
                Missing in this run: n = [{formatList(missingNodeCounts)}], m/n = [{formatList(missingRatios)}]
              </p>
            )}
          </div>

          {syntheticEnabled && syntheticCount > 0 && (
            <div className="rounded-[12px] border border-dashed border-[color-mix(in_srgb,var(--accent)_50%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] px-4 py-3 text-sm text-[var(--accent)]">
              Missing scale coverage was auto-filled with deterministic synthetic graphs so small, medium, and large groups are always testable.
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {requestedScales.map((scaleKey) => {
              const scale = scaleBuckets[scaleKey] || { graphCount: 0 };
              return (
                <button
                  key={scaleKey}
                  type="button"
                  onClick={() => setActiveScale(scaleKey)}
                  className={clsx(
                    "inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm font-bold transition-colors",
                    selectedScaleKey === scaleKey
                      ? "border-[color-mix(in_srgb,var(--accent)_52%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_14%,var(--panel-strong))] text-[var(--accent)]"
                      : "border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] text-[var(--text-dim)] hover:border-[color-mix(in_srgb,var(--accent)_42%,var(--border))]"
                  )}
                >
                  {SCALE_TITLES[scaleKey]}
                  <span className="text-xs text-[var(--text-muted)]">({scale.graphCount || 0})</span>
                </button>
              );
            })}
          </div>

          <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Active Scale" value={SCALE_TITLES[selectedScaleKey]} />
            <StatCard label="Graphs" value={activeBucket?.graphCount ?? 0} />
            <StatCard label="Node Groups" value={(activeBucket?.byNodeCount || []).length} />
            <StatCard
              label="Ratio Groups"
              value={(activeBucket?.byConnectivityRatio || []).length}
            />
          </div>

          <div className="grid gap-2.5 sm:grid-cols-2">
            <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3.5 py-3">
              <p className="m-0 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-muted)]">Active Scale Dataset Files</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-dim)]">{(activeSelection.selectedFiles || []).length}</p>
              <p className="mt-1 text-xs text-[var(--text-muted)] break-all">
                {(activeSelection.selectedFiles || []).join(", ") || "-"}
              </p>
            </div>
            <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3.5 py-3">
              <p className="m-0 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--text-muted)]">Active Scale Synthetic Files</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-dim)]">{(activeSelection.syntheticFiles || []).length}</p>
              <p className="mt-1 text-xs text-[var(--text-muted)] break-all">
                {(activeSelection.syntheticFiles || []).join(", ") || "-"}
              </p>
            </div>
          </div>

          <div className="overflow-x-auto rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-3">
            <p className="mb-1 text-sm font-semibold text-[var(--text-dim)]">
              Active Scale Coverage by (n, m, s)
            </p>
            <p className="mb-2 text-xs text-[var(--text-muted)]">
              {activePairCoverage.length} (n,m) pairs selected from dataset files.
            </p>
            {activePairCoverage.length ? (
              <table className="w-full min-w-[680px] border-separate border-spacing-y-1.5 text-sm">
                <thead>
                  <tr className="text-left text-[var(--text-muted)]">
                    <th className="px-2 py-1 font-semibold">n</th>
                    <th className="px-2 py-1 font-semibold">m</th>
                    <th className="px-2 py-1 font-semibold">m/n</th>
                    <th className="px-2 py-1 font-semibold">s count</th>
                    <th className="px-2 py-1 font-semibold">s values</th>
                  </tr>
                </thead>
                <tbody>
                  {activePairCoverage.map((row) => (
                    <tr
                      key={`n${row.n}_m${row.m}`}
                      className="rounded-[10px] bg-[color-mix(in_srgb,var(--panel)_88%,var(--panel-strong))] text-[var(--text-dim)]"
                    >
                      <td className="px-2 py-1.5 font-semibold">{row.n}</td>
                      <td className="px-2 py-1.5">{row.m}</td>
                      <td className="px-2 py-1.5">
                        {row.ratio !== null && row.ratio !== undefined ? formatNumber(row.ratio, 3) : "-"}
                      </td>
                      <td className="px-2 py-1.5">{row.sCount ?? 0}</td>
                      <td className="px-2 py-1.5 break-all">{(row.sValues || []).join(", ") || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="rounded-[10px] border border-dashed border-[color-mix(in_srgb,var(--border-strong)_70%,transparent)] px-3 py-4 text-sm text-[var(--text-muted)]">
                No dataset pair coverage in this scope.
              </div>
            )}
          </div>

          <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
            {methodKeys.map((methodKey, index) => {
              const row = (activeBucket?.methodSummary || {})[methodKey] || {};
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
                    Avg Weight: {row.avgWeight !== null ? formatNumber(row.avgWeight, 3) : "-"}
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Avg Cover Size: {row.avgCoverSize !== null ? formatNumber(row.avgCoverSize, 3) : "-"}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <ChartCard
              title="Node Count vs Avg Weight"
              data={activeBucket?.nodeWeightChart || []}
              xKey="nodeCount"
              methodKeys={methodKeys}
              chartTheme={chartTheme}
            />
            <ChartCard
              title="Node Count vs Avg Cover Size"
              data={activeBucket?.nodeCoverSizeChart || []}
              xKey="nodeCount"
              methodKeys={methodKeys}
              chartTheme={chartTheme}
            />
            <ChartCard
              title="Connectivity Ratio (m/n) vs Avg Weight"
              data={activeBucket?.ratioWeightChart || []}
              xKey="connectivityRatio"
              methodKeys={methodKeys}
              chartTheme={chartTheme}
            />
            <ChartCard
              title="Connectivity Ratio (m/n) vs Avg Cover Size"
              data={activeBucket?.ratioCoverSizeChart || []}
              xKey="connectivityRatio"
              methodKeys={methodKeys}
              chartTheme={chartTheme}
            />
            <KChartCard
              title="Node Count vs Avg K"
              data={activeBucket?.nodeKChart || []}
              xKey="nodeCount"
              chartTheme={chartTheme}
            />
            <KChartCard
              title="Connectivity Ratio (m/n) vs Avg K"
              data={activeBucket?.ratioKChart || []}
              xKey="connectivityRatio"
              chartTheme={chartTheme}
            />
          </div>

          <div className="rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="m-0 text-sm font-semibold text-[var(--text-dim)]">Raw JSON</p>
              <button
                type="button"
                className={clsx(
                  "cursor-pointer rounded-full border px-3.5 py-1.5 text-xs font-bold transition-all",
                  rawJsonCopyStatus === "copied"
                    ? "border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_12%,var(--panel-strong))] text-[var(--accent)]"
                    : rawJsonCopyStatus === "error"
                      ? "border-[color-mix(in_srgb,var(--danger)_48%,var(--border))] bg-[color-mix(in_srgb,var(--danger)_10%,var(--panel-strong))] text-[var(--danger)]"
                      : "border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] text-[var(--text-dim)] hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))]"
                )}
                onClick={copyRawPresetJson}
              >
                {rawJsonCopyStatus === "copied"
                  ? "Copied"
                  : rawJsonCopyStatus === "error"
                    ? "Copy failed"
                    : "Copy"}
              </button>
            </div>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Complete preset response payload used to build charts and summary cards.
            </p>
            <pre className="mt-2 max-h-[360px] overflow-auto rounded-[10px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_98%,transparent)] p-3 font-mono text-xs leading-relaxed text-[var(--text-dim)]">
              {rawPresetJson}
            </pre>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-[14px] border border-dashed border-[color-mix(in_srgb,var(--border-strong)_75%,transparent)] bg-[color-mix(in_srgb,var(--panel-strong)_85%,transparent)] px-6 py-10 text-center">
          <FlaskConical size={32} className="mb-3 text-[var(--text-muted)] opacity-40" />
          <p className="text-sm text-[var(--text-muted)]">
            Run Preset Scale Tests to compare weight and cover set size across small, medium, and large scales.
          </p>
        </div>
      )}
    </section>
  );
}
