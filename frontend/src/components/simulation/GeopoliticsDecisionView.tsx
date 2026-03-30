"use client";

import { useEffect, useState } from "react";
import { Shield, Eye, Play, Check } from "lucide-react";
import type { DecisionPoint, DecisionOption } from "@/types/simulation";
import { getDecisionPoints, resolveDecisionPoint, continueSimulation } from "@/lib/gatewayApi";

interface Props {
  scenarioId: string;
  onResolved: () => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  military: "#ef4444",
  economic: "#a78bfa",
  diplomatic: "#22d3ee",
  treaty: "#34d399",
  intelligence: "#f59e0b",
  nothing: "#6b7280",
};

const DIRECTION_META: Record<string, { emoji: string; color: string; appliesTo: string }> = {
  escalate:   { emoji: "🔴", color: "#ef4444", appliesTo: "적대국" },
  diplomatic: { emoji: "🟡", color: "#f59e0b", appliesTo: "전체" },
  economic:   { emoji: "🔵", color: "#a78bfa", appliesTo: "적대국" },
  maintain:   { emoji: "⚪", color: "#6b7280", appliesTo: "동맹국" },
};

const STATE_LABELS: Record<string, { label: string; color: string }> = {
  threat_perception:  { label: "위협 인식", color: "#ef4444" },
  domestic_pressure:  { label: "국내 압력", color: "#f59e0b" },
  resource_level:     { label: "자원 수준", color: "#34d399" },
};

const DELTA_COLORS: Record<string, string> = {
  threat: "#ef4444",
  domestic: "#f59e0b",
  resource: "#34d399",
  tension: "#ef4444",
  stability: "#22d3ee",
};

function catColor(opt: DecisionOption): string {
  const cat = String(opt.data?.category ?? opt.data?.action_category ?? "nothing").toLowerCase();
  return CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.nothing;
}

function safePct(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : 0;
}

