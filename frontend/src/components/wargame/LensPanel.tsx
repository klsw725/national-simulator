"use client";

import type { WargameLens } from "@/types/simulation";

interface Props {
  activeLens: WargameLens;
  onLensChange: (lens: WargameLens) => void;
}

const LENSES: { key: WargameLens; icon: string; label: string }[] = [
  { key: "info_warfare", icon: "📰", label: "정보전" },
  { key: "diplomacy", icon: "🤝", label: "외교" },
  { key: "military", icon: "🛡", label: "군사" },
  { key: "economy", icon: "📊", label: "경제" },
  { key: "relations", icon: "🔗", label: "관계" },
  { key: "whatif", icon: "⑂", label: "What-If" },
];

export default function LensPanel({ activeLens, onLensChange }: Props) {
  return (
    <div className="flex flex-col items-center gap-1 py-2 w-[56px] shrink-0 border-r border-[var(--border-secondary)] bg-[var(--bg-secondary)]">
      {LENSES.map((lens) => {
        const isActive = activeLens === lens.key;

        return (
          <button
            key={lens.key}
            onClick={() => onLensChange(lens.key)}
            title={lens.label}
            className="flex flex-col items-center justify-center gap-0.5 w-11 h-11 rounded-md border-none cursor-pointer transition-all duration-150"
            style={{
              background: isActive ? "rgba(34, 211, 238, 0.12)" : "transparent",
              boxShadow: isActive ? "inset 0 0 0 1px var(--accent-cyan)" : "none",
            }}
          >
            <span className="text-base leading-none">{lens.icon}</span>
            <span
              className="text-[8px] font-semibold leading-none"
              style={{ color: isActive ? "var(--accent-cyan)" : "var(--text-muted)" }}
            >
              {lens.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
