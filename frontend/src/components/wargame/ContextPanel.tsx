"use client";

import type { ActorState, WargamePhase } from "@/types/simulation";

interface Props {
  actorStates: Record<string, ActorState>;
  phase: WargamePhase;
  playerActorId: string | null;
}

const STATE_BARS: { key: keyof ActorState; label: string; color: string }[] = [
  { key: "threat_perception", label: "위협", color: "var(--accent-red)" },
  { key: "domestic_pressure", label: "압력", color: "#f59e0b" },
  { key: "resource_level", label: "자원", color: "#34d399" },
];

function safePct(v: number): number {
  return Math.max(0, Math.min(100, Math.round(v * 100)));
}

function ActorCard({ actor, isPlayer }: { actor: ActorState; isPlayer: boolean }) {
  return (
    <div
      className="flex flex-col gap-1.5 p-2.5 rounded border bg-[var(--bg-primary)]"
      style={{
        borderColor: isPlayer ? "var(--accent-cyan)" : "var(--border-secondary)",
        borderLeftWidth: isPlayer ? 3 : 1,
      }}
    >
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold text-[var(--text-primary)]">
          {actor.name}
        </span>
        {isPlayer && (
          <span className="text-[9px] font-bold px-1.5 py-px rounded-full bg-[rgba(34,211,238,0.12)] text-[var(--accent-cyan)]">
            YOU
          </span>
        )}
      </div>

      {STATE_BARS.map((bar) => {
        const val = actor[bar.key];
        if (typeof val !== "number") return null;
        const pct = safePct(val);

        return (
          <div key={bar.key} className="flex items-center gap-1.5">
            <span className="text-[9px] text-[var(--text-muted)] w-6 shrink-0">
              {bar.label}
            </span>
            <div className="flex-1 h-1 rounded-full bg-[var(--border-secondary)] overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ width: `${pct}%`, background: bar.color }}
              />
            </div>
            <span
              className="text-[9px] font-mono font-bold w-7 text-right"
              style={{ color: bar.color }}
            >
              {pct}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function ContextPanel({ actorStates, phase, playerActorId }: Props) {
  const actors = Object.values(actorStates);
  const sortedActors = [...actors].sort((a, b) => {
    if (a.actor_id === playerActorId) return -1;
    if (b.actor_id === playerActorId) return 1;
    return a.name.localeCompare(b.name);
  });

  const phaseLabel: Record<WargamePhase, string> = {
    simulation: "시뮬레이션 진행 중",
    briefing: "브리핑 대기",
    decision: "결정 필요",
    confirmation: "결정 반영 중",
  };

  return (
    <div className="flex flex-col w-[320px] shrink-0 border-l border-[var(--border-secondary)] bg-[var(--bg-secondary)] overflow-hidden">
      <div className="px-3 py-2.5 border-b border-[var(--border-secondary)] flex items-center justify-between">
        <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest">
          상황판
        </span>
        <span
          className="text-[9px] font-semibold px-1.5 py-px rounded-full"
          style={{
            background: phase === "decision"
              ? "rgba(245,158,11,0.15)"
              : phase === "simulation"
                ? "rgba(34,211,238,0.12)"
                : "rgba(107,114,128,0.15)",
            color: phase === "decision"
              ? "#f59e0b"
              : phase === "simulation"
                ? "var(--accent-cyan)"
                : "var(--text-muted)",
          }}
        >
          {phaseLabel[phase]}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-2.5 flex flex-col gap-2">
        <div className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-0.5">
          행위자 상태 ({actors.length})
        </div>

        {sortedActors.map((actor) => (
          <ActorCard
            key={actor.actor_id}
            actor={actor}
            isPlayer={actor.actor_id === playerActorId}
          />
        ))}

        {actors.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-[var(--text-muted)] text-xs">
            행위자 데이터 없음
          </div>
        )}
      </div>
    </div>
  );
}
