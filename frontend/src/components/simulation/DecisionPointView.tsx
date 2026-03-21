"use client";

import { useEffect, useState } from "react";
import { Star, Check, ChevronDown, Play, Edit3, Sparkles } from "lucide-react";
import type { DecisionPoint, DecisionOption } from "@/types/simulation";
import { getDecisionPoints, resolveDecisionPoint } from "@/lib/gatewayApi";

interface Props {
  scenarioId: string;
  type: "seed_selection" | "parameter_recommendation";
  onResolved: (selectedOption: DecisionOption, dpId: string) => void;
}

export default function DecisionPointView({ scenarioId, type, onResolved }: Props) {
  const [decisionPoint, setDecisionPoint] = useState<DecisionPoint | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [isCustom, setIsCustom] = useState(false);
  const [customData, setCustomData] = useState<Record<string, unknown>>({});
  const [isResolving, setIsResolving] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    getDecisionPoints(scenarioId, "pending")
      .then((res) => {
        const match = res.decision_points.find((dp) => dp.type === type);
        setDecisionPoint(match ?? null);
        if (match?.recommended) {
          setSelectedOptionId(match.recommended);
        }
      })
      .catch(() => setDecisionPoint(null))
      .finally(() => setIsLoading(false));
  }, [scenarioId, type]);

  const handleSubmit = () => {
    if (!decisionPoint || (!selectedOptionId && !isCustom)) return;
    setIsResolving(true);

    const payload: { selected_option_id?: string; custom_data?: Record<string, unknown> } = isCustom
      ? { custom_data: customData }
      : { selected_option_id: selectedOptionId! };

    resolveDecisionPoint(scenarioId, decisionPoint.id, payload)
      .then((resolved) => {
        const chosen = isCustom
          ? { id: "custom", label: "Custom", description: "", confidence: 1, reasoning: "", data: customData }
          : decisionPoint.options.find((o) => o.id === selectedOptionId)!;
        onResolved(chosen, resolved.id);
      })
      .catch(() => {})
      .finally(() => setIsResolving(false));
  };

  if (isLoading) {
    return (
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        padding: 16,
        background: "var(--bg-primary)",
        border: "1px solid var(--border-secondary)",
        borderRadius: 6,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <LoadingSpinner />
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
            {type === "seed_selection" ? "Seed" : "Parameter"} 결정 지점 로딩 중...
          </span>
        </div>
      </div>
    );
  }

  if (!decisionPoint) {
    return (
      <div style={{
        padding: 16,
        background: "var(--bg-primary)",
        border: "1px solid var(--border-secondary)",
        borderRadius: 6,
        textAlign: "center",
      }}>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          결정 지점이 없습니다
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Sparkles size={14} color="var(--accent-cyan)" />
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
          {type === "seed_selection" ? "Seed 선택" : "파라미터 추천"}
        </span>
        <span style={{
          fontSize: 10,
          padding: "2px 6px",
          borderRadius: 999,
          background: "rgba(34, 211, 238, 0.1)",
          color: "var(--accent-cyan)",
          fontWeight: 600,
        }}>
          {decisionPoint.options.length}개 옵션
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {decisionPoint.options.map((option) => (
          <OptionCard
            key={option.id}
            option={option}
            isRecommended={option.id === decisionPoint.recommended}
            isSelected={!isCustom && selectedOptionId === option.id}
            type={type}
            onSelect={() => {
              setSelectedOptionId(option.id);
              setIsCustom(false);
            }}
          />
        ))}
      </div>

      {decisionPoint.allow_custom && (
        <CustomInputSection
          type={type}
          isCustom={isCustom}
          customData={customData}
          onToggle={() => {
            setIsCustom((v) => !v);
            if (!isCustom) setSelectedOptionId(null);
          }}
          onChange={setCustomData}
        />
      )}

      <button
        disabled={(!selectedOptionId && !isCustom) || isResolving}
        onClick={handleSubmit}
        style={{
          width: "100%",
          padding: "8px 12px",
          background: (!selectedOptionId && !isCustom) || isResolving
            ? "var(--border-secondary)"
            : "var(--accent-cyan)",
          border: "none",
          borderRadius: 4,
          color: (!selectedOptionId && !isCustom) || isResolving
            ? "var(--text-muted)"
            : "var(--bg-primary)",
          fontSize: 12,
          fontWeight: 700,
          cursor: (!selectedOptionId && !isCustom) || isResolving ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
        }}
      >
        {isResolving ? (
          <>
            <LoadingSpinner />
            처리 중...
          </>
        ) : (
          <>
            <Play size={12} />
            선택 확정
          </>
        )}
      </button>
    </div>
  );
}

