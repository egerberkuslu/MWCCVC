import React from "react";
import { Activity, Moon, Network, ScanLine, SunMedium } from "lucide-react";
import clsx from "clsx";

export default function HeaderBar({
  source,
  activeK,
  graphStats,
  themeMode,
  onToggleTheme,
  solveStatus,
}) {
  return (
    <header className="reveal delay-1 relative z-1 mx-auto max-w-[1680px] rounded-[30px] border border-[var(--border-strong)] bg-[linear-gradient(152deg,var(--panel-soft),var(--panel))] px-6 py-6 shadow-[var(--shadow)] backdrop-blur-[22px] backdrop-saturate-[142%] md:px-8 md:py-7">
      <p className="m-0 text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
        Capacitated Connected Vertex Cover
      </p>
      <h1 className="mt-2 text-[clamp(1.85rem,4.6vw,3.5rem)] font-[760] leading-[0.93] tracking-tight">
        CCVC Analysis Studio
        <span className="mt-2 block text-[clamp(0.78rem,1.1vw,1rem)] font-bold uppercase tracking-[0.11em] text-[var(--accent)]">
          Apple-style research interface for connected cover optimization
        </span>
      </h1>

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <Pill>
          <ScanLine size={15} />
          Source: <strong className="text-[var(--text)]">{source}</strong>
        </Pill>
        <Pill>
          <Activity size={15} />
          Active K: <strong className="text-[var(--text)]">{activeK}</strong>
        </Pill>
        <Pill>
          <Network size={15} />
          Graph: <strong className="text-[var(--text)]">{graphStats ? `${graphStats.n}V / ${graphStats.m}E` : "-"}</strong>
        </Pill>
        <Pill
          className={clsx(
            solveStatus === "loading" && "border-[color-mix(in_srgb,var(--accent)_54%,var(--border))] text-[var(--accent)]",
            solveStatus === "error" && "border-[color-mix(in_srgb,var(--danger)_52%,var(--border))] text-[var(--danger)]",
            solveStatus === "completed" && "border-[color-mix(in_srgb,var(--success)_52%,var(--border))] text-[var(--success)]"
          )}
        >
          Status: <strong className="capitalize">{solveStatus}</strong>
        </Pill>

        <button
          type="button"
          onClick={onToggleTheme}
          className="inline-flex min-h-[44px] cursor-pointer items-center gap-2 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] px-4 py-2.5 text-sm font-semibold text-[var(--text-dim)] transition-all duration-150 hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--accent)_54%,var(--border))]"
        >
          {themeMode === "dark" ? <SunMedium size={16} /> : <Moon size={16} />}
          {themeMode === "dark" ? "Daylight" : "Midnight"}
        </button>
      </div>
    </header>
  );
}

function Pill({ children, className = "" }) {
  return (
    <div
      className={clsx(
        "inline-flex min-h-[44px] items-center gap-2 rounded-full border border-[var(--border)] bg-[color-mix(in_srgb,var(--panel-strong)_94%,transparent)] px-4 py-2.5 text-sm font-semibold text-[var(--text-dim)]",
        className
      )}
    >
      {children}
    </div>
  );
}
