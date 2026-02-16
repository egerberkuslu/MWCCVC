import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { DEFAULT_SEED, METHODS } from "./constants/ui";
import {
  buildAdjacency,
  buildDensityBenchmarkGraph,
  buildEmbeddedGraph,
  computeGraphStats,
  layoutGraph,
  parseGraphData,
} from "./utils/graph";
import { clamp, parseManualK } from "./utils/format";
import {
  buildLatexBarsCode,
  buildLatexComparisonCode,
  buildLatexConvergenceCode,
} from "./utils/latex";
import {
  runDagdevirenAnalysis,
  runDagdevirenPresetTests,
  solveBenchmarkGraph,
  solveGraph,
} from "./services/solverApi";
import HeaderBar from "./components/layout/HeaderBar";
import ControlPanel from "./components/panels/ControlPanel";
import GraphStudio from "./components/panels/GraphStudio";
import WorkspacePanel from "./components/panels/WorkspacePanel";
import BenchmarkPanel from "./components/panels/BenchmarkPanel";
import DatasetAnalysisPanel from "./components/panels/DatasetAnalysisPanel";
import PresetScaleTestsPanel from "./components/panels/PresetScaleTestsPanel";

const DAGDEVIREN_PAPER_RATIOS = [2, 4, 6, 8];
const DAGDEVIREN_SCALE_GROUPS = {
  small: [10, 15, 20, 25],
  medium: [50, 100, 150, 200],
  large: [250, 500, 750, 1000],
};
const DAGDEVIREN_CAPACITY_BY_SCALE = { small: 18, medium: 16, large: 16 };
const PRESET_SCALE_RUN_SCOPES = ["all", "small", "medium", "large"];

