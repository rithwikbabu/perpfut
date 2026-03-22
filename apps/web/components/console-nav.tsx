"use client";

import Link from "next/link";


type ConsoleNavKey = "overview" | "backtests";

const NAV_ITEMS: Array<{ key: ConsoleNavKey; label: string; href: string }> = [
  { key: "overview", label: "Overview", href: "/" },
  { key: "backtests", label: "Backtests", href: "/backtests" },
];

export function ConsoleNav({ active }: { active: ConsoleNavKey }) {
  return (
    <div className="mt-8 space-y-2">
      {NAV_ITEMS.map((item, index) => (
        <Link
          key={item.key}
          href={item.href}
          className={`flex items-center justify-between border px-3 py-3 text-sm tracking-wide transition ${
            item.key === active
              ? "border-[var(--border-strong)] bg-[rgba(84,191,255,0.08)]"
              : "border-transparent bg-transparent text-[var(--muted)] hover:border-[var(--border)] hover:text-[var(--text)]"
          }`}
        >
          <span>{item.label}</span>
          <span className="mono text-[11px]">{String(index + 1).padStart(2, "0")}</span>
        </Link>
      ))}
    </div>
  );
}
