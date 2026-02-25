import { formatMs } from "./format";

export function escapeLatex(text) {
  return String(text)
    .replace(/\\/g, "\\textbackslash{}")
    .replace(/_/g, "\\_")
    .replace(/%/g, "\\%")
    .replace(/&/g, "\\&")
    .replace(/#/g, "\\#")
    .replace(/\$/g, "\\$")
    .replace(/{/g, "\\{")
    .replace(/}/g, "\\}");
}

export function buildLatexComparisonCode(methodRows, graphStats, activeK) {
  if (!methodRows.length || !graphStats) return "% Run algorithms to generate comparison table.";

  const rows = methodRows
    .map(
      (row) =>
        `${escapeLatex(row.label)} & ${Number.isFinite(row.totalWeight) ? row.totalWeight.toFixed(3) : "-"} & ${
          row.coverSize
        } & ${row.valid ? "\\checkmark" : "$\\times$"} & ${formatMs(row.time)} \\\\`
    )
    .join("\n");

  return `\\begin{table}[htbp]
\\centering
\\caption{CCVC algorithm comparison ($|V|=${graphStats.n}$, $|E|=${graphStats.m}$, $K=${activeK}$)}
\\begin{tabular}{lrrrr}
\\toprule
Method & $w(S)$ & $|S|$ & Valid & Time \\\\
\\midrule
${rows}
\\bottomrule
\\end{tabular}
\\end{table}`;
}

export function buildLatexBarsCode(methodRows) {
  if (!methodRows.length) return "% Run algorithms to generate bar chart code.";

  const labels = methodRows.map((row) => escapeLatex(row.label)).join(",");
  const coords = methodRows
    .map((row) => `(${escapeLatex(row.label)}, ${Number.isFinite(row.totalWeight) ? row.totalWeight.toFixed(3) : 0})`)
    .join(" ");

  return `\\begin{figure}[htbp]
\\centering
\\begin{tikzpicture}
\\begin{axis}[
  ybar,
  symbolic x coords={${labels}},
  xtick=data,
  xlabel={Method},
  ylabel={Total Weight}
]
\\addplot coordinates {${coords}};
\\end{axis}
\\end{tikzpicture}
\\caption{CCVC objective comparison}
\\end{figure}`;
}

export function buildLatexConvergenceCode(convergenceData) {
  if (!convergenceData.length) return "% Run HGA-family methods to generate convergence code.";

  const coords = convergenceData.map((row) => `(${row.gen}, ${row.bestWeight.toFixed(6)})`).join(" ");

  return `\\begin{figure}[htbp]
\\centering
\\begin{tikzpicture}
\\begin{axis}[
  xlabel={Generation},
  ylabel={Best Weight},
  grid=major
]
\\addplot[smooth, thick] coordinates {${coords}};
\\end{axis}
\\end{tikzpicture}
\\caption{Metaheuristic convergence trend}
\\end{figure}`;
}
