"use client";

import { useState } from "react";
import type { DecisionPoint, DecisionOption } from "@/types/simulation";

interface DecisionCardProps {
  decisionPoint: DecisionPoint;
  round: number;
  onConfirm: (selectedOptionId: string) => void;
  onWhatIf: () => void;
}

const CATEGORY_META: Record<string, { emoji: string; borderCls: string }> = {
  military: { emoji: "🔴", borderCls: "border-l-red-500" },
  escalate: { emoji: "🔴", borderCls: "border-l-red-500" },
  diplomatic: { emoji: "🟡", borderCls: "border-l-yellow-500" },
  economic: { emoji: "🟢", borderCls: "border-l-emerald-500" },
  maintain: { emoji: "⚪", borderCls: "border-l-gray-400" },
  nothing: { emoji: "⚪", borderCls: "border-l-gray-400" },
};

const DELTA_LABELS: Record<string, string> = {
  tension: "긴장도",
  threat: "위협 인식",
  threat_perception: "위협 인식",
  domestic: "국내 압력",
  domestic_pressure: "국내 압력",
  resource: "자원 수준",
  resource_level: "자원 수준",
  alliance_trust: "동맹 신뢰",
  stability: "안정도",
};

const DECISION_TITLES: Record<string, string> = {
  geopolitics_actor_response: "지정학 이벤트 대응",
  geopolitics_direction: "시나리오 방향 결정",
};

function getCategoryMeta(opt: DecisionOption) {
  const cat = String(
    opt.data?.category ?? opt.data?.action_category ?? opt.data?.direction ?? "nothing",
  ).toLowerCase();
  return CATEGORY_META[cat] ?? CATEGORY_META.nothing;
}

function getDeltas(opt: DecisionOption): { key: string; label: string; val: number }[] {
  const result: { key: string; label: string; val: number }[] = [];
  for (const [k, v] of Object.entries(opt.data)) {
    if (k.startsWith("delta_") && typeof v === "number") {
      const rawKey = k.replace("delta_", "");
      result.push({
        key: rawKey,
        label: DELTA_LABELS[rawKey] ?? rawKey,
        val: v,
      });
    }
  }
  return result;
}

function getNarrative(dp: DecisionPoint): string {
  const firstData = dp.options[0]?.data;
  if (firstData?.narrative) return String(firstData.narrative);

  const trigger = firstData?.trigger_event as Record<string, unknown> | undefined;
  if (trigger?.description) return String(trigger.description);

  const sourceActor = trigger?.source_actor ? String(trigger.source_actor) : null;
  const action = trigger?.action_type
    ? String(trigger.action_type).replace(/_/g, " ")
    : null;
  if (sourceActor && action) {
    return `${sourceActor}이(가) ${action} 행동을 취했습니다. 대응 방안을 결정하십시오.`;
  }

  return "상황이 전개되고 있습니다. 아래 선택지 중 대응 방안을 결정하십시오.";
}