function OptionCard({
  option,
  isRecommended,
  isSelected,
  type,
  onSelect,
}: {
  option: DecisionOption;
  isRecommended: boolean;
  isSelected: boolean;
  type: "seed_selection" | "parameter_recommendation";
  onSelect: () => void;
}) {
  const confidenceColor = option.confidence >= 0.7
    ? "var(--accent-cyan)"
    : option.confidence >= 0.4
      ? "var(--accent-amber, #f59e0b)"
      : "var(--accent-red)";

  return (
    <div
      onClick={onSelect}
      style={{
        background: "var(--bg-primary)",
        border: isSelected
          ? "1.5px solid var(--accent-cyan)"
          : "1px solid var(--border-secondary)",
        borderRadius: 6,
        padding: 10,
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        transition: "border-color 0.15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{
          width: 18,
          height: 18,
          borderRadius: "50%",
          border: isSelected
            ? "2px solid var(--accent-cyan)"
            : "1.5px solid var(--border-secondary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          background: isSelected ? "rgba(34, 211, 238, 0.15)" : "transparent",
        }}>
          {isSelected && <Check size={10} color="var(--accent-cyan)" />}
        </div>

        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", flex: 1 }}>
          {option.label}
        </span>

        {isRecommended && (
          <span style={{
            fontSize: 10,
            fontWeight: 600,
            padding: "2px 8px",
            borderRadius: 999,
            background: "rgba(34, 211, 238, 0.12)",
            color: "var(--accent-cyan)",
            display: "flex",
            alignItems: "center",
            gap: 3,
            flexShrink: 0,
          }}>
            <Star size={9} />
            AI 추천
          </span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{
          flex: 1,
          height: 4,
          borderRadius: 999,
          background: "var(--border-secondary)",
          overflow: "hidden",
        }}>
          <div style={{
            width: `${Math.round(option.confidence * 100)}%`,
            height: "100%",
            background: confidenceColor,
            transition: "width 0.3s ease",
          }} />
        </div>
        <span style={{
          fontSize: 11,
          fontWeight: 600,
          color: confidenceColor,
          fontFamily: "monospace",
          flexShrink: 0,
        }}>
          {Math.round(option.confidence * 100)}%
        </span>
      </div>

      <span style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>
        {option.reasoning}
      </span>

      {type === "seed_selection" && option.data.seed_text != null && (
        <div style={{
          padding: "6px 8px",
          background: "var(--bg-secondary)",
          borderRadius: 4,
          border: "1px solid var(--border-secondary)",
        }}>
          <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "monospace", lineHeight: 1.4 }}>
            {String(option.data.seed_text).length > 150
              ? String(option.data.seed_text).slice(0, 150) + "..."
              : String(option.data.seed_text)}
          </span>
        </div>
      )}

      {type === "parameter_recommendation" && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "2px 12px",
          padding: "6px 8px",
          background: "var(--bg-secondary)",
          borderRadius: 4,
          border: "1px solid var(--border-secondary)",
        }}>
          <ParamRow label="Platform" value={option.data.platform} />
          <ParamRow label="Rounds" value={option.data.max_rounds} />
          <ParamRow label="Hours" value={option.data.simulation_hours} />
          <ParamRow label="Geopolitics" value={option.data.geopolitics_enabled} />
          <ParamRow label="Web Search" value={option.data.web_search_enabled} />
        </div>
      )}
    </div>
  );
}

function ParamRow({ label, value }: { label: string; value: unknown }) {
  if (value === undefined) return null;
  const display = typeof value === "boolean" ? (value ? "ON" : "OFF") : String(value);
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-muted)", padding: "2px 0" }}>
      <span>{label}</span>
      <span style={{ fontWeight: 700, fontFamily: "monospace", color: "var(--text-primary)" }}>
        {display}
      </span>
    </div>
  );
}

function CustomInputSection({
  type,
  isCustom,
  customData,
  onToggle,
  onChange,
}: {
  type: "seed_selection" | "parameter_recommendation";
  isCustom: boolean;
  customData: Record<string, unknown>;
  onToggle: () => void;
  onChange: (data: Record<string, unknown>) => void;
}) {
  return (
    <div style={{
      background: "var(--bg-primary)",
      border: isCustom
        ? "1.5px solid var(--accent-cyan)"
        : "1px solid var(--border-secondary)",
      borderRadius: 6,
      overflow: "hidden",
    }}>
      <div
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "8px 10px",
          cursor: "pointer",
        }}
      >
        <Edit3 size={12} color={isCustom ? "var(--accent-cyan)" : "var(--text-muted)"} />
        <span style={{
          fontSize: 12,
          fontWeight: 600,
          color: isCustom ? "var(--accent-cyan)" : "var(--text-muted)",
          flex: 1,
        }}>
          커스텀 입력
        </span>
        <ChevronDown
          size={12}
          color="var(--text-muted)"
          style={{
            transform: isCustom ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.15s ease",
          }}
        />
      </div>

      {isCustom && (
        <div style={{ padding: "0 10px 10px", display: "flex", flexDirection: "column", gap: 8 }}>
          {type === "seed_selection" && (
            <textarea
              placeholder="Seed 텍스트를 입력하세요..."
              value={(customData.seed_text as string) ?? ""}
              onChange={(e) => onChange({ ...customData, seed_text: e.target.value })}
              rows={6}
              style={{
                width: "100%",
                padding: "8px 10px",
                background: "var(--bg-secondary)",
                border: "1px solid var(--accent-cyan)",
                borderRadius: 4,
                color: "var(--text-primary)",
                fontSize: 12,
                fontFamily: "monospace",
                lineHeight: 1.5,
                resize: "vertical",
                outline: "none",
              }}
            />
          )}

          {type === "parameter_recommendation" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <NumberInput
                label="Rounds"
                value={(customData.rounds as number) ?? 10}
                min={1}
                max={100}
                onChange={(v) => onChange({ ...customData, rounds: v })}
              />
              <NumberInput
                label="Hours"
                value={(customData.hours as number) ?? 24}
                min={1}
                max={720}
                onChange={(v) => onChange({ ...customData, hours: v })}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function NumberInput({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ fontSize: 12, color: "var(--text-muted)", width: 50 }}>
        {label}
      </span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{
          width: 70,
          padding: "6px 8px",
          background: "var(--bg-secondary)",
          border: "1px solid var(--accent-cyan)",
          borderRadius: 4,
          color: "var(--text-primary)",
          fontSize: 13,
          fontWeight: 600,
          textAlign: "center",
          outline: "none",
        }}
      />
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div style={{
      width: 12,
      height: 12,
      border: "2px solid var(--border-secondary)",
      borderTopColor: "var(--accent-cyan)",
      borderRadius: "50%",
      animation: "dpv-spin 0.6s linear infinite",
    }}>
      <style>{`@keyframes dpv-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
