"use client";

import { memo, useMemo } from "react";
import type { DecisionRecord } from "@/hooks/useWargame";

interface RoundTimelineProps {
  currentRound: number;
  totalRounds: number;
  decisionRounds: number[];
  decisions?: DecisionRecord[];
  onScrub: (round: number) => void;
  selectedRound: number | null;
}

function RoundTimeline({
  currentRound,
  totalRounds,
  decisionRounds,
  decisions,
  onScrub,
  selectedRound,
}: RoundTimelineProps) {
  const decisionSet = new Set(decisionRounds);
  const rounds = Array.from({ length: totalRounds }, (_, i) => i + 1);

  const decisionByRound = useMemo(() => {
    const map = new Map<number, DecisionRecord>();
    if (decisions) {
      for (const d of decisions) map.set(d.round, d);
    }
    return map;
  }, [decisions]);

  return (
    <div className="flex items-center gap-0 px-3 h-full select-none overflow-x-auto">
      {rounds.map((r) => {
        const isPast = r < currentRound;
        const isCurrent = r === currentRound;
        const isSelected = r === selectedRound;
        const isDecision = decisionSet.has(r);

        return (
          <div key={r} className="flex items-center">
            {r > 1 && (
              <div
                className="h-px shrink-0"
                style={{
                  width: 16,
                  background: isPast || isCurrent
                    ? "var(--accent-cyan)"
                    : "var(--border-secondary)",
                  opacity: isPast || isCurrent ? 0.5 : 1,
                }}
              />
            )}

            <button
              onClick={() => onScrub(r)}
              className="relative flex flex-col items-center shrink-0 cursor-pointer bg-transparent border-none p-0 group"
              title={
                isDecision && decisionByRound.has(r)
                  ? `R${r}: ${decisionByRound.get(r)!.label} → ${decisionByRound.get(r)!.outcome}`
                  : `라운드 ${r}${isDecision ? " (결정)" : ""}`
              }
            >
              {isDecision && (
                <span className="absolute -top-3.5 text-[9px] leading-none text-amber-400">
                  ⚡
                </span>
              )}

              <div
                className="rounded-full transition-all duration-200 group-hover:scale-125"
                style={{
                  width: isCurrent ? 12 : isSelected ? 10 : 7,
                  height: isCurrent ? 12 : isSelected ? 10 : 7,
                  background: isCurrent
                    ? "var(--accent-cyan)"
                    : isSelected
                      ? "var(--accent-cyan)"
                      : isPast
                        ? "var(--text-muted)"
                        : "var(--border-secondary)",
                  boxShadow: isCurrent
                    ? "0 0 8px rgba(34,211,238,0.5)"
                    : isSelected
                      ? "0 0 6px rgba(34,211,238,0.3)"
                      : "none",
                  animation: isCurrent ? "pulse-marker 2s ease-in-out infinite" : "none",
                }}
              />

              <span
                className="mt-0.5 text-[8px] leading-none font-medium tabular-nums"
                style={{
                  color: isCurrent || isSelected
                    ? "var(--accent-cyan)"
                    : isPast
                      ? "var(--text-muted)"
                      : "var(--border-secondary)",
                }}
              >
                {r}
              </span>
            </button>
          </div>
        );
      })}

      <style>{`
        @keyframes pulse-marker {
          0%, 100% { box-shadow: 0 0 4px rgba(34,211,238,0.3); }
          50% { box-shadow: 0 0 12px rgba(34,211,238,0.6); }
        }
      `}</style>
    </div>
  );
}

export default memo(RoundTimeline);
