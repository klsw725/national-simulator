"use client";

import type { WargamePhase, WargameState } from "@/types/simulation";

interface Props {
  state: WargameState;
  isMockMode: boolean;
}

const PHASES: { key: WargamePhase; label: string }[] = [
  { key: "simulation", label: "시뮬레이션" },
  { key: "briefing", label: "브리핑" },
  { key: "decision", label: "결정" },
  { key: "confirmation", label: "확정" },
];

const PHASE_COLORS: Record<WargamePhase, string> = {
  simulation: "var(--accent-cyan)",
  briefing: "var(--text-muted)",
  decision: "#f59e0b",
  confirmation: "var(--text-muted)",
};

function getRoleBadge(state: WargameState): { emoji: string; label: string } {
  if (state.role === "game_master") {
    return { emoji: "🎮", label: "GAME MASTER" };
  }
  const actor = state.actorId ? state.actorStates[state.actorId] : null;
  const name = actor?.name ?? state.actorId ?? "—";
  return { emoji: "🏛", label: `${name} (ACTOR)` };
}

export default function PhaseBar({ state, isMockMode }: Props) {
  const activeColor = PHASE_COLORS[state.phase];
  const role = getRoleBadge(state);
  const tensionPct = Math.round(state.tension * 100);

  return (
    <div className="flex items-center gap-4 px-4 h-12 shrink-0 border-b border-[var(--border-secondary)] bg-[var(--bg-secondary)]">
      <div className="flex items-center gap-1.5">
        {PHASES.map((p, idx) => {
          const isCurrent = state.phase === p.key;
          const phaseIdx = PHASES.findIndex((ph) => ph.key === state.phase);
          const isDone = idx < phaseIdx;
          const color = isCurrent ? activeColor : isDone ? "var(--accent-cyan)" : "var(--border-secondary)";

          return (
            <div key={p.key} className="flex items-center gap-1.5">
              {idx > 0 && (
                <div
                  className="w-4 h-px"
                  style={{ background: isDone ? "var(--accent-cyan)" : "var(--border-secondary)" }}
                />
              )}
              <div className="flex items-center gap-1">
                <span
                  className="block rounded-full transition-all duration-200"
                  style={{
                    width: isCurrent ? 10 : 7,
                    height: isCurrent ? 10 : 7,
                    background: isCurrent || isDone ? color : "transparent",
                    border: `2px solid ${color}`,
                    boxShadow: isCurrent ? `0 0 6px ${color}` : "none",
                  }}
                />
                <span
                  className="text-[10px] font-semibold tracking-wide whitespace-nowrap"
                  style={{ color: isCurrent ? activeColor : isDone ? "var(--text-muted)" : "var(--border-secondary)" }}
                >
                  {p.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="ml-auto flex items-center gap-4">
        <span className="text-[11px] font-bold tracking-wider text-[var(--text-primary)] font-mono">
          R{state.round}/{state.totalRounds}
        </span>

        <span
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
          style={{
            background: state.role === "game_master" ? "rgba(168,85,247,0.15)" : "rgba(34,211,238,0.12)",
            color: state.role === "game_master" ? "#a855f7" : "var(--accent-cyan)",
          }}
        >
          {role.emoji} {role.label}
        </span>

        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-widest">
            긴장
          </span>
          <div className="w-16 h-1.5 rounded-full bg-[var(--border-secondary)] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${tensionPct}%`,
                background: state.tension > 0.7
                  ? "var(--accent-red)"
                  : state.tension > 0.4
                    ? "#f59e0b"
                    : "var(--accent-cyan)",
              }}
            />
          </div>
          <span
            className="text-[10px] font-mono font-bold w-7 text-right"
            style={{
              color: state.tension > 0.7
                ? "var(--accent-red)"
                : state.tension > 0.4
                  ? "#f59e0b"
                  : "var(--accent-cyan)",
            }}
          >
            {state.tension.toFixed(1)}
          </span>
        </div>

        {isMockMode && (
          <span className="text-[9px] font-bold px-1.5 py-px rounded bg-[rgba(245,158,11,0.15)] text-[#f59e0b]">
            MOCK
          </span>
        )}
      </div>
    </div>
  );
}
