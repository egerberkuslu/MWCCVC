import React from "react";
import clsx from "clsx";
import {
  Database,
  Gauge,
  Loader2,
  Minus,
  Play,
  Plus,
  RotateCcw,
  Search,
  UploadCloud,
  WandSparkles,
} from "lucide-react";
import { formatNumber } from "../../utils/format";

const panel = "rounded-[26px] border border-[var(--border)] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] p-5 shadow-[var(--shadow)] backdrop-blur-[18px] backdrop-saturate-[135%]";
const PRESET_SCOPE_LABELS = {
  all: "All Scales",
  small: "Small",
  medium: "Medium",
  large: "Large",
};

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
  canDatasetAnalysis,
  datasetRunning,
  onRunDatasetAnalysis,
  datasetErr,
  canPresetScaleTests,
  presetScaleTestsRunning,
  onRunPresetScaleTests,
  presetScaleTestErr,
  presetScaleRunScope,
  onPresetScaleRunScopeChange,
  datasetNFilter,
  onDatasetNFilterChange,
  datasetMFilter,
  onDatasetMFilterChange,
  datasetSFilter,
  onDatasetSFilterChange,
  datasetFilterMode,
  onDatasetFilterModeChange,
  datasetFilenameRaw,
  onDatasetFilenameRawChange,
  datasetRatioFilterInput,
  onDatasetRatioFilterInputChange,
  datasetMaxFilesInput,
  onDatasetMaxFilesInputChange,
  datasetFilenameContains,
  onApplyDatasetPaperPreset,
  onClearDatasetFilters,
  graphStats,
  activeK,
  kBounds,
}) {
  const activePresetScope = PRESET_SCOPE_LABELS[presetScaleRunScope] ? presetScaleRunScope : "all";
  const presetRunLabel =
    activePresetScope === "all"
      ? "Run Preset Scale Tests"
      : `Run ${PRESET_SCOPE_LABELS[activePresetScope]} Scale Test`;
  const presetRunningLabel =
    activePresetScope === "all"
      ? "Running All Scale Tests..."
      : `Running ${PRESET_SCOPE_LABELS[activePresetScope]} Scale...`;

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

      <ControlGroup label="Dagdeviren Filter">
        <p className="mt-0 text-xs text-[var(--text-muted)]">
          Pick a filter style, then run dataset analysis directly from this panel.
        </p>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onApplyDatasetPaperPreset}
            className="inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-[var(--radius-sm)] border border-[color-mix(in_srgb,var(--accent)_50%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_12%,var(--panel-strong))] px-3 py-2 text-xs font-bold text-[var(--accent)] transition-colors hover:bg-[color-mix(in_srgb,var(--accent)_18%,var(--panel-strong))]"
          >
            <WandSparkles size={14} />
            Apply Paper Preset
          </button>
          <button
            type="button"
            onClick={onClearDatasetFilters}
            className="inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3 py-2 text-xs font-bold text-[var(--text-dim)] transition-colors hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))]"
          >
            <RotateCcw size={14} />
            Clear Filters
          </button>
        </div>

        <div className="mt-3 rounded-[12px] border border-[var(--border)] p-1">
          <div className="grid grid-cols-2 gap-1">
            <button
              type="button"
              onClick={() => onDatasetFilterModeChange("guided")}
              className={clsx(
                "cursor-pointer rounded-[9px] px-3 py-2 text-xs font-bold transition-colors",
                datasetFilterMode === "guided"
                  ? "bg-[color-mix(in_srgb,var(--accent)_16%,var(--panel-strong))] text-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-dim)]"
              )}
            >
              Guided (n,m,s)
            </button>
            <button
              type="button"
              onClick={() => onDatasetFilterModeChange("raw")}
              className={clsx(
                "cursor-pointer rounded-[9px] px-3 py-2 text-xs font-bold transition-colors",
                datasetFilterMode === "raw"
                  ? "bg-[color-mix(in_srgb,var(--accent)_16%,var(--panel-strong))] text-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-dim)]"
              )}
            >
              Filename Search
            </button>
          </div>
        </div>

        {datasetFilterMode === "guided" ? (
          <>
            <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
              <FieldBox label="n">
                <input
                  type="number"
                  min={1}
                  step={1}
                  placeholder="e.g. 100"
                  value={datasetNFilter}
                  onChange={(event) => onDatasetNFilterChange(event.target.value)}
                  className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
                />
              </FieldBox>
              <FieldBox label="m">
                <input
                  type="number"
                  min={1}
                  step={1}
                  placeholder="e.g. 400"
                  value={datasetMFilter}
                  onChange={(event) => onDatasetMFilterChange(event.target.value)}
                  className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
                />
              </FieldBox>
              <FieldBox label="s">
                <input
                  type="number"
                  min={1}
                  step={1}
                  placeholder="optional seed"
                  value={datasetSFilter}
                  onChange={(event) => onDatasetSFilterChange(event.target.value)}
                  className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
                />
              </FieldBox>
              <FieldBox label="Max Files">
                <input
                  type="number"
                  min={1}
                  max={400}
                  step={1}
                  value={datasetMaxFilesInput}
                  onChange={(event) => onDatasetMaxFilesInputChange(event.target.value)}
                  className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
                />
              </FieldBox>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[20, 100, 500, 1000].map((nValue) => (
                <button
                  key={nValue}
                  type="button"
                  onClick={() => onDatasetNFilterChange(String(nValue))}
                  className="cursor-pointer rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-2.5 py-1 text-xs font-semibold text-[var(--text-muted)] transition-colors hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] hover:text-[var(--accent)]"
                >
                  n={nValue}
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="mt-3">
            <FieldBox label="Filename contains">
              <input
                type="text"
                placeholder="e.g. n500_m2000_ or _s3.txt"
                value={datasetFilenameRaw}
                onChange={(event) => onDatasetFilenameRawChange(event.target.value)}
                className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
              />
            </FieldBox>
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              Use this when you want full control over pattern matching.
            </p>
          </div>
        )}

        <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
          <FieldBox label="Ratios (m/n)">
            <input
              type="text"
              placeholder="2,4,6,8"
              value={datasetRatioFilterInput}
              onChange={(event) => onDatasetRatioFilterInputChange(event.target.value)}
              className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_96%,transparent)] px-3 py-2.5 text-[var(--text)] focus:border-[color-mix(in_srgb,var(--accent)_56%,var(--border))] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)] focus:outline-0"
            />
          </FieldBox>
          <FieldBox label="Current filter preview">
            <div className="min-h-[42px] rounded-[var(--radius-sm)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] px-3 py-2 text-sm text-[var(--text-dim)]">
              {datasetFilenameContains || "All Dagdeviren files"}
            </div>
          </FieldBox>
        </div>

        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Paper topology groups: small [10, 15, 20, 25], medium [50, 100, 150, 200], large [250, 500, 750, 1000]
          with ratios m/n = 2, 4, 6, 8.
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          If both n and m are set, the run automatically uses ratio m/n for matching.
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Preset tests trace files by (n,m) pair and include all matching s-seed files.
        </p>
      </ControlGroup>

      <ControlGroup label="Preset Test Scope">
        <p className="mt-0 text-xs text-[var(--text-muted)]">
          Choose one scale to run separately, or run all scales together.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-1.5 rounded-[12px] border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] p-1">
          {Object.entries(PRESET_SCOPE_LABELS).map(([scopeKey, scopeLabel]) => (
            <button
              key={scopeKey}
              type="button"
              onClick={() => onPresetScaleRunScopeChange(scopeKey)}
              className={clsx(
                "cursor-pointer rounded-[9px] px-3 py-2 text-xs font-bold transition-colors",
                activePresetScope === scopeKey
                  ? "bg-[color-mix(in_srgb,var(--accent)_16%,var(--panel-strong))] text-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-dim)]"
              )}
            >
              {scopeLabel}
            </button>
          ))}
        </div>
      </ControlGroup>

      {/* Action buttons */}
      <div className="mt-5 grid gap-3">
        <button
          className="flex h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--accent)_62%,#000_20%)] bg-[linear-gradient(140deg,var(--accent),var(--accent-soft))] text-sm font-bold text-white shadow-[var(--shadow-btn)] transition-all duration-150 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-48 disabled:shadow-none disabled:hover:translate-y-0"
          disabled={!canDatasetAnalysis}
          onClick={onRunDatasetAnalysis}
        >
          {datasetRunning ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
          {datasetRunning ? "Analyzing Dataset..." : "Run Dagdeviren Analysis"}
        </button>
        <button
          className="flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--accent)_40%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_10%,var(--panel-strong))] text-sm font-bold text-[var(--accent)] transition-all duration-150 hover:-translate-y-0.5 hover:shadow-[var(--shadow-btn)] disabled:cursor-not-allowed disabled:opacity-48 disabled:hover:translate-y-0"
          disabled={!canPresetScaleTests}
          onClick={onRunPresetScaleTests}
        >
          {presetScaleTestsRunning ? <Loader2 size={16} className="animate-spin" /> : <Gauge size={16} />}
          {presetScaleTestsRunning ? presetRunningLabel : presetRunLabel}
        </button>
        <div className="grid gap-2 sm:grid-cols-2">
          <button
            className="flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_12%,var(--panel-strong))] text-sm font-bold text-[var(--accent)] transition-all duration-150 hover:-translate-y-0.5 hover:shadow-[var(--shadow-btn)] disabled:cursor-not-allowed disabled:opacity-48 disabled:hover:translate-y-0"
            disabled={!canSolve}
            onClick={onSolve}
          >
            {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {running ? "Computing..." : "Run Algorithms"}
          </button>
          <button
            className="flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_95%,transparent)] text-sm font-bold text-[var(--text-dim)] transition-all duration-150 hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] hover:shadow-[var(--shadow-btn)] disabled:cursor-not-allowed disabled:opacity-48 disabled:hover:translate-y-0"
            disabled={!canBenchmark}
            onClick={onRunBenchmark}
          >
            {benchmarkRunning ? <Loader2 size={16} className="animate-spin" /> : <Gauge size={16} />}
            {benchmarkRunning ? "Benchmarking..." : "Run Benchmark"}
          </button>
        </div>
        <div className="rounded-[12px] border border-dashed border-[color-mix(in_srgb,var(--accent)_38%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_8%,transparent)] px-3 py-2 text-xs text-[var(--text-muted)]">
          <Search size={13} className="mr-1 inline-block" />
          Tip: start with paper preset, run dataset analysis, then narrow down with n/m/s or filename search.
        </div>
        {runErr && <p className="text-sm font-semibold text-[var(--danger)]">{runErr}</p>}
        {benchmarkErr && <p className="text-sm font-semibold text-[var(--danger)]">{benchmarkErr}</p>}
        {datasetErr && <p className="text-sm font-semibold text-[var(--danger)]">{datasetErr}</p>}
        {presetScaleTestErr && <p className="text-sm font-semibold text-[var(--danger)]">{presetScaleTestErr}</p>}
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

function FieldBox({ label, children }) {
  return (
    <label className="grid gap-1">
      <span className="text-xs font-bold uppercase tracking-[0.075em] text-[var(--text-muted)]">{label}</span>
      {children}
    </label>
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
