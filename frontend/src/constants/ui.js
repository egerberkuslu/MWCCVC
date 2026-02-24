import {
  Activity,
  BarChart3,
  Code2,
  FileCode2,
  Gauge,
  Sparkles,
  TrendingUp,
} from "lucide-react";

export const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";
export const DEFAULT_SEED = 42;

export const METHODS = [
  { key: "hga", label: "HGA-CCVC", color: "var(--method-hga)", mark: "●" },
  { key: "gccvc", label: "GCCVC", color: "var(--method-gccvc)", mark: "▲" },
  { key: "grccvc", label: "GRCCVC", color: "var(--method-grccvc)", mark: "◆" },
  { key: "gwccvc", label: "GWCCVC", color: "var(--method-gwccvc)", mark: "■" },
  { key: "exact", label: "Exact B&B", color: "var(--method-exact)", mark: "★" },
];

export const WORKSPACE_TABS = [
  { value: "overview", label: "Overview", icon: Activity },
  { value: "insights", label: "Insights", icon: Gauge },
  { value: "bars", label: "Bars", icon: BarChart3 },
  { value: "convergence", label: "Convergence", icon: TrendingUp },
  { value: "paper-figure", label: "Paper Figure", icon: Sparkles },
  { value: "latex", label: "LaTeX Lab", icon: FileCode2 },
  { value: "raw", label: "Raw Data", icon: Code2 },
];

export const INSPECTOR_TABS = [
  { value: "node", label: "Node" },
  { value: "solution", label: "Solution" },
  { value: "validity", label: "Validity" },
];

export const MODEL_EQUATIONS = [
  { label: "Objective", tex: "\\min \\sum_{v \\in S} w(v)" },
  { label: "Density", tex: "\\rho = \\frac{2|E|}{|V|(|V|-1)}" },
  { label: "Capacity Utilization", tex: "\\text{CapUtil} = \\frac{|E|}{|S| \\cdot K}" },
  { label: "Connectivity", tex: "G[S] \\text{ is connected}" },
  { label: "Cover Constraint", tex: "\\forall (u,v) \\in E: u \\in S \\lor v \\in S" },
  {
    label: "Capacity Constraint (Exact)",
    tex: "\\exists\\,\\phi:E\\to S,\\ \\phi(u,v)\\in\\{u,v\\}\\cap S,\\ \\forall v\\in S:\\ |\\phi^{-1}(v)|\\le K",
  },
];

export const TABLE_HEADERS_TEX = {
  weight: "w(S)",
  coverSize: "|S|",
  gap: "\\Delta\\%",
  density: "\\rho",
};