export default function App() {
  const [graph, setGraph] = useState(null);
  const [results, setResults] = useState(null);
  const [solveMeta, setSolveMeta] = useState(null);
  const [running, setRunning] = useState(false);

  const [source, setSource] = useState("Embedded 100V");
  const [uploadErr, setUploadErr] = useState("");
  const [runErr, setRunErr] = useState("");
  const [benchmarkErr, setBenchmarkErr] = useState("");
  const [datasetErr, setDatasetErr] = useState("");

  const [workspaceTab, setWorkspaceTab] = useState("overview");
  const [inspectorTab, setInspectorTab] = useState("node");
  const [latexTab, setLatexTab] = useState("full");

  const [kMode, setKMode] = useState("manual");
  const [capKInput, setCapKInput] = useState("9");
  const [optimizeGoal, setOptimizeGoal] = useState("min-feasible-k");
  const [optimizeTrials, setOptimizeTrials] = useState(14);

  const [popSize, setPopSize] = useState(40);
  const [generations, setGenerations] = useState(60);

  const [selectedMethod, setSelectedMethod] = useState("hga");
  const [hoverNode, setHoverNode] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);

  const [labelMode, setLabelMode] = useState("weight");
  const [edgeViewMode, setEdgeViewMode] = useState("cover-related");
  const [nodeScale, setNodeScale] = useState(1.2);
  const [edgeStrength, setEdgeStrength] = useState(0.9);
  const [edgeLimit, setEdgeLimit] = useState(220);

  const [benchmarkRows, setBenchmarkRows] = useState(null);
  const [benchmarkRunning, setBenchmarkRunning] = useState(false);
  const [datasetAnalysis, setDatasetAnalysis] = useState(null);
  const [datasetRunning, setDatasetRunning] = useState(false);
  const [presetScaleTests, setPresetScaleTests] = useState(null);
  const [presetScaleTestsRunning, setPresetScaleTestsRunning] = useState(false);
  const [datasetNFilter, setDatasetNFilter] = useState("");
  const [datasetMFilter, setDatasetMFilter] = useState("");
  const [datasetSFilter, setDatasetSFilter] = useState("");
  const [datasetFilterMode, setDatasetFilterMode] = useState("guided");
  const [datasetFilenameRaw, setDatasetFilenameRaw] = useState("");
  const [datasetRatioFilterInput, setDatasetRatioFilterInput] = useState(
    DAGDEVIREN_PAPER_RATIOS.join(",")
  );
  const [datasetMaxFilesInput, setDatasetMaxFilesInput] = useState("400");
  const [presetScaleTestErr, setPresetScaleTestErr] = useState("");
  const [presetScaleRunScope, setPresetScaleRunScope] = useState("all");

  const [themeMode, setThemeMode] = useState(() => {
    if (typeof window === "undefined") return "dark";
    return window.localStorage.getItem("ccvc-theme") === "light" ? "light" : "dark";
  });

  const stageRef = useRef(null);
  const fileRef = useRef(null);
  const [stageSize, setStageSize] = useState({ width: 760, height: 440 });

  const parsePositiveIntInput = (value) => {
    const parsed = Number.parseInt(String(value ?? "").trim(), 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  };

  const datasetN = parsePositiveIntInput(datasetNFilter);
  const datasetM = parsePositiveIntInput(datasetMFilter);
  const datasetS = parsePositiveIntInput(datasetSFilter);
  const datasetRatioFilter = useMemo(() => {
    const tokens = String(datasetRatioFilterInput)
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const values = [];
    for (const token of tokens) {
      const parsed = Number.parseFloat(token);
      if (Number.isFinite(parsed) && parsed > 0) values.push(Number(parsed.toFixed(6)));
    }
    return [...new Set(values)].sort((a, b) => a - b);
  }, [datasetRatioFilterInput]);
  const guidedRatioOverride = useMemo(() => {
    if (datasetFilterMode !== "guided") return null;
    if (datasetN === null || datasetM === null || datasetN <= 0) return null;
    return Number((datasetM / datasetN).toFixed(6));
  }, [datasetFilterMode, datasetN, datasetM]);
  const effectiveDatasetRatios = useMemo(() => {
    if (guidedRatioOverride !== null) return [guidedRatioOverride];
    return datasetRatioFilter.length ? datasetRatioFilter : undefined;
  }, [datasetRatioFilter, guidedRatioOverride]);
  const datasetMaxFiles = clamp(parsePositiveIntInput(datasetMaxFilesInput) || 400, 1, 400);
  const datasetFilenameContains = useMemo(() => {
    if (datasetFilterMode === "raw") {
      return String(datasetFilenameRaw || "").trim();
    }
    if (datasetN !== null && datasetM !== null && datasetS !== null) {
      return `n${datasetN}_m${datasetM}_s${datasetS}`;
    }
    if (datasetN !== null && datasetM !== null) {
      return `n${datasetN}_m${datasetM}_`;
    }
    if (datasetN !== null) {
      return `n${datasetN}_`;
    }
    if (datasetM !== null) {
      return `_m${datasetM}_`;
    }
    if (datasetS !== null) {
      return `_s${datasetS}.txt`;
    }
    return "";
  }, [datasetFilterMode, datasetFilenameRaw, datasetN, datasetM, datasetS]);

  const manualK = parseManualK(capKInput);
  const canSolve = Boolean(graph) && !running && (kMode === "auto" || manualK !== null);
  const canBenchmark = !benchmarkRunning && (kMode === "auto" || manualK !== null);
  const canDatasetAnalysis = !datasetRunning && (kMode === "auto" || manualK !== null);
  const canPresetScaleTests =
    !presetScaleTestsRunning && !datasetRunning && (kMode === "auto" || manualK !== null);
  const normalizedPresetScaleRunScope = PRESET_SCALE_RUN_SCOPES.includes(presetScaleRunScope)
    ? presetScaleRunScope
    : "all";
  const presetScopeNodeCount =
    normalizedPresetScaleRunScope === "all"
      ? 0
      : DAGDEVIREN_SCALE_GROUPS[normalizedPresetScaleRunScope]?.length || 0;
  const presetScopeRatioCount = effectiveDatasetRatios?.length || DAGDEVIREN_PAPER_RATIOS.length;
  const presetSyntheticTargetPerScale =
    normalizedPresetScaleRunScope === "all"
      ? 1
      : Math.max(1, presetScopeNodeCount, presetScopeRatioCount);

  const loadEmbedded = useCallback(() => {
    setGraph(buildEmbeddedGraph(100, DEFAULT_SEED));
    setResults(null);
    setSolveMeta(null);
    setSource("Embedded 100V");
    setUploadErr("");
    setRunErr("");
    setBenchmarkErr("");
    setDatasetErr("");
    setPresetScaleTestErr("");
    setSelectedMethod("hga");
    setSelectedNode(null);
    setHoverNode(null);
  }, []);

  useEffect(() => {
    loadEmbedded();
  }, [loadEmbedded]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("ccvc-theme", themeMode);
  }, [themeMode]);

  useEffect(() => {
    if (!stageRef.current) return undefined;

    const update = () => {
      const width = clamp(Math.floor(stageRef.current?.clientWidth || 760), 340, 980);
      const height = clamp(Math.floor(width * 0.56), 280, 560);
      setStageSize({ width, height });
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(stageRef.current);
    return () => observer.disconnect();
  }, []);

  const handleUpload = useCallback((event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const parsed = parseGraphData(String(ev.target?.result || ""));
        if (!parsed.vertices.length || !parsed.edges.length) {
          setUploadErr("Invalid file format: expected vertex rows followed by edge rows.");
          return;
        }

        setGraph(parsed);
        setResults(null);
        setSolveMeta(null);
        setSource(file.name);
        setUploadErr("");
        setRunErr("");
        setSelectedNode(null);
        setHoverNode(null);
      } catch (error) {
        setUploadErr(error instanceof Error ? error.message : "Failed to parse file.");
      }
    };

    reader.readAsText(file);
  }, []);

  const handleStepK = useCallback((delta) => {
    setCapKInput((prev) => {
      const current = parseManualK(prev) ?? 1;
      return String(Math.max(1, current + delta));
    });
  }, []);

  const handleOptimizeTrialsChange = useCallback((value) => {
    setOptimizeTrials(clamp(Number(value) || 6, 6, 36));
  }, []);

  const applyDatasetPaperPreset = useCallback(() => {
    setDatasetFilterMode("guided");
    setDatasetFilenameRaw("");
    setDatasetNFilter("");
    setDatasetMFilter("");
    setDatasetSFilter("");
    setDatasetRatioFilterInput(DAGDEVIREN_PAPER_RATIOS.join(","));
    setDatasetMaxFilesInput("400");
  }, []);

  const clearDatasetFilters = useCallback(() => {
    setDatasetFilterMode("guided");
    setDatasetFilenameRaw("");
    setDatasetNFilter("");
    setDatasetMFilter("");
    setDatasetSFilter("");
    setDatasetRatioFilterInput("");
    setDatasetMaxFilesInput("400");
  }, []);

  const solve = useCallback(async () => {
    if (!graph || running || (kMode === "manual" && manualK === null)) return;

    setRunning(true);
    setRunErr("");
    setResults(null);
    setSolveMeta(null);

    try {
      const data = await solveGraph({
        vertices: graph.vertices.map((vertex) => ({ id: vertex.id, weight: vertex.weight })),
        edges: graph.edges,
        capacityK: kMode === "manual" ? manualK : undefined,
        optimizeK: kMode === "auto",
        optimizeGoal,
        optimizeMaxTrials: optimizeTrials,
        popSize,
        generations,
        seed: DEFAULT_SEED,
        includeExact: graph.vertices.length <= 18,
      });

      const nextResults = data?.results || {};
      setResults(nextResults);
      setSolveMeta(data?.meta || null);
      setWorkspaceTab("overview");
      setSelectedNode(null);
      setHoverNode(null);

      const first = METHODS.find((method) => nextResults[method.key]);
      if (first) setSelectedMethod(first.key);
    } catch (error) {
      setRunErr(error instanceof Error ? error.message : "Failed to run algorithms.");
    } finally {
      setRunning(false);
    }
  }, [graph, running, kMode, manualK, optimizeGoal, optimizeTrials, popSize, generations]);

  const runBenchmark = useCallback(async () => {
    if (!canBenchmark || benchmarkRunning) return;

    setBenchmarkRunning(true);
    setBenchmarkErr("");
    setBenchmarkRows(null);

    try {
      const densities = [0.1, 0.16, 0.22, 0.28, 0.34];
      const rows = [];
      const benchmarkMethods = ["gccvc", "grccvc", "gwccvc", "hga", "exact"];

      for (let i = 0; i < densities.length; i++) {
        const density = densities[i];
        const graphInstance = buildDensityBenchmarkGraph({
          n: 16,
          density,
          seed: 700 + i * 37,
        });

        const data = await solveBenchmarkGraph({
          vertices: graphInstance.vertices,
          edges: graphInstance.edges,
          capacityK: kMode === "manual" ? manualK : undefined,
          optimizeK: kMode === "auto",
          optimizeGoal,
          optimizeMaxTrials: Math.max(6, Math.min(optimizeTrials, 12)),
          popSize: Math.min(popSize, 40),
          generations: Math.min(generations, 80),
          seed: DEFAULT_SEED + i,
          includeExact: true,
          methods: benchmarkMethods,
        });

        rows.push({
          id: `B${i + 1}`,
          density,
          capacityK: data?.meta?.capacityK ?? null,
          results: data?.results || {},
        });
      }

      setBenchmarkRows(rows);
    } catch (error) {
      setBenchmarkErr(error instanceof Error ? error.message : "Failed to build benchmark.");
    } finally {
      setBenchmarkRunning(false);
    }
  }, [benchmarkRunning, canBenchmark, kMode, manualK, optimizeGoal, optimizeTrials, popSize, generations]);

  const runDataset = useCallback(async () => {
    if (!canDatasetAnalysis || datasetRunning) return;
    setDatasetRunning(true);
    setDatasetErr("");
    setDatasetAnalysis(null);

    try {
      const data = await runDagdevirenAnalysis({
        maxFiles: datasetMaxFiles,
        filenameContains: datasetFilenameContains || undefined,
        ratios: effectiveDatasetRatios,
        optimizeK: kMode === "auto",
        optimizeGoal,
        optimizeMaxTrials: optimizeTrials,
        smallScales: DAGDEVIREN_SCALE_GROUPS.small,
        mediumScales: DAGDEVIREN_SCALE_GROUPS.medium,
        largeScales: DAGDEVIREN_SCALE_GROUPS.large,
        capacityByScale: DAGDEVIREN_CAPACITY_BY_SCALE,
        methods: ["gccvc", "grccvc", "gwccvc", "hga"],
        includeExact: false,
        capacityK: kMode === "manual" ? manualK || undefined : undefined,
        popSize,
        generations,
        seed: DEFAULT_SEED,
      });
      setDatasetAnalysis(data || null);
    } catch (error) {
      setDatasetErr(error instanceof Error ? error.message : "Failed to run Dagdeviren analysis.");
    } finally {
      setDatasetRunning(false);
    }
  }, [
    canDatasetAnalysis,
    datasetRunning,
    datasetMaxFiles,
    datasetFilenameContains,
    effectiveDatasetRatios,
    optimizeGoal,
    optimizeTrials,
    kMode,
    manualK,
    popSize,
    generations,
  ]);

  const runPresetScaleTests = useCallback(async () => {
    if (!canPresetScaleTests || presetScaleTestsRunning) return;
    setPresetScaleTestsRunning(true);
    setPresetScaleTestErr("");
    setPresetScaleTests(null);

    try {
      const data = await runDagdevirenPresetTests({
        maxFilesPerScale: datasetMaxFiles,
        filenameContains: datasetFilenameContains || undefined,
        ratios: effectiveDatasetRatios,
        targetScales:
          normalizedPresetScaleRunScope === "all" ? undefined : [normalizedPresetScaleRunScope],
        fillMissingWithSynthetic: false,
        syntheticTargetPerScale: presetSyntheticTargetPerScale,
        optimizeK: kMode === "auto",
        optimizeGoal,
        optimizeMaxTrials: optimizeTrials,
        methods: ["gccvc", "grccvc", "gwccvc", "hga"],
        includeExact: false,
        capacityK: kMode === "manual" ? manualK || undefined : undefined,
        popSize,
        generations,
        seed: DEFAULT_SEED,
      });
      setPresetScaleTests(data || null);
    } catch (error) {
      setPresetScaleTestErr(
        error instanceof Error ? error.message : "Failed to run Dagdeviren preset scale tests."
      );
    } finally {
      setPresetScaleTestsRunning(false);
    }
  }, [
    canPresetScaleTests,
    presetScaleTestsRunning,
    datasetMaxFiles,
    datasetFilenameContains,
    effectiveDatasetRatios,
    normalizedPresetScaleRunScope,
    presetSyntheticTargetPerScale,
    optimizeGoal,
    optimizeTrials,
    kMode,
    manualK,
    popSize,
    generations,
  ]);

  const graphStats = useMemo(() => computeGraphStats(graph), [graph]);

  const positionedGraph = useMemo(() => {
    if (!graph) return null;
    return {
      ...graph,
      vertices: layoutGraph(graph.vertices, graph.edges, stageSize.width, stageSize.height),
    };
  }, [graph, stageSize.width, stageSize.height]);

  const vertexMap = useMemo(() => {
    if (!positionedGraph) return new Map();
    return new Map(positionedGraph.vertices.map((vertex) => [vertex.id, vertex]));
  }, [positionedGraph]);

  const adjacencyMap = useMemo(() => {
    if (!positionedGraph) return new Map();
    return buildAdjacency(positionedGraph);
  }, [positionedGraph]);

  const methodRows = useMemo(() => {
    if (!results) return [];

    const base = METHODS.map((method) => {
      const payload = results[method.key];
      if (!payload) return null;

      const verification = payload.verification || {};
      return {
        ...method,
        result: payload,
        verification,
        cover: Array.isArray(payload.cover) ? payload.cover : [],
        totalWeight: Number(verification.totalWeight),
        coverSize: Number(verification.coverSize),
        time: Number(payload.time),
        valid: Boolean(verification.isValid),
      };
    }).filter(Boolean);

    const bestWeight = Math.min(
      ...base.map((row) => (Number.isFinite(row.totalWeight) ? row.totalWeight : Number.POSITIVE_INFINITY))
    );

    return base
      .map((row) => ({
        ...row,
        gapPct:
          Number.isFinite(bestWeight) && bestWeight > 0 && Number.isFinite(row.totalWeight)
            ? ((row.totalWeight - bestWeight) / bestWeight) * 100
            : 0,
      }))
      .sort((a, b) => (a.totalWeight || Infinity) - (b.totalWeight || Infinity));
  }, [results]);

  useEffect(() => {
    if (!methodRows.length) return;
    if (!methodRows.some((row) => row.key === selectedMethod)) {
      setSelectedMethod(methodRows[0].key);
    }
  }, [methodRows, selectedMethod]);

  const activeMethod = useMemo(
    () => methodRows.find((row) => row.key === selectedMethod) || null,
    [methodRows, selectedMethod]
  );

  const coverSet = useMemo(() => new Set(activeMethod?.cover || []), [activeMethod]);

  const inspectedNodeId = selectedNode ?? hoverNode;
  const inspectedInfo = useMemo(() => {
    if (!positionedGraph || inspectedNodeId === null) return null;
    const node = positionedGraph.vertices.find((vertex) => vertex.id === inspectedNodeId);
    if (!node) return null;

    return {
      id: node.id,
      weight: node.weight,
      degree: adjacencyMap.get(node.id)?.size || 0,
      inCover: coverSet.has(node.id),
    };
  }, [positionedGraph, inspectedNodeId, adjacencyMap, coverSet]);

  const displayEdges = useMemo(() => {
    if (!positionedGraph) return [];

    let edges = positionedGraph.edges;

    if (edgeViewMode === "cover-related" && activeMethod) {
      edges = edges.filter(([u, v]) => coverSet.has(u) || coverSet.has(v));
    } else if (edgeViewMode === "cover-core" && activeMethod) {
      edges = edges.filter(([u, v]) => coverSet.has(u) && coverSet.has(v));
    } else if (edgeViewMode === "hover-local") {
      if (inspectedNodeId !== null) edges = edges.filter(([u, v]) => u === inspectedNodeId || v === inspectedNodeId);
      else if (activeMethod) edges = edges.filter(([u, v]) => coverSet.has(u) || coverSet.has(v));
    } else if (edgeViewMode === "uncovered-only" && activeMethod) {
      edges = edges.filter(([u, v]) => !coverSet.has(u) && !coverSet.has(v));
    }

    if (edges.length <= edgeLimit) return edges;
    const stride = Math.ceil(edges.length / edgeLimit);
    return edges.filter((_, index) => index % stride === 0).slice(0, edgeLimit);
  }, [positionedGraph, edgeViewMode, activeMethod, coverSet, inspectedNodeId, edgeLimit]);

  const solverSummary = useMemo(() => {
    if (!methodRows.length) return null;

    const validRows = methodRows.filter((row) => row.valid);
    const bestValid = validRows.length ? validRows[0] : null;
    const fastest = [...methodRows].sort((a, b) => (a.time || Infinity) - (b.time || Infinity))[0] || null;

    return {
      bestValid,
      fastest,
      validCount: validRows.length,
      totalCount: methodRows.length,
    };
  }, [methodRows]);

  const barsData = useMemo(
    () =>
      methodRows.map((row) => ({
        name: row.label,
        weight: Number.isFinite(row.totalWeight) ? row.totalWeight : 0,
        size: Number.isFinite(row.coverSize) ? row.coverSize : 0,
        time: Number.isFinite(row.time) ? row.time : 0,
      })),
    [methodRows]
  );

  const convergenceData = useMemo(() => {
    const history = Array.isArray(results?.hga?.history) ? results.hga.history : [];
    return history
      .map((row) => ({
        gen: Number(row?.gen),
        bestWeight: Number(row?.bestWeight),
      }))
      .filter((row) => Number.isFinite(row.gen) && Number.isFinite(row.bestWeight));
  }, [results]);

  const greedyBest = useMemo(() => {
    const other = methodRows
      .filter((row) => row.key !== "hga" && Number.isFinite(row.totalWeight))
      .map((row) => row.totalWeight);
    if (!other.length) return null;
    return Math.min(...other);
  }, [methodRows]);

  const benchmarkSeries = useMemo(() => {
    if (!benchmarkRows?.length) return [];

    return benchmarkRows.map((row) => {
      const item = { instance: row.id, density: Number(row.density.toFixed(2)) };
      METHODS.forEach((method) => {
        const w = Number(row.results?.[method.key]?.verification?.totalWeight);
        if (Number.isFinite(w)) item[method.key] = w;
      });
      return item;
    });
  }, [benchmarkRows]);

  const benchmarkMethods = useMemo(() => {
    if (!benchmarkSeries.length) return [];
    const sample = benchmarkSeries[0];
    return METHODS.filter((method) => Object.prototype.hasOwnProperty.call(sample, method.key));
  }, [benchmarkSeries]);

  const activeK = solveMeta?.capacityK ?? (kMode === "manual" ? manualK ?? "-" : "-");
  const kBounds = solveMeta?.kBounds || null;

  const chartTheme = useMemo(
    () =>
      themeMode === "dark"
        ? {
            axis: "#c8d7f0",
            grid: "rgba(146, 167, 198, 0.26)",
            tooltipBg: "rgba(15, 26, 44, 0.96)",
            tooltipBorder: "rgba(146, 167, 198, 0.42)",
          }
        : {
            axis: "#2c3c5c",
            grid: "rgba(53, 75, 109, 0.2)",
            tooltipBg: "rgba(255, 255, 255, 0.96)",
            tooltipBorder: "rgba(130, 152, 188, 0.42)",
          },
    [themeMode]
  );

  const latexComparisonCode = useMemo(
    () => buildLatexComparisonCode(methodRows, graphStats, activeK),
    [methodRows, graphStats, activeK]
  );

  const latexBarsCode = useMemo(() => buildLatexBarsCode(methodRows), [methodRows]);

  const latexConvergenceCode = useMemo(
    () => buildLatexConvergenceCode(convergenceData),
    [convergenceData]
  );

  const latexByTab = useMemo(
    () => ({
      comparison: latexComparisonCode,
      bars: latexBarsCode,
      convergence: latexConvergenceCode,
      full: `${latexComparisonCode}\n\n${latexBarsCode}\n\n${latexConvergenceCode}`,
    }),
    [latexComparisonCode, latexBarsCode, latexConvergenceCode]
  );

  const solveStatus = running ? "loading" : runErr ? "error" : results ? "completed" : "idle";
  const loadingModal = useMemo(() => {
    if (presetScaleTestsRunning) {
      return {
        title: "Running Preset Scale Tests",
        description: "Analyzing dataset files, generating graph outputs, and updating charts.",
      };
    }
    if (datasetRunning) {
      return {
        title: "Analyzing Dagdeviren Dataset",
        description: "Processing graph files and preparing scale/connectivity chart data.",
      };
    }
    if (running) {
      return {
        title: "Computing Graph Solution",
        description: "Running algorithms and refreshing graph metrics and charts.",
      };
    }
    if (benchmarkRunning) {
      return {
        title: "Running Benchmark",
        description: "Evaluating benchmark instances and updating comparison charts.",
      };
    }
    return null;
  }, [presetScaleTestsRunning, datasetRunning, running, benchmarkRunning]);

  return (
    <div className={`studio theme-${themeMode}`}>
      <div className="bg-ink" aria-hidden="true" />
      <div className="bg-grid" aria-hidden="true" />
      <div className="bg-noise" aria-hidden="true" />

      <HeaderBar
        source={source}
        activeK={activeK}
        graphStats={graphStats}
        themeMode={themeMode}
        solveStatus={solveStatus}
        onToggleTheme={() => setThemeMode((prev) => (prev === "dark" ? "light" : "dark"))}
      />

      <main className="relative z-1 mx-auto mt-4 flex max-w-[1680px] flex-col gap-4 lg:flex-row">
        <div className="w-full shrink-0 lg:w-[380px] xl:w-[420px]">
          <ControlPanel
            source={source}
            fileRef={fileRef}
            onLoadEmbedded={loadEmbedded}
            onUpload={handleUpload}
            uploadErr={uploadErr}
            kMode={kMode}
            setKMode={setKMode}
            capKInput={capKInput}
            setCapKInput={setCapKInput}
            onStepK={handleStepK}
            manualK={manualK}
            optimizeGoal={optimizeGoal}
            setOptimizeGoal={setOptimizeGoal}
            optimizeTrials={optimizeTrials}
            onOptimizeTrialsChange={handleOptimizeTrialsChange}
            popSize={popSize}
            onPopSizeChange={(value) => setPopSize(clamp(Number(value), 10, 120))}
            generations={generations}
            onGenerationsChange={(value) => setGenerations(clamp(Number(value), 20, 220))}
            canSolve={canSolve}
            running={running}
            onSolve={solve}
            runErr={runErr}
            canBenchmark={canBenchmark}
            benchmarkRunning={benchmarkRunning}
            onRunBenchmark={runBenchmark}
            benchmarkErr={benchmarkErr}
            canDatasetAnalysis={canDatasetAnalysis}
            datasetRunning={datasetRunning}
            onRunDatasetAnalysis={runDataset}
            datasetErr={datasetErr}
            canPresetScaleTests={canPresetScaleTests}
            presetScaleTestsRunning={presetScaleTestsRunning}
            onRunPresetScaleTests={runPresetScaleTests}
            presetScaleTestErr={presetScaleTestErr}
            presetScaleRunScope={normalizedPresetScaleRunScope}
            onPresetScaleRunScopeChange={setPresetScaleRunScope}
            datasetNFilter={datasetNFilter}
            onDatasetNFilterChange={setDatasetNFilter}
            datasetMFilter={datasetMFilter}
            onDatasetMFilterChange={setDatasetMFilter}
            datasetSFilter={datasetSFilter}
            onDatasetSFilterChange={setDatasetSFilter}
            datasetFilterMode={datasetFilterMode}
            onDatasetFilterModeChange={setDatasetFilterMode}
            datasetFilenameRaw={datasetFilenameRaw}
            onDatasetFilenameRawChange={setDatasetFilenameRaw}
            datasetRatioFilterInput={datasetRatioFilterInput}
            onDatasetRatioFilterInputChange={setDatasetRatioFilterInput}
            datasetMaxFilesInput={datasetMaxFilesInput}
            onDatasetMaxFilesInputChange={setDatasetMaxFilesInput}
            datasetFilenameContains={datasetFilenameContains}
            onApplyDatasetPaperPreset={applyDatasetPaperPreset}
            onClearDatasetFilters={clearDatasetFilters}
            graphStats={graphStats}
            activeK={activeK}
            kBounds={kBounds}
          />
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <GraphStudio
            stageRef={stageRef}
            stageSize={stageSize}
            methodRows={methodRows}
            selectedMethod={selectedMethod}
            setSelectedMethod={setSelectedMethod}
            labelMode={labelMode}
            setLabelMode={setLabelMode}
            edgeViewMode={edgeViewMode}
            setEdgeViewMode={setEdgeViewMode}
            nodeScale={nodeScale}
            setNodeScale={setNodeScale}
            edgeStrength={edgeStrength}
            setEdgeStrength={setEdgeStrength}
            edgeLimit={edgeLimit}
            setEdgeLimit={setEdgeLimit}
            positionedGraph={positionedGraph}
            displayEdges={displayEdges}
            vertexMap={vertexMap}
            coverSet={coverSet}
            hoverNode={hoverNode}
            setHoverNode={setHoverNode}
            selectedNode={selectedNode}
            setSelectedNode={setSelectedNode}
            inspectorTab={inspectorTab}
            setInspectorTab={setInspectorTab}
            inspectedInfo={inspectedInfo}
            activeMethod={activeMethod}
          />

          <WorkspacePanel
            workspaceTab={workspaceTab}
            setWorkspaceTab={setWorkspaceTab}
            methodRows={methodRows}
            selectedMethod={selectedMethod}
            setSelectedMethod={setSelectedMethod}
            solverSummary={solverSummary}
            activeMethod={activeMethod}
            barsData={barsData}
            convergenceData={convergenceData}
            greedyBest={greedyBest}
            chartTheme={chartTheme}
            graphStats={graphStats}
            activeK={activeK}
            latexTab={latexTab}
            setLatexTab={setLatexTab}
            latexByTab={latexByTab}
            solveMeta={solveMeta}
            results={results}
            datasetAnalysis={datasetAnalysis}
            presetScaleTests={presetScaleTests}
          />
        </div>
      </main>

      <div className="relative z-1 mx-auto mt-4 max-w-[1680px]">
        <BenchmarkPanel
          benchmarkSeries={benchmarkSeries}
          benchmarkRows={benchmarkRows || []}
          benchmarkMethods={benchmarkMethods}
          benchmarkRunning={benchmarkRunning}
          chartTheme={chartTheme}
        />
      </div>

      <div className="relative z-1 mx-auto mt-4 max-w-[1680px]">
        <DatasetAnalysisPanel
          datasetAnalysis={datasetAnalysis}
          datasetRunning={datasetRunning}
          datasetErr={datasetErr}
          chartTheme={chartTheme}
        />
      </div>

      <div className="relative z-1 mx-auto mt-4 max-w-[1680px]">
        <PresetScaleTestsPanel
          presetScaleTests={presetScaleTests}
          presetRunning={presetScaleTestsRunning}
          presetErr={presetScaleTestErr}
          chartTheme={chartTheme}
        />
      </div>

      {loadingModal && (
        <div className="fixed inset-0 z-[140] flex items-center justify-center bg-[rgba(5,10,22,0.72)] backdrop-blur-[3px]">
          <div
            role="status"
            aria-live="polite"
            className="mx-4 w-full max-w-[520px] rounded-[20px] border border-[color-mix(in_srgb,var(--accent)_44%,var(--border))] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] px-6 py-5 shadow-[var(--shadow)]"
          >
            <div className="flex items-start gap-4">
              <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-[color-mix(in_srgb,var(--accent)_46%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_12%,var(--panel-strong))]">
                <Loader2 size={20} className="animate-spin text-[var(--accent)]" />
              </span>
              <div>
                <p className="m-0 text-sm font-bold text-[var(--text-dim)]">{loadingModal.title}</p>
                <p className="mt-1 text-sm text-[var(--text-muted)]">{loadingModal.description}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