export default function DecisionCard({
  decisionPoint,
  round,
  onConfirm,
  onWhatIf,
}: DecisionCardProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const title = DECISION_TITLES[decisionPoint.type] ?? "외교 위기";
  const narrative = getNarrative(decisionPoint);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-auto">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" />

      <div className="relative w-full max-w-[550px] mx-4 max-h-[85vh] flex flex-col rounded-lg border border-[var(--border-secondary)] bg-[var(--bg-tertiary)] shadow-2xl">
        <div className="shrink-0 px-5 py-3.5 border-b border-[var(--border-secondary)] flex items-center gap-2.5">
          <span className="text-base leading-none">⚠️</span>
          <span className="text-sm font-bold text-[var(--text-primary)] tracking-wide">
            {title}
          </span>
          <span className="text-[10px] font-bold font-mono text-[var(--text-muted)] ml-auto">
            Round {round}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
          <p className="text-xs text-[var(--text-muted)] leading-relaxed border-l-2 border-amber-500/40 pl-3 italic">
            {narrative}
          </p>

          <div className="flex flex-col gap-2.5">
            {decisionPoint.options.map((opt) => (
              <OptionCard
                key={opt.id}
                option={opt}
                isSelected={selectedId === opt.id}
                isRecommended={opt.id === decisionPoint.recommended}
                isEngineRecommended={Boolean(opt.data?.engine_recommended)}
                onSelect={() => setSelectedId(opt.id)}
              />
            ))}
          </div>
        </div>

        <div className="shrink-0 px-5 py-4 border-t border-[var(--border-secondary)] flex gap-3">
          <button
            disabled={!selectedId}
            onClick={() => selectedId && onConfirm(selectedId)}
            className={`flex-1 py-2.5 rounded-md text-sm font-bold tracking-wide transition-colors duration-150 ${
              selectedId
                ? "bg-amber-500/90 text-black cursor-pointer hover:bg-amber-400"
                : "bg-[var(--border-secondary)] text-[var(--text-muted)] cursor-not-allowed"
            }`}
          >
            결정 확정
          </button>
          <button
            onClick={onWhatIf}
            className="px-4 py-2.5 rounded-md text-sm font-semibold text-[var(--text-muted)] border border-[var(--border-secondary)] bg-transparent cursor-pointer transition-colors duration-150 hover:border-[var(--accent-cyan)] hover:text-[var(--accent-cyan)]"
          >
            What-If 분기
          </button>
        </div>
      </div>
    </div>
  );
}

function OptionCard({
  option,
  isSelected,
  isRecommended,
  isEngineRecommended,
  onSelect,
}: {
  option: DecisionOption;
  isSelected: boolean;
  isRecommended: boolean;
  isEngineRecommended: boolean;
  onSelect: () => void;
}) {
  const meta = getCategoryMeta(option);
  const deltas = getDeltas(option);
  const advisor = option.reasoning;

  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className={`flex flex-col gap-2 p-3 rounded border border-[var(--border-secondary)] border-l-[3px] ${meta.borderCls} transition-all duration-150 cursor-pointer bg-[var(--bg-primary)] ${
        isSelected
          ? "ring-1 ring-[var(--accent-cyan)] shadow-lg"
          : "hover:ring-1 hover:ring-[rgba(34,211,238,0.3)]"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm leading-none">{meta.emoji}</span>
        <span className="text-xs font-bold text-[var(--text-primary)] flex-1">
          {option.label}
        </span>
        {isEngineRecommended && (
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-[rgba(34,211,238,0.12)] text-[var(--accent-cyan)]">
            엔진 추천
          </span>
        )}
        {isRecommended && !isEngineRecommended && (
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-[rgba(34,211,238,0.12)] text-[var(--accent-cyan)]">
            AI 추천
          </span>
        )}
        <div
          className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
            isSelected
              ? "border-[var(--accent-cyan)] bg-[rgba(34,211,238,0.15)]"
              : "border-[var(--border-secondary)]"
          }`}
        >
          {isSelected && (
            <div className="w-2 h-2 rounded-full bg-[var(--accent-cyan)]" />
          )}
        </div>
      </div>

      {option.description && (
        <p className="text-[11px] text-[var(--text-muted)] leading-relaxed pl-6">
          {option.description}
        </p>
      )}

      {deltas.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pl-6">
          {deltas.map((d) => {
            const positive = d.val >= 0;
            const colorCls = positive
              ? "text-red-400 bg-red-400/10"
              : "text-emerald-400 bg-emerald-400/10";
            return (
              <span
                key={d.key}
                className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded ${colorCls}`}
              >
                {d.label} {positive ? "↑" : "↓"}
                {Math.abs(d.val * 100).toFixed(0)}%
              </span>
            );
          })}
        </div>
      )}

      {advisor && (
        <div className="pl-6 flex items-start gap-1.5 mt-0.5">
          <span className="text-[10px] shrink-0">📊</span>
          <span className="text-[10px] text-[var(--text-muted)] leading-relaxed italic">
            &ldquo;{advisor}&rdquo;
          </span>
        </div>
      )}
    </div>
  );
}
