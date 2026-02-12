import React from "react";
import clsx from "clsx";
import * as Tabs from "@radix-ui/react-tabs";
import { INSPECTOR_TABS } from "../../constants/ui";
import StatusBadge from "../common/StatusBadge";
import StatRow from "../common/StatRow";
import { clamp, formatMs, formatNumber, formatPercent } from "../../utils/format";

const panel = "rounded-[26px] border border-[var(--border)] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] p-5 shadow-[var(--shadow)] backdrop-blur-[18px] backdrop-saturate-[135%]";

export default function GraphStudio({
  stageRef,
  stageSize,
  methodRows,
  selectedMethod,
  setSelectedMethod,
  labelMode,
  setLabelMode,
  edgeViewMode,
  setEdgeViewMode,
  nodeScale,
  setNodeScale,
  edgeStrength,
  setEdgeStrength,
  edgeLimit,
  setEdgeLimit,
  positionedGraph,
  displayEdges,
  vertexMap,
  coverSet,
  hoverNode,
  setHoverNode,
  selectedNode,
  setSelectedNode,
  inspectorTab,
  setInspectorTab,
  inspectedInfo,
  activeMethod,
}) {
  return (
    <section className={clsx(panel, "reveal delay-3 min-w-0")} ref={stageRef}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-bold tracking-tight">Interactive Graph Studio</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">Force-directed graph view with node selection and method overlays.</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold uppercase tracking-[0.095em] text-[var(--text-muted)]">Label</label>
          <select
            value={labelMode}
            onChange={(event) => setLabelMode(event.target.value)}
            className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2 text-sm text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:outline-0"
          >
            <option value="none">None</option>
            <option value="id">Node ID</option>
            <option value="weight">Weight</option>
          </select>
        </div>
      </div>

      {/* Horizontal toolbar */}
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <ToolSlider label="Node Size" value={nodeScale.toFixed(1)} min={0.8} max={2.2} step={0.1} current={nodeScale} onChange={(v) => setNodeScale(Number(v))} />
        <ToolSlider label="Edge Emphasis" value={edgeStrength.toFixed(1)} min={0.4} max={1.4} step={0.1} current={edgeStrength} onChange={(v) => setEdgeStrength(Number(v))} />
        <div className="flex flex-col gap-1">
          <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">Edge View</span>
          <select
            value={edgeViewMode}
            onChange={(event) => setEdgeViewMode(event.target.value)}
            className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] px-3 py-2 text-sm text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:outline-0"
          >
            <option value="all">All</option>
            <option value="cover-related">Cover related</option>
            <option value="cover-core">Cover core</option>
            <option value="hover-local">Hover local</option>
            <option value="uncovered-only">Uncovered only</option>
          </select>
        </div>
      </div>

      {/* Method chips */}
      <div className="mb-4 flex flex-wrap gap-2.5">
        {methodRows.length ? (
          methodRows.map((method) => (
            <button
              key={method.key}
              className={clsx(
                "inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold transition-all duration-150 hover:-translate-y-0.5",
                method.key === selectedMethod
                  ? "border-[color-mix(in_srgb,var(--chip)_56%,var(--border))] text-[var(--chip)] shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--chip)_22%,transparent),0_0_12px_color-mix(in_srgb,var(--chip)_18%,transparent)]"
                  : "border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] text-[var(--text-dim)]"
              )}
              style={{ "--chip": method.color }}
              onClick={() => setSelectedMethod(method.key)}
            >
              <span
                className="inline-grid h-5 w-5 place-items-center rounded-full text-xs"
                style={{ color: method.color, background: `color-mix(in srgb, ${method.color} 14%, transparent)` }}
              >
                {method.mark}
              </span>
              {method.label}
            </button>
          ))
        ) : (
          <p className="text-sm text-[var(--text-muted)]">Run solver to activate method selection.</p>
        )}
      </div>

      {/* Canvas + Inspector */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_340px]">
        <div
          className="min-h-[300px] overflow-hidden rounded-[19px] border border-[var(--border)]"
          style={{
            "--active-method": activeMethod?.color || "var(--accent)",
            background: `radial-gradient(220px 130px at 12% 10%, color-mix(in srgb, var(--accent-soft) 16%, transparent), transparent 82%),
              radial-gradient(280px 180px at 90% 88%, color-mix(in srgb, var(--accent) 15%, transparent), transparent 86%),
              color-mix(in srgb, var(--panel-strong) 95%, transparent)`,
          }}
        >
          <svg viewBox={`0 0 ${stageSize.width} ${stageSize.height}`} className="block h-auto w-full" role="img" aria-label="Graph visualization">
            {displayEdges.map(([u, v], index) => {
              const a = vertexMap.get(u);
              const b = vertexMap.get(v);
              if (!a || !b) return null;

              const bothCovered = coverSet.has(u) && coverSet.has(v);
              const singleCovered = coverSet.has(u) || coverSet.has(v);

              return (
                <line
                  key={`${u}-${v}-${index}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  className={bothCovered ? "edge both" : singleCovered ? "edge one" : "edge"}
                  style={{
                    opacity: bothCovered ? 0.86 : singleCovered ? 0.64 : 0.42,
                    strokeWidth: bothCovered ? 1.8 * edgeStrength : 1 * edgeStrength,
                  }}
                />
              );
            })}

            {positionedGraph?.vertices.map((vertex) => {
              const isHover = hoverNode === vertex.id;
              const isSelected = selectedNode === vertex.id;
              const inCover = coverSet.has(vertex.id);
              const baseRadius = clamp(3.3 + Number(vertex.weight) * 0.03, 3.6, 8.8) * nodeScale;
              const showLabel =
                labelMode !== "none" &&
                (positionedGraph.vertices.length <= 80 || isHover || isSelected || inCover || labelMode === "id");

              return (
                <g key={vertex.id} transform={`translate(${vertex.x} ${vertex.y})`}>
                  {inCover && <circle r={baseRadius + 5} className="node-glow" />}
                  <circle
                    r={baseRadius + (isHover || isSelected ? 2 : 0)}
                    className={inCover ? "node in-cover" : "node"}
                    data-selected={isSelected}
                    onMouseEnter={() => setHoverNode(vertex.id)}
                    onMouseLeave={() => setHoverNode(null)}
                    onClick={() => setSelectedNode((current) => (current === vertex.id ? null : vertex.id))}
                  />
                  {showLabel && (
                    <text className="node-label" textAnchor="middle" dominantBaseline="central">
                      {labelMode === "id" ? vertex.id : Math.round(vertex.weight)}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        {/* Inspector with Radix Tabs */}
        <Tabs.Root
          value={inspectorTab}
          onValueChange={setInspectorTab}
          className="flex min-h-[340px] flex-col rounded-[var(--radius-md)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-4"
        >
          <Tabs.List className="grid grid-cols-3 gap-1.5">
            {INSPECTOR_TABS.map((tab) => (
              <Tabs.Trigger
                key={tab.value}
                value={tab.value}
                className={clsx(
                  "cursor-pointer rounded-full border px-3 py-2 text-sm font-bold transition-colors",
                  "data-[state=active]:border-[color-mix(in_srgb,var(--accent)_48%,var(--border))] data-[state=active]:text-[var(--accent)]",
                  "data-[state=inactive]:border-[var(--border)] data-[state=inactive]:bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] data-[state=inactive]:text-[var(--text-muted)]"
                )}
              >
                {tab.label}
              </Tabs.Trigger>
            ))}
          </Tabs.List>

          <div className="mt-4 flex flex-col gap-2">
            <Tabs.Content value="node" className="animate-fade-in">
              {inspectedInfo ? (
                <>
                  <StatRow label="Node" value={`v${inspectedInfo.id}`} />
                  <StatRow label="Weight" value={formatNumber(inspectedInfo.weight, 3)} />
                  <StatRow label="Degree" value={inspectedInfo.degree} />
                  <StatRow label="In Cover" value={inspectedInfo.inCover ? "Yes" : "No"} />
                  <StatRow label="Selection" value={selectedNode !== null ? "Pinned" : "Hover"} />
                </>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Hover or click a node to inspect details.</p>
              )}
            </Tabs.Content>

            <Tabs.Content value="solution" className="animate-fade-in">
              {activeMethod ? (
                <>
                  <StatRow label="Method" value={activeMethod.label} />
                  <StatRow label="Total Weight" value={formatNumber(activeMethod.totalWeight, 3)} />
                  <StatRow label="Cover Size" value={activeMethod.coverSize} />
                  <StatRow label="Gap" value={formatPercent(activeMethod.gapPct)} />
                  <StatRow label="Runtime" value={formatMs(activeMethod.time)} />
                </>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Run algorithms to populate solution details.</p>
              )}
            </Tabs.Content>

            <Tabs.Content value="validity" className="animate-fade-in">
              {activeMethod?.verification ? (
                <div className="grid gap-2">
                  <StatusBadge ok={activeMethod.verification.isCover} label="Vertex Cover" />
                  <StatusBadge ok={activeMethod.verification.isConnected} label="Connected" />
                  <StatusBadge ok={activeMethod.verification.capacityFeasible} label="Capacity" />
                  <StatusBadge ok={activeMethod.verification.isValid} label="Valid CCVC" />
                </div>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Run algorithms to inspect validity checks.</p>
              )}
            </Tabs.Content>
          </div>
        </Tabs.Root>
      </div>

      {/* Footer */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]" htmlFor="edge-limit">
            Edge limit
          </label>
          <input
            id="edge-limit"
            type="range"
            min={40}
            max={500}
            step={10}
            value={edgeLimit}
            onChange={(event) => setEdgeLimit(Number(event.target.value))}
            className="w-28 accent-[var(--accent)]"
          />
          <strong className="text-sm">{edgeLimit}</strong>
        </div>

        <div className="flex flex-wrap gap-4 text-sm text-[var(--text-muted)]">
          <span className="inline-flex items-center gap-2">
            <i className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--graph-edge-2)]" /> Both endpoints covered
          </span>
          <span className="inline-flex items-center gap-2">
            <i className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--graph-edge-1)]" /> One endpoint covered
          </span>
          <span className="inline-flex items-center gap-2">
            <i className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--graph-edge)]" /> Uncovered edge
          </span>
        </div>
      </div>
    </section>
  );
}

function ToolSlider({ label, value, min, max, step, current, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
        {label} <strong className="text-[var(--text)]">{value}</strong>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={current}
        onChange={(e) => onChange(e.target.value)}
        className="w-28 accent-[var(--accent)]"
      />
    </div>
  );
}
