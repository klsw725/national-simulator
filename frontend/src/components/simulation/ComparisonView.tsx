"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/gatewayApi";
import type { Scenario } from "@/types/simulation";

interface ComparisonViewProps {
  scenarios: Scenario[];
}

type CompareResult = Awaited<ReturnType<typeof api.compareScenarios>>;

export default function ComparisonView({ scenarios }: ComparisonViewProps) {
  const completed = scenarios.filter((s) => s.status === "completed");
  const [idA, setIdA] = useState("");
  const [idB, setIdB] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = useCallback(async () => {
    if (!idA || !idB || idA === idB) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.compareScenarios(idA, idB);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "비교 실패");
    } finally {
      setLoading(false);
    }
  }, [idA, idB]);

  useEffect(() => {
    setResult(null);
  }, [idA, idB]);

  const selectStyle: React.CSSProperties = {
    flex: 1,
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 4,
    padding: "6px 8px",
    fontSize: 11,
    color: "#d1d5db",
    outline: "none",
  };

  if (completed.length < 2) {
    return (
      <div style={{ padding: 24, color: "rgb(107, 114, 128)", fontSize: 13, textAlign: "center" }}>
        비교하려면 완료된 시나리오가 2개 이상 필요합니다
      </div>
    );
  }

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <select value={idA} onChange={(e) => setIdA(e.target.value)} style={selectStyle}>
          <option value="">시나리오 A 선택</option>
          {completed.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <span style={{ color: "rgb(107, 114, 128)", fontSize: 12 }}>vs</span>
        <select value={idB} onChange={(e) => setIdB(e.target.value)} style={selectStyle}>
          <option value="">시나리오 B 선택</option>
          {completed.filter((s) => s.id !== idA).map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      <button
        onClick={handleCompare}
        disabled={!idA || !idB || idA === idB || loading}
        style={{
          padding: "8px 12px",
          background: idA && idB && idA !== idB ? "var(--accent-cyan)" : "rgba(255,255,255,0.05)",
          border: "none",
          borderRadius: 6,
          color: idA && idB ? "var(--bg-primary)" : "rgb(75, 85, 99)",
          fontSize: 12,
          fontWeight: 600,
          cursor: idA && idB ? "pointer" : "default",
        }}
      >
        {loading ? "비교 중..." : "비교하기"}
      </button>

      {error && <div style={{ fontSize: 11, color: "#ef4444" }}>{error}</div>}

      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <ScenarioCard label="A" data={result.scenario_a} color="#22d3ee" />
            <ScenarioCard label="B" data={result.scenario_b} color="#a855f7" />
          </div>

          <DiffSection diff={result.diff} />
        </div>
      )}
    </div>
  );
}

function ScenarioCard({
  label,
  data,
  color,
}: {
  label: string;
  data: CompareResult["scenario_a"];
  color: string;
}) {
  return (
    <div
      style={{
        flex: 1,
        background: "rgba(255,255,255,0.03)",
        border: `1px solid ${color}33`,
        borderRadius: 6,
        padding: 12,
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 700, color, marginBottom: 6 }}>
        {label}: {data.name}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
        <Row label="지역" value={data.region_name} />
        <Row label="행위자" value={`${data.actors.length}개`} />
        <Row label="액션" value={`${data.action_count}건`} />
        <Row label="지정학" value={`${data.geopolitics_events}건`} />
      </div>
    </div>
  );
}

function DiffSection({ diff }: { diff: CompareResult["diff"] }) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.05)",
        borderRadius: 6,
        padding: 12,
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 600, color: "rgb(107, 114, 128)", textTransform: "uppercase", marginBottom: 8 }}>
        차이점
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>
        <DiffRow label="액션 수 차이" value={diff.action_count_delta} suffix="건" />
        <DiffRow label="지정학 이벤트 차이" value={diff.geopolitics_events_delta} suffix="건" />
        {diff.actors_only_a.length > 0 && (
          <div style={{ color: "#d1d5db" }}>
            <span style={{ color: "rgb(107,114,128)" }}>A에만 있는 행위자:</span>{" "}
            {diff.actors_only_a.join(", ")}
          </div>
        )}
        {diff.actors_only_b.length > 0 && (
          <div style={{ color: "#d1d5db" }}>
            <span style={{ color: "rgb(107,114,128)" }}>B에만 있는 행위자:</span>{" "}
            {diff.actors_only_b.join(", ")}
          </div>
        )}
        {diff.actors_common.length > 0 && (
          <div style={{ color: "rgb(107,114,128)" }}>
            공통 행위자: {diff.actors_common.join(", ")}
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: "rgb(107,114,128)" }}>{label}</span>
      <span style={{ color: "#d1d5db" }}>{value}</span>
    </div>
  );
}

function DiffRow({ label, value, suffix }: { label: string; value: number; suffix: string }) {
  const color = value > 0 ? "#22c55e" : value < 0 ? "#ef4444" : "#9ca3af";
  const sign = value > 0 ? "+" : "";
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: "rgb(107,114,128)" }}>{label}</span>
      <span style={{ color, fontVariantNumeric: "tabular-nums" }}>
        {sign}{value} {suffix}
      </span>
    </div>
  );
}
