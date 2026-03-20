"use client";

import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import type { ScenarioFormData, PipelineMode } from "@/types/simulation";

const REGION_PRESETS: { label: string; name: string; bbox: [number, number, number, number] }[] = [
  { label: "South China Sea", name: "South China Sea", bbox: [108, 5, 121, 23] },
  { label: "Taiwan Strait", name: "Taiwan Strait", bbox: [117, 22, 122, 26] },
  { label: "East China Sea", name: "East China Sea", bbox: [122, 25, 132, 35] },
  { label: "Korean Peninsula", name: "Korean Peninsula", bbox: [124, 33, 132, 43] },
  { label: "Strait of Hormuz", name: "Strait of Hormuz", bbox: [54, 24, 58, 28] },
];

interface Props {
  onSubmit: (data: ScenarioFormData) => Promise<void>;
  isRunning: boolean;
}

export default function ScenarioForm({ onSubmit, isRunning }: Props) {
  const [name, setName] = useState("");
  const [regionIdx, setRegionIdx] = useState(0);
  const [question, setQuestion] = useState("");
  const [maxRounds, setMaxRounds] = useState(10);
  const [submitting, setSubmitting] = useState(false);
  const [mode, setMode] = useState<PipelineMode>("auto");

  const region = REGION_PRESETS[regionIdx];

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting || isRunning) return;

    setSubmitting(true);
    try {
      await onSubmit({
        name: name.trim() || `${region.name} scenario`,
        region: { bbox: region.bbox, name: region.name },
        question: question.trim(),
        max_rounds: maxRounds,
        data_sources: ["ships", "flights", "satellites"],
        mode,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 12px",
    background: "var(--bg-primary)",
    border: "1px solid var(--border-secondary)",
    borderRadius: 4,
    color: "var(--text-primary)",
    fontSize: 13,
    outline: "none",
    fontFamily: "inherit",
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: 11,
    fontWeight: 600,
    color: "var(--text-muted)",
    marginBottom: 6,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Name */}
      <div>
        <label style={labelStyle}>시나리오 이름</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="예: 남중국해 분쟁 시나리오"
          style={inputStyle}
        />
      </div>

      {/* Region */}
      <div>
        <label style={labelStyle}>분석 지역</label>
        <select
          value={regionIdx}
          onChange={(e) => setRegionIdx(Number(e.target.value))}
          style={{ ...inputStyle, cursor: "pointer" }}
        >
          {REGION_PRESETS.map((r, i) => (
            <option key={r.name} value={i}>
              {r.label}
            </option>
          ))}
        </select>
        <div
          style={{
            marginTop: 6,
            padding: "6px 10px",
            background: "rgba(34, 211, 238, 0.06)",
            border: "1px solid rgba(34, 211, 238, 0.15)",
            borderRadius: 4,
            fontSize: 11,
            fontFamily: "monospace",
            color: "var(--accent-cyan)",
          }}
        >
          BBOX: [{region.bbox.join(", ")}]
        </div>
      </div>

      {/* Question */}
      <div>
        <label style={labelStyle}>분석 질문</label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="예: 이 지역의 군사적 긴장 상황을 분석하시오"
          rows={3}
          style={{ ...inputStyle, resize: "vertical", minHeight: 60 }}
        />
      </div>

      {/* Max Rounds */}
      <div>
        <label style={labelStyle}>
          시뮬레이션 라운드: {maxRounds}
        </label>
        <input
          type="range"
          min={1}
          max={30}
          value={maxRounds}
          onChange={(e) => setMaxRounds(Number(e.target.value))}
          style={{
            width: "100%",
            accentColor: "var(--accent-cyan)",
            cursor: "pointer",
          }}
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 10,
            color: "var(--text-muted)",
            marginTop: 2,
          }}
        >
          <span>1</span>
          <span>30</span>
        </div>
      </div>

      <div>
        <label style={labelStyle}>파이프라인 모드</label>
        <div
          style={{
            display: "flex",
            background: "var(--bg-primary)",
            border: "1px solid var(--border-secondary)",
            borderRadius: 4,
            overflow: "hidden",
          }}
        >
          {([
            { value: "auto" as const, label: "자동 실행" },
            { value: "checkpoint" as const, label: "단계별 검토" },
          ]).map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setMode(opt.value)}
              style={{
                flex: 1,
                padding: "7px 12px",
                background: mode === opt.value ? "var(--accent-cyan)" : "transparent",
                color: mode === opt.value ? "var(--bg-primary)" : "var(--text-muted)",
                border: "none",
                fontSize: 12,
                fontWeight: mode === opt.value ? 700 : 400,
                cursor: "pointer",
                transition: "background 0.15s, color 0.15s",
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={submitting || isRunning}
        style={{
          padding: "10px 16px",
          background: submitting || isRunning ? "rgba(34, 211, 238, 0.15)" : "var(--accent-cyan)",
          color: submitting || isRunning ? "var(--text-muted)" : "var(--bg-primary)",
          border: "none",
          borderRadius: 4,
          fontSize: 13,
          fontWeight: 700,
          cursor: submitting || isRunning ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          transition: "background 0.15s, color 0.15s",
        }}
      >
        {submitting && <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />}
        {submitting ? "처리 중..." : isRunning ? "실행 중..." : "시뮬레이션 시작"}
      </button>
    </form>
  );
}
