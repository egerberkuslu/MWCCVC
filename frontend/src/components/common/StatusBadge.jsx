import React from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import clsx from "clsx";

export default function StatusBadge({ ok, label }) {
  return (
    <span
      className={clsx(
        "inline-flex w-fit items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-bold",
        ok
          ? "border-[color-mix(in_srgb,var(--success)_54%,transparent)] bg-[color-mix(in_srgb,var(--success)_14%,transparent)] text-[var(--success)]"
          : "border-[color-mix(in_srgb,var(--danger)_54%,transparent)] bg-[color-mix(in_srgb,var(--danger)_14%,transparent)] text-[var(--danger)]"
      )}
    >
      {ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />} {label}
    </span>
  );
}