export default function GeopoliticsDecisionView({ scenarioId, onResolved }: Props) {
  const [dp, setDp] = useState<DecisionPoint | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);

  useEffect(() => {
    setLoading(true);
    getDecisionPoints(scenarioId, "pending")
      .then((res) => {
        const match = res.decision_points.find(
          (d) => d.type === "geopolitics_actor_response" || d.type === "geopolitics_direction",
        );
        setDp(match ?? null);
        if (match?.recommended) setSelectedId(match.recommended);
      })
      .catch(() => setDp(null))
      .finally(() => setLoading(false));
  }, [scenarioId]);

  const handleSubmit = async () => {
    if (!dp || !selectedId) return;
    setResolving(true);
    try {
      await resolveDecisionPoint(scenarioId, dp.id, { selected_option_id: selectedId });
      await continueSimulation(scenarioId);
      onResolved();
    } catch {
    } finally {
      setResolving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ ...wrapStyle, alignItems: "center", justifyContent: "center", minHeight: 120, display: "flex" }}>
        <Spinner />
        <span style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: 8 }}>
          지정학 결정 지점 로딩 중...
        </span>
      </div>
    );
  }

  if (!dp) {
    return (
      <div style={{ ...wrapStyle, textAlign: "center", padding: 24 }}>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          대기 중인 지정학 결정 지점이 없습니다
        </span>
      </div>
    );
  }

  const isActorRole = dp.type === "geopolitics_actor_response";

  return (
    <div style={wrapStyle}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {isActorRole
          ? <Shield size={14} color="#ef4444" />
          : <Eye size={14} color="var(--accent-cyan)" />}
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
          {isActorRole ? "🎖 지정학 이벤트 대응" : "🌐 시나리오 방향 결정"}
        </span>
        <span style={{
          fontSize: 10, padding: "2px 6px", borderRadius: 999,
          background: "rgba(239, 68, 68, 0.12)", color: "#ef4444",
          fontWeight: 600, marginLeft: "auto",
        }}>
          개입 필요
        </span>
      </div>

      {isActorRole
        ? <ActorRoleBody dp={dp} selectedId={selectedId} onSelect={setSelectedId} />
        : <GameMasterBody dp={dp} selectedId={selectedId} onSelect={setSelectedId} />}

      <button
        disabled={!selectedId || resolving}
        onClick={handleSubmit}
        style={{
          width: "100%", padding: "8px 12px",
          background: !selectedId || resolving ? "var(--border-secondary)" : "var(--accent-cyan)",
          border: "none", borderRadius: 4,
          color: !selectedId || resolving ? "var(--text-muted)" : "var(--bg-primary)",
          fontSize: 12, fontWeight: 700,
          cursor: !selectedId || resolving ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
        }}
      >
        {resolving
          ? <><Spinner /> 처리 중...</>
          : <><Play size={12} /> 선택 적용</>}
      </button>

      <style>{`@keyframes gdv-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function ActorRoleBody({ dp, selectedId, onSelect }: {
  dp: DecisionPoint; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const sample = dp.options[0]?.data ?? {};
  const trigger = sample.trigger_event as Record<string, unknown> | undefined;
  const playerState = sample.player_state as Record<string, unknown> | undefined;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {trigger && <TriggerEventCard event={trigger} />}
      {playerState && <PlayerStateBars state={playerState} />}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {dp.options.map((opt) => (
          <ActorOptionCard
            key={opt.id}
            option={opt}
            isSelected={selectedId === opt.id}
            isRecommended={opt.id === dp.recommended}
            onSelect={() => onSelect(opt.id)}
          />
        ))}
      </div>
    </div>
  );
}

function TriggerEventCard({ event }: { event: Record<string, unknown> }) {
  const source = String(event.source_actor ?? "Unknown");
  const action = String(event.action_type ?? "unknown").replace(/_/g, " ");
  const targets = Array.isArray(event.target_actors)
    ? (event.target_actors as string[]).join(", ")
    : String(event.target_actors ?? "—");
  const magnitude = safePct(event.magnitude);

  return (
    <div style={{
      padding: 10, background: "var(--bg-primary)",
      border: "1px solid var(--border-secondary)", borderRadius: 4,
      display: "flex", flexDirection: "column", gap: 6,
    }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        트리거 이벤트
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <InfoTag label="출발" value={source} color="#ef4444" />
        <InfoTag label="행동" value={action} color="#f59e0b" />
        <InfoTag label="대상" value={targets} color="#22d3ee" />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 10, color: "var(--text-muted)", width: 40 }}>규모</span>
        <div style={{ flex: 1, height: 4, borderRadius: 999, background: "var(--border-secondary)", overflow: "hidden" }}>
          <div style={{ width: `${Math.round(magnitude * 100)}%`, height: "100%", background: "#ef4444", transition: "width 0.3s" }} />
        </div>
        <span style={{ fontSize: 10, fontFamily: "monospace", color: "#ef4444", fontWeight: 600 }}>
          {(magnitude * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

function PlayerStateBars({ state }: { state: Record<string, unknown> }) {
  const entries = Object.entries(STATE_LABELS).filter(([k]) => state[k] != null);
  if (entries.length === 0) return null;

  return (
    <div style={{
      padding: 10, background: "var(--bg-primary)",
      border: "1px solid var(--border-secondary)", borderRadius: 4,
      display: "flex", flexDirection: "column", gap: 6,
    }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        당신의 국가
      </div>
      {entries.map(([key, meta]) => {
        const val = safePct(state[key]);
        return (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 10, color: "var(--text-muted)", width: 52, flexShrink: 0 }}>{meta.label}</span>
            <div style={{ flex: 1, height: 4, borderRadius: 999, background: "var(--border-secondary)", overflow: "hidden" }}>
              <div style={{ width: `${Math.round(val * 100)}%`, height: "100%", background: meta.color, transition: "width 0.3s" }} />
            </div>
            <span style={{ fontSize: 10, fontFamily: "monospace", color: meta.color, fontWeight: 600, width: 28, textAlign: "right" }}>
              {(val * 100).toFixed(0)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

function ActorOptionCard({ option, isSelected, isRecommended, onSelect }: {
  option: DecisionOption; isSelected: boolean; isRecommended: boolean; onSelect: () => void;
}) {
  const borderColor = catColor(option);
  const engineRec = Boolean(option.data?.engine_recommended);

  const deltas: { key: string; val: number }[] = [];
  for (const [k, v] of Object.entries(option.data)) {
    if (k.startsWith("delta_") && typeof v === "number") {
      deltas.push({ key: k.replace("delta_", ""), val: v });
    }
  }

  return (
    <div
      onClick={onSelect}
      style={{
        background: "var(--bg-primary)",
        border: isSelected ? `1.5px solid ${borderColor}` : "1px solid var(--border-secondary)",
        borderLeft: `3px solid ${borderColor}`,
        borderRadius: 4, padding: "8px 10px", cursor: "pointer",
        display: "flex", flexDirection: "column", gap: 4,
        transition: "border-color 0.15s, box-shadow 0.15s",
        boxShadow: isSelected ? `0 0 8px ${borderColor}33` : "none",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{
          width: 16, height: 16, borderRadius: "50%",
          border: isSelected ? `2px solid ${borderColor}` : "1.5px solid var(--border-secondary)",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          background: isSelected ? `${borderColor}22` : "transparent",
        }}>
          {isSelected && <Check size={9} color={borderColor} />}
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", flex: 1 }}>
          {option.label}
        </span>
        {engineRec && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 999,
            background: "rgba(34, 211, 238, 0.12)", color: "var(--accent-cyan)",
          }}>
            엔진 추천
          </span>
        )}
        {isRecommended && !engineRec && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 999,
            background: "rgba(34, 211, 238, 0.12)", color: "var(--accent-cyan)",
          }}>
            AI 추천
          </span>
        )}
      </div>

      {option.description && (
        <span style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4, paddingLeft: 22 }}>
          {option.description}
        </span>
      )}

      {deltas.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, paddingLeft: 22, marginTop: 2 }}>
          {deltas.map((d) => (
            <DeltaTag key={d.key} label={d.key} value={d.val} />
          ))}
        </div>
      )}
    </div>
  );
}

function GameMasterBody({ dp, selectedId, onSelect }: {
  dp: DecisionPoint; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const roundEvents = (dp.options[0]?.data?.round_events ?? []) as Array<Record<string, unknown>>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {roundEvents.length > 0 && (
        <div style={{
          padding: 10, background: "var(--bg-primary)",
          border: "1px solid var(--border-secondary)", borderRadius: 4,
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            라운드 요약
          </div>
          {roundEvents.slice(0, 5).map((ev, i) => (
            <div key={i} style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4, display: "flex", gap: 4 }}>
              <span style={{ color: "#f59e0b" }}>•</span>
              <span>{String(ev.content ?? ev.action_type ?? "event")}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {dp.options.map((opt) => {
          const dirKey = String(opt.data?.direction ?? opt.id).toLowerCase();
          const meta = DIRECTION_META[dirKey] ?? { emoji: "⚪", color: "#6b7280", appliesTo: "전체" };
          const appliesTo = String(opt.data?.applies_to ?? meta.appliesTo);
          const isSelected = selectedId === opt.id;

          const deltas: { key: string; val: number }[] = [];
          for (const [k, v] of Object.entries(opt.data)) {
            if (k.startsWith("delta_") && typeof v === "number") {
              deltas.push({ key: k.replace("delta_", ""), val: v });
            }
          }

          return (
            <div
              key={opt.id}
              onClick={() => onSelect(opt.id)}
              style={{
                background: "var(--bg-primary)",
                border: isSelected ? `1.5px solid ${meta.color}` : "1px solid var(--border-secondary)",
                borderRadius: 4, padding: 10, cursor: "pointer",
                display: "flex", flexDirection: "column", gap: 6,
                transition: "border-color 0.15s, box-shadow 0.15s",
                boxShadow: isSelected ? `0 0 8px ${meta.color}33` : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 16 }}>{meta.emoji}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
                  {opt.label}
                </span>
                {isSelected && <Check size={10} color={meta.color} style={{ marginLeft: "auto" }} />}
              </div>
              {opt.description && (
                <span style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.4 }}>
                  {opt.description}
                </span>
              )}
              {deltas.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                  {deltas.map((d) => (
                    <DeltaTag key={d.key} label={d.key} value={d.val} />
                  ))}
                </div>
              )}
              <span style={{
                fontSize: 9, fontWeight: 600, padding: "1px 5px", borderRadius: 999,
                background: `${meta.color}18`, color: meta.color, alignSelf: "flex-start",
              }}>
                {appliesTo}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function InfoTag({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <span style={{
      fontSize: 10, padding: "2px 6px", borderRadius: 3,
      background: `${color}14`, color, fontWeight: 600,
      display: "inline-flex", gap: 3,
    }}>
      <span style={{ opacity: 0.6 }}>{label}</span> {value}
    </span>
  );
}

function DeltaTag({ label, value }: { label: string; value: number }) {
  const positive = value >= 0;
  const color = DELTA_COLORS[label] ?? (positive ? "#ef4444" : "#34d399");
  return (
    <span style={{
      fontSize: 9, padding: "1px 4px", borderRadius: 2,
      background: `${color}14`, color, fontWeight: 600, fontFamily: "monospace",
    }}>
      {positive ? "+" : ""}{value.toFixed(2)} {label}
    </span>
  );
}

function Spinner() {
  return (
    <div style={{
      width: 12, height: 12,
      border: "2px solid var(--border-secondary)",
      borderTopColor: "var(--accent-cyan)",
      borderRadius: "50%",
      animation: "gdv-spin 0.6s linear infinite",
    }} />
  );
}

const wrapStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 14,
  background: "var(--bg-tertiary)",
  borderRadius: 6,
  padding: 14,
  border: "1px solid var(--border-secondary)",
};
