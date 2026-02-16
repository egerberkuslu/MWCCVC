import React, { useCallback, useMemo } from "react";
import clsx from "clsx";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { MODEL_EQUATIONS, WORKSPACE_TABS } from "../../constants/ui";
import { formatMs, formatNumber, formatPercent } from "../../utils/format";
import MathBlock from "../common/MathBlock";

const panel = "rounded-[26px] border border-[var(--border)] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] p-5 shadow-[var(--shadow)] backdrop-blur-[18px] backdrop-saturate-[135%]";

export default function WorkspacePanel({
  workspaceTab,
  setWorkspaceTab,
  methodRows,
  selectedMethod,
  setSelectedMethod,
  solverSummary,
  activeMethod,
  barsData,
  convergenceData,
  greedyBest,
  chartTheme,
  graphStats,
  activeK,
  latexTab,
  setLatexTab,
  latexByTab,
  solveMeta,
  results,
  datasetAnalysis,
  presetScaleTests,
}) {
  const copyLatex = useCallback(() => {
    navigator.clipboard?.writeText(latexByTab[latexTab] || "");
  }, [latexByTab, latexTab]);
  const rawWorkspacePayload = useMemo(() => {
    const payload = {};
    if (solveMeta || results) {
      payload.solve = {
        meta: solveMeta || null,
        results: results || null,
      };
    }
    if (datasetAnalysis) {
      payload.datasetAnalysis = datasetAnalysis;
    }
    if (presetScaleTests) {
      payload.presetScaleTests = presetScaleTests;
    }
    if (!Object.keys(payload).length) {
      payload.note = "Run solve, dataset analysis, or preset tests to populate raw data.";
    }
    return payload;
  }, [solveMeta, results, datasetAnalysis, presetScaleTests]);
  const rawWorkspaceJson = useMemo(
    () => JSON.stringify(rawWorkspacePayload, null, 2),
    [rawWorkspacePayload]
  );

  return (
    <section className={clsx(panel, "reveal delay-4 min-w-0")}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="m-0 text-lg font-bold tracking-tight">Workspace</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">Overview, insights, bars, convergence, paper figure, LaTeX lab, and raw JSON.</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-2 text-sm font-semibold text-[var(--text-dim)]">
          {methodRows.length ? `${methodRows.length} methods` : "Idle"}
        </span>
      </div>

      {/* Tab bar */}
      <div className="mb-4 flex flex-wrap gap-2">
        {WORKSPACE_TABS.map((tab) => {
          const Icon = tab.icon;
          const active = workspaceTab === tab.value;
          return (
            <button
              key={tab.value}
              className={clsx(
                "inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold transition-all duration-150",
                active
                  ? "border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_14%,var(--panel-strong))] text-[var(--accent)] shadow-[var(--shadow-sm)]"
                  : "border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] text-[var(--text-muted)] hover:text-[var(--text-dim)]"
              )}
              onClick={() => setWorkspaceTab(tab.value)}
            >
              <Icon size={15} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {workspaceTab === "overview" && (
        <div className="animate-fade-in flex flex-col gap-4">
          <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
            <Card title="Solution Ranking">
              {methodRows.length ? (
                <div className="mt-3 grid gap-2">
                  {methodRows.map((row, idx) => (
                    <button
                      key={row.key}
                      className={clsx(
                        "grid cursor-pointer grid-cols-[34px_minmax(120px,1fr)_90px_58px] items-center gap-2 rounded-[var(--radius-sm)] border border-l-[3px] px-3 py-2.5 text-sm text-[var(--text-dim)] transition-colors sm:grid-cols-[34px_minmax(120px,1fr)_90px_58px]",
                        row.key === selectedMethod
                          ? "border-[color-mix(in_srgb,var(--rank)_50%,var(--border))] bg-[color-mix(in_srgb,var(--rank)_10%,var(--panel-strong))]"
                          : "border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)]"
                      )}
                      style={{ "--rank": row.color, borderLeftColor: row.color }}
                      onClick={() => setSelectedMethod(row.key)}
                    >
                      <span className="font-extrabold" style={{ color: row.color }}>#{idx + 1}</span>
                      <span className="font-bold">{row.label}</span>
                      <span className="justify-self-end font-bold">{formatNumber(row.totalWeight, 3)}</span>
                      <span className="justify-self-end text-[var(--text-muted)]">{idx === 0 ? "best" : `+${formatNumber(row.gapPct, 1)}%`}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-[var(--text-muted)]">Run algorithms to generate ranking.</p>
              )}
            </Card>

            <Card title="Solver Summary">
              <div className="mt-3 grid grid-cols-2 gap-2.5">
                <SummaryCell label="Best Valid" value={solverSummary?.bestValid?.label || "-"} />
                <SummaryCell label="Fastest" value={solverSummary?.fastest?.label || "-"} />
                <SummaryCell label="Valid Solutions" value={solverSummary ? `${solverSummary.validCount}/${solverSummary.totalCount}` : "-"} />
                <SummaryCell
                  label="Active CapUtil"
                  value={
                    activeMethod?.verification?.totalCapacity > 0
                      ? formatPercent((activeMethod.verification.edgeCount / activeMethod.verification.totalCapacity) * 100)
                      : "-"
                  }
                />
              </div>
            </Card>
          </div>

          <Card title="Academic Comparison Table">
            {methodRows.length ? (
              <div className="mt-3 overflow-x-auto">
                <table className="academic-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Method</th>
                      <th><MathBlock tex="w(S)" /></th>
                      <th><MathBlock tex="|S|" /></th>
                      <th>Cover</th>
                      <th>Conn</th>
                      <th>Cap</th>
                      <th>Valid</th>
                      <th><MathBlock tex="\Delta\%" /></th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {methodRows.map((row, idx) => (
                      <tr key={row.key}>
                        <td>{idx + 1}</td>
                        <td style={{ color: row.color, fontWeight: 700 }}>{row.label}</td>
                        <td>{formatNumber(row.totalWeight, 3)}</td>
                        <td>{row.coverSize}</td>
                        <td>{row.verification?.isCover ? "\u2713" : "\u2717"}</td>
                        <td>{row.verification?.isConnected ? "\u2713" : "\u2717"}</td>
                        <td>{row.verification?.capacityFeasible ? "\u2713" : "\u2717"}</td>
                        <td>{row.valid ? "\u2713" : "\u2717"}</td>
                        <td>{formatNumber(row.gapPct, 2)}</td>
                        <td>{formatMs(row.time)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-2 text-sm text-[var(--text-muted)]">No comparison data available yet.</p>
            )}
          </Card>
        </div>
      )}

      {workspaceTab === "insights" && (
        <div className="animate-fade-in flex flex-col gap-4">
          <Card title="Graph Metrics">
            {graphStats ? (
              <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                <SummaryCell label={<MathBlock tex="|V|" />} value={graphStats.n} />
                <SummaryCell label={<MathBlock tex="|E|" />} value={graphStats.m} />
                <SummaryCell label={<MathBlock tex="\rho" />} value={formatNumber(graphStats.density, 3)} />
                <SummaryCell label="Avg Degree" value={formatNumber(graphStats.avgDegree, 2)} />
                <SummaryCell label="Avg Weight" value={formatNumber(graphStats.avgWeight, 2)} />
                <SummaryCell label="Components" value={graphStats.components} />
              </div>
            ) : (
              <p className="mt-2 text-sm text-[var(--text-muted)]">No graph loaded.</p>
            )}
          </Card>

          <Card title="Model Equations">
            <div className="mt-3 grid gap-2.5">
              {MODEL_EQUATIONS.map((eq) => (
                <div
                  key={eq.label}
                  className="flex items-center justify-between gap-3 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-3"
                >
                  <span className="text-sm font-semibold text-[var(--text-muted)]">{eq.label}</span>
                  <MathBlock tex={eq.tex} display className="text-base" />
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {workspaceTab === "bars" && (
        <div className="animate-fade-in flex flex-col gap-4">
          <Card title="Objective Weight Comparison" className="min-h-[300px]">
            {barsData.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={barsData} margin={{ top: 10, right: 10, left: -15, bottom: 8 }}>
                  <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                  <XAxis dataKey="name" tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                  <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      background: chartTheme.tooltipBg,
                      border: `1px solid ${chartTheme.tooltipBorder}`,
                      borderRadius: 12,
                    }}
                  />
                  <Bar dataKey="weight" fill="var(--accent)" radius={[10, 10, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="mt-2 text-sm text-[var(--text-muted)]">Run algorithms to visualize bars.</p>
            )}
          </Card>

          <Card title="Cover Size & Runtime" className="min-h-[300px]">
            {barsData.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={barsData} margin={{ top: 10, right: 10, left: -15, bottom: 8 }}>
                  <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                  <XAxis dataKey="name" tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                  <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      background: chartTheme.tooltipBg,
                      border: `1px solid ${chartTheme.tooltipBorder}`,
                      borderRadius: 12,
                    }}
                  />
                  <Legend />
                  <Bar dataKey="size" fill="var(--method-gccvc)" radius={[10, 10, 0, 0]} />
                  <Bar dataKey="time" fill="var(--method-exact)" radius={[10, 10, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="mt-2 text-sm text-[var(--text-muted)]">Run algorithms to visualize bars.</p>
            )}
          </Card>
        </div>
      )}

      {workspaceTab === "convergence" && (
        <div className="animate-fade-in flex flex-col gap-4">
          <Card title="HGA Convergence" className="min-h-[300px]">
            {convergenceData.length ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={convergenceData} margin={{ top: 10, right: 16, left: -10, bottom: 8 }}>
                  <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                  <XAxis dataKey="gen" tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                  <YAxis tick={{ fill: chartTheme.axis, fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      background: chartTheme.tooltipBg,
                      border: `1px solid ${chartTheme.tooltipBorder}`,
                      borderRadius: 12,
                    }}
                  />
                  <Line type="monotone" dataKey="bestWeight" stroke="var(--accent)" strokeWidth={2.6} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="mt-2 text-sm text-[var(--text-muted)]">Run HGA to populate convergence chart.</p>
            )}
          </Card>

          {convergenceData.length > 1 && (
            <Card title="Convergence Summary">
              <div className="mt-3 grid grid-cols-2 gap-2.5">
                <SummaryCell label="Initial" value={formatNumber(convergenceData[0].bestWeight, 3)} />
                <SummaryCell label="Final" value={formatNumber(convergenceData[convergenceData.length - 1].bestWeight, 3)} />
                <SummaryCell
                  label="Improvement"
                  value={formatNumber(convergenceData[0].bestWeight - convergenceData[convergenceData.length - 1].bestWeight, 3)}
                />
                <SummaryCell label="Greedy Best" value={greedyBest ? formatNumber(greedyBest, 3) : "-"} />
              </div>
            </Card>
          )}
        </div>
      )}

      {workspaceTab === "paper-figure" && (
        <div className="animate-fade-in flex flex-col gap-4">
          <Card title="Paper Figure Preview" className="min-h-[360px]">
            <p className="mt-1 text-sm text-[var(--text-muted)]">Publication-ready combined objective and convergence snapshots.</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="min-h-[260px] rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-2">
                {barsData.length ? (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={barsData} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
                      <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                      <XAxis dataKey="name" tick={{ fill: chartTheme.axis, fontSize: 11 }} />
                      <YAxis tick={{ fill: chartTheme.axis, fontSize: 11 }} />
                      <Bar dataKey="weight" fill="var(--accent)" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="p-4 text-sm text-[var(--text-muted)]">Run algorithms first.</p>
                )}
              </div>
              <div className="min-h-[260px] rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-2">
                {convergenceData.length ? (
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={convergenceData} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
                      <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 4" />
                      <XAxis dataKey="gen" tick={{ fill: chartTheme.axis, fontSize: 11 }} />
                      <YAxis tick={{ fill: chartTheme.axis, fontSize: 11 }} />
                      <Line type="monotone" dataKey="bestWeight" stroke="var(--method-exact)" strokeWidth={2.4} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="p-4 text-sm text-[var(--text-muted)]">Run HGA first.</p>
                )}
              </div>
            </div>
          </Card>
        </div>
      )}

      {workspaceTab === "latex" && (
        <div className="animate-fade-in flex flex-col gap-4">
          <Card title="LaTeX Comparison & Export">
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {["comparison", "bars", "convergence", "full"].map((t) => (
                <button
                  key={t}
                  className={clsx(
                    "cursor-pointer rounded-full border px-4 py-2 text-sm font-bold capitalize transition-colors",
                    latexTab === t
                      ? "border-[color-mix(in_srgb,var(--accent)_50%,var(--border))] text-[var(--accent)]"
                      : "border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] text-[var(--text-muted)]"
                  )}
                  onClick={() => setLatexTab(t)}
                >
                  {t}
                </button>
              ))}
              <button
                className="ml-auto cursor-pointer rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-4 py-2 text-sm font-bold text-[var(--text-dim)] transition-all hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))]"
                onClick={copyLatex}
              >
                Copy
              </button>
            </div>
            <pre className="mt-3 max-h-[360px] overflow-auto rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_98%,transparent)] p-4 font-mono text-sm leading-relaxed text-[var(--text-dim)]">
              {latexByTab[latexTab]}
            </pre>
          </Card>
        </div>
      )}

      {workspaceTab === "raw" && (
        <div className="animate-fade-in flex flex-col gap-4">
          <Card title="Raw JSON">
            <pre className="mt-3 max-h-[360px] overflow-auto rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_98%,transparent)] p-4 font-mono text-sm leading-relaxed text-[var(--text-dim)]">
              {rawWorkspaceJson}
            </pre>
          </Card>
        </div>
      )}

      {!methodRows.length && workspaceTab !== "raw" && (
        <div className="mt-3 rounded-[12px] border border-dashed border-[color-mix(in_srgb,var(--border-strong)_72%,transparent)] bg-[color-mix(in_srgb,var(--panel-strong)_82%,transparent)] p-4 text-center text-sm text-[var(--text-muted)]">
          Run algorithms to populate detailed workspace outputs.
        </div>
      )}

      {workspaceTab === "overview" && graphStats && (
        <p className="mt-3 text-sm text-[var(--text-muted)]">
          Figure context: |V|={graphStats.n}, |E|={graphStats.m}, K={activeK}
        </p>
      )}
    </section>
  );
}

function Card({ title, children, className = "" }) {
  return (
    <article
      className={clsx(
        "rounded-[var(--radius-md)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-4",
        className
      )}
    >
      <h3 className="m-0 text-base font-bold tracking-tight">{title}</h3>
      {children}
    </article>
  );
}

function SummaryCell({ label, value }) {
  return (
    <div className="rounded-[11px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3.5 py-3">
      <small className="block text-xs font-bold uppercase tracking-[0.08em] text-[var(--text-muted)]">{label}</small>
      <strong className="mt-1 block text-base tracking-tight">{value}</strong>
    </div>
  );
}
