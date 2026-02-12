import React from "react";
import clsx from "clsx";
import { Gauge, Loader2, Minus, Play, Plus, UploadCloud, WandSparkles } from "lucide-react";
import { formatNumber } from "../../utils/format";

const panel = "rounded-[26px] border border-[var(--border)] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] p-5 shadow-[var(--shadow)] backdrop-blur-[18px] backdrop-saturate-[135%]";

export default function ControlPanel({
  source,
  fileRef,
  onLoadEmbedded,
  onUpload,
  uploadErr,
  kMode,
  setKMode,
  capKInput,
  setCapKInput,
  onStepK,
  manualK,
  optimizeGoal,
  setOptimizeGoal,
  optimizeTrials,
  onOptimizeTrialsChange,
  popSize,
  onPopSizeChange,
  generations,
  onGenerationsChange,
  canSolve,
  running,
  onSolve,
  runErr,
  canBenchmark,
  benchmarkRunning,
  onRunBenchmark,
  benchmarkErr,
  graphStats,
  activeK,
  kBounds,
}) {
  return (
    <section className={clsx(panel, "reveal delay-2 min-w-0")}>
      <div className="mb-4">
        <h2 className="m-0 text-lg font-bold tracking-tight">Model Control</h2>
        <p className="mt-1 text-sm text-[var(--text-muted)]">Configure dataset, capacity strategy, and solver settings.</p>
      </div>

      {/* Instance selector */}
      <ControlGroup label="Instance">
        <div className="grid grid-cols-2 gap-2.5">
          <button
            onClick={onLoadEmbedded}
            className="flex min-h-[44px] cursor-pointer items-center justify-center gap-2 rounded-[var(--radius-md)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3 py-2.5 text-sm font-semibold text-[var(--text-dim)] transition-all duration-150 hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] hover:shadow-[var(--shadow-btn)]"
          >
            <WandSparkles size={15} />
            Embedded 100V
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            className="flex min-h-[44px] cursor-pointer items-center justify-center gap-2 rounded-[var(--radius-md)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3 py-2.5 text-sm font-semibold text-[var(--text-dim)] transition-all duration-150 hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] hover:shadow-[var(--shadow-btn)]"
          >
            <UploadCloud size={15} />
            Upload .txt
          </button>
          <input ref={fileRef} type="file" accept=".txt,.csv,.dat" className="hidden" onChange={onUpload} />
        </div>
        {uploadErr && <p className="mt-2 text-sm font-semibold text-[var(--danger)]">{uploadErr}</p>}
      </ControlGroup>

      {/* Capacity strategy */}
      <ControlGroup label="Capacity Strategy">
        <div className="relative grid grid-cols-2 overflow-hidden rounded-[12px] border border-[var(--border)]">
          <div
            className="pointer-events-none absolute inset-y-0 w-1/2 rounded-[11px] bg-[color-mix(in_srgb,var(--accent)_14%,var(--panel-strong))] transition-transform duration-200"
            style={{ transform: kMode === "auto" ? "translateX(100%)" : "translateX(0)" }}
          />
          <button
            className={clsx(
              "relative z-1 cursor-pointer border-0 bg-transparent py-3 text-sm font-semibold transition-colors",
              kMode === "manual" ? "text-[var(--accent)]" : "text-[var(--text-muted)]"
            )}
            onClick={() => setKMode("manual")}
          >
            Manual K
          </button>
          <button
            className={clsx(
              "relative z-1 cursor-pointer border-0 bg-transparent py-3 text-sm font-semibold transition-colors",
              kMode === "auto" ? "text-[var(--accent)]" : "text-[var(--text-muted)]"
            )}
            onClick={() => setKMode("auto")}
          >
            Auto Optimize K
          </button>
        </div>

        {kMode === "manual" ? (
          <div className="mt-3 grid grid-cols-[auto_1fr] items-center gap-3">
            <span className="text-sm text-[var(--text-muted)]">K Stepper</span>
            <div className="grid grid-cols-[44px_minmax(0,1fr)_44px] gap-1.5">
              <button
                type="button"
                aria-label="Decrease K"
                onClick={() => onStepK(-1)}
                disabled={manualK === null || manualK <= 1}
                className="inline-grid h-[44px] cursor-pointer place-items-center rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] text-[var(--text-dim)] transition-colors hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] hover:text-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Minus size={16} />
              </button>
              <input
                type="number"
                min={1}
                step={1}
                value={capKInput}
                onChange={(event) => setCapKInput(event.target.value)}
                className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-center text-base text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
              />
              <button
                type="button"
                aria-label="Increase K"
                onClick={() => onStepK(1)}
                className="inline-grid h-[44px] cursor-pointer place-items-center rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] text-[var(--text-dim)] transition-colors hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] hover:text-[var(--accent)]"
              >
                <Plus size={16} />
              </button>
            </div>
          </div>
        ) : (
          <>
            <FieldRow label="Goal">
              <select
                value={optimizeGoal}
                onChange={(event) => setOptimizeGoal(event.target.value)}
                className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
              >
                <option value="min-feasible-k">Min feasible K</option>
                <option value="best-weight">Best objective weight</option>
              </select>
            </FieldRow>
            <FieldRow label="Trial budget">
              <input
                type="number"
                min={6}
                max={36}
                step={2}
                value={optimizeTrials}
                onChange={(event) => onOptimizeTrialsChange(event.target.value)}
                className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
              />
            </FieldRow>
          </>
        )}

        {kMode === "manual" && manualK === null && (
          <p className="mt-2 text-sm font-semibold text-[var(--danger)]">K must be an integer &ge; 1.</p>
        )}
      </ControlGroup>

      {/* Evolution parameters */}
      <ControlGroup label="Evolution Parameters">
        <div className="mt-1 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2.5">
          <span className="text-sm text-[var(--text-muted)]">Population <strong className="text-[var(--text)]">{popSize}</strong></span>
          <input
            type="range"
            min={10}
            max={120}
            step={5}
            value={popSize}
            onChange={(event) => onPopSizeChange(event.target.value)}
            className="w-full accent-[var(--accent)]"
          />
          <span className="text-sm text-[var(--text-muted)]">Generations <strong className="text-[var(--text)]">{generations}</strong></span>
          <input
            type="range"
            min={20}
            max={220}
            step={10}
            value={generations}
            onChange={(event) => onGenerationsChange(event.target.value)}
            className="w-full accent-[var(--accent)]"
          />
        </div>
      </ControlGroup>

      {/* Action buttons */}
      <div className="mt-5 grid gap-3">
        <button
          className="flex h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--accent)_62%,#000_20%)] bg-[linear-gradient(140deg,var(--accent),var(--accent-soft))] text-sm font-bold text-white shadow-[var(--shadow-btn)] transition-all duration-150 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-48 disabled:shadow-none disabled:hover:translate-y-0"
          disabled={!canSolve}
          onClick={onSolve}
        >
          {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {running ? "Computing..." : "Run Algorithms"}
        </button>
        <button
          className="flex h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_12%,var(--panel-strong))] text-sm font-bold text-[var(--accent)] transition-all duration-150 hover:-translate-y-0.5 hover:shadow-[var(--shadow-btn)] disabled:cursor-not-allowed disabled:opacity-48 disabled:hover:translate-y-0"
          disabled={!canBenchmark}
          onClick={onRunBenchmark}
        >
          {benchmarkRunning ? <Loader2 size={16} className="animate-spin" /> : <Gauge size={16} />}
          {benchmarkRunning ? "Benchmarking..." : "Run Density Benchmark"}
        </button>
        {runErr && <p className="text-sm font-semibold text-[var(--danger)]">{runErr}</p>}
        {benchmarkErr && <p className="text-sm font-semibold text-[var(--danger)]">{benchmarkErr}</p>}
      </div>

      {/* Metrics grid */}
      {graphStats && (
        <div className="mt-4 grid grid-cols-2 gap-2.5">
          <MetricChip label="|V|" value={graphStats.n} />
          <MetricChip label="|E|" value={graphStats.m} />
          <MetricChip label="Density" value={formatNumber(graphStats.density, 3)} />
          <MetricChip label="Avg Degree" value={formatNumber(graphStats.avgDegree, 2)} />
          <MetricChip label="Avg Weight" value={formatNumber(graphStats.avgWeight, 2)} />
          <MetricChip label="Components" value={graphStats.components} />
          <MetricChip label="K" value={activeK} accent />
          <MetricChip label="Source" value={source} title={source} />
        </div>
      )}

      {kBounds && (
        <p className="mt-3 text-sm text-[var(--text-muted)]">
          K bounds from graph: {kBounds.minK} .. {kBounds.maxK}
        </p>
      )}
    </section>
  );
}

function ControlGroup({ label, children }) {
  return (
    <div className="mt-4 border-t border-[color-mix(in_srgb,var(--border)_74%,transparent)] pt-4">
      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.095em] text-[var(--text-muted)]">{label}</label>
      {children}
    </div>
  );
}

function FieldRow({ label, children }) {
  return (
    <div className="mt-3 grid grid-cols-[auto_1fr] items-center gap-3">
      <span className="text-sm text-[var(--text-muted)]">{label}</span>
      {children}
    </div>
  );
}

function MetricChip({ label, value, accent, title }) {
  return (
    <div
      className={clsx(
        "flex items-center justify-between gap-2 rounded-[12px] border bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-3.5",
        accent
          ? "border-[color-mix(in_srgb,var(--accent)_50%,var(--border))] shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--accent)_20%,transparent)]"
          : "border-[var(--border)]"
      )}
      title={title}
    >
      <span className="text-xs font-bold uppercase tracking-[0.07em] text-[var(--text-muted)]">{label}</span>
      <strong className="max-w-[140px] truncate text-base">{value}</strong>
    </div>
  );
}
