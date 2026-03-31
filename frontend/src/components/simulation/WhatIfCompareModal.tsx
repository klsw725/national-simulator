"use client";

import { useEffect, useState } from "react";
import { X, Loader2 } from "lucide-react";
import VarianceCard from "./whatif/VarianceCard";
import ActorColumn from "./whatif/ActorColumn";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";
import {
  getWhatIfBranch,
  getWhatIfComparison,
  WhatIfBranch,
  WhatIfComparison,
} from "@/lib/gatewayApi";

interface Props {
  scenarioId: string;
  branchId: string;
  onClose: () => void;
}

export default function WhatIfCompareModal({ scenarioId, branchId, onClose }: Props) {
  const [branch, setBranch] = useState<WhatIfBranch | null>(null);
  const [comparison, setComparison] = useState<WhatIfComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [b, c] = await Promise.all([
          getWhatIfBranch(scenarioId, branchId),
          getWhatIfComparison(scenarioId, branchId),
        ]);
        if (cancelled) return;
        setBranch(b);
        setComparison(c);
      } catch {
        if (!cancelled) setError("비교 데이터를 불러올 수 없습니다");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [scenarioId, branchId]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const chartData = comparison
    ? comparison.tension_curves.original.map((val, i) => ({
        round: `R${i + 1}`,
        original: val,
        branch: comparison.tension_curves.branch[i] ?? null,
      }))
    : [];

  const tensionAdv = comparison?.tension_advantage ?? 0;
  const tensionColor = tensionAdv < 0 ? "#22c55e" : tensionAdv > 0 ? "#ef4444" : "var(--text-muted)";
  const tensionLabel = tensionAdv < 0 ? "긴장 완화" : tensionAdv > 0 ? "긴장 증가" : "변화 없음";

  const stepOrig = comparison?.step_variance.original ?? 0;
  const stepBranch = comparison?.step_variance.branch ?? 0;
  const stepBetter = stepBranch < stepOrig;

  const slopeOrig = comparison?.slope_variance.original ?? 0;
  const slopeBranch = comparison?.slope_variance.branch ?? 0;
  const slopeBetter = slopeBranch < slopeOrig;

  const modText = branch?.modification ?? "";
  const truncMod = modText.length > 60 ? modText.slice(0, 60) + "..." : modText;

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 29,
          background: "rgba(0,0,0,0.6)",
        }}
      />

      <div
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          zIndex: 30,
          width: "80vw",
          maxHeight: "85vh",
          overflowY: "auto",
          background: "var(--bg-secondary)",
          border: "1px solid var(--border-secondary)",
          borderRadius: 12,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {loading ? (
          <div
            style={{
              height: 300,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              color: "var(--text-muted)",
              fontSize: 13,
            }}
          >
            <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
            비교 데이터 로딩 중...
          </div>
        ) : error ? (
          <div
            style={{
              height: 200,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ef4444",
              fontSize: 13,
              padding: 24,
            }}
          >
            {error}
          </div>
        ) : (
          <>
            <div
              style={{
                padding: "20px 24px 16px",
                borderBottom: "1px solid var(--border-secondary)",
                position: "relative",
              }}
            >
              <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)" }}>
                What-If 비교: {truncMod}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                원본 시나리오 · 분기 시점:{" "}
                {branch?.branch_point_round !== null && branch?.branch_point_round !== undefined
                  ? `라운드 ${branch.branch_point_round}`
                  : "분기 시점 미지정"}
              </div>
              <button
                onClick={onClose}
                style={{
                  position: "absolute",
                  top: 16,
                  right: 16,
                  background: "none",
                  border: "none",
                  color: "var(--text-muted)",
                  cursor: "pointer",
                  padding: 4,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 24 }}>
              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text-muted)",
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.05em",
                    marginBottom: 12,
                  }}
                >
                  Tension Curve
                </div>
                <div
                  style={{
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border-secondary)",
                    borderRadius: 8,
                    padding: "16px 12px 8px",
                  }}
                >
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="var(--border-secondary)" strokeDasharray="3 3" />
                      <XAxis
                        dataKey="round"
                        tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                        stroke="var(--text-muted)"
                        tickLine={false}
                      />
                      <YAxis
                        domain={[0, 1]}
                        tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                        stroke="var(--text-muted)"
                        tickLine={false}
                        width={32}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "var(--bg-secondary)",
                          border: "1px solid var(--border-secondary)",
                          borderRadius: 6,
                          fontSize: 11,
                          color: "var(--text-primary)",
                        }}
                        labelStyle={{ color: "var(--text-muted)", fontSize: 10, marginBottom: 4 }}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: 11, color: "var(--text-muted)" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="original"
                        name="원본"
                        stroke="#22d3ee"
                        strokeWidth={2}
                        dot={false}
                        activeDot={{ r: 3, fill: "#22d3ee" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="branch"
                        name="분기"
                        stroke="#a78bfa"
                        strokeWidth={2}
                        strokeDasharray="6 3"
                        dot={false}
                        activeDot={{ r: 3, fill: "#a78bfa" }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text-muted)",
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.05em",
                    marginBottom: 12,
                  }}
                >
                  MAXS Metrics
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                  <div
                    style={{
                      background: "var(--bg-tertiary)",
                      border: "1px solid var(--border-secondary)",
                      borderRadius: 8,
                      padding: 16,
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase" as const, letterSpacing: "0.04em" }}>
                      Tension Advantage
                    </div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: tensionColor, fontVariantNumeric: "tabular-nums" }}>
                      {tensionAdv > 0 ? "+" : ""}{tensionAdv.toFixed(3)}
                    </div>
                    <div style={{ fontSize: 10, color: tensionColor }}>
                      {tensionLabel}
                    </div>
                  </div>

                  <VarianceCard
                    label="Step Variance"
                    original={stepOrig}
                    branch={stepBranch}
                    betterLabel="더 안정적"
                    worseLabel="덜 안정적"
                    isBetter={stepBetter}
                  />

                  <VarianceCard
                    label="Slope Variance"
                    original={slopeOrig}
                    branch={slopeBranch}
                    betterLabel="더 일관적"
                    worseLabel="덜 일관적"
                    isBetter={slopeBetter}
                  />
                </div>
              </div>

              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text-muted)",
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.05em",
                    marginBottom: 12,
                  }}
                >
                  Actor Diff
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <ActorColumn
                    title="원본만 출현"
                    actors={comparison?.actor_diff.only_original ?? []}
                    accentColor="#22d3ee"
                  />
                  <ActorColumn
                    title="분기만 출현"
                    actors={comparison?.actor_diff.only_branch ?? []}
                    accentColor="#a78bfa"
                  />
                </div>
                <div
                  style={{
                    marginTop: 10,
                    display: "flex",
                    gap: 16,
                    flexWrap: "wrap",
                    fontSize: 11,
                    color: "var(--text-muted)",
                  }}
                >
                  <span>공통 행위자: {comparison?.actor_diff.common.length ?? 0}명</span>
                  <span>
                    액션 수 차이:{" "}
                    <span style={{ color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
                      {(comparison?.action_count_delta ?? 0) > 0 ? "+" : ""}
                      {comparison?.action_count_delta ?? 0}건
                    </span>
                  </span>
                  <span>
                    지정학 이벤트 차이:{" "}
                    <span style={{ color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
                      {(comparison?.geopolitics_delta ?? 0) > 0 ? "+" : ""}
                      {comparison?.geopolitics_delta ?? 0}건
                    </span>
                  </span>
                </div>
              </div>

              {comparison?.causal_attribution && (
                <div>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "var(--text-muted)",
                      textTransform: "uppercase" as const,
                      letterSpacing: "0.05em",
                      marginBottom: 12,
                    }}
                  >
                    Causal Attribution
                  </div>
                  <div
                    style={{
                      background: "var(--bg-tertiary)",
                      border: "1px solid var(--border-secondary)",
                      borderRadius: 8,
                      padding: 16,
                    }}
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {Object.entries(comparison.causal_attribution.tension_advantage_explained)
                        .sort(([, a], [, b]) => b - a)
                        .map(([factor, contribution]) => (
                          <div key={factor} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span
                              style={{
                                fontSize: 11,
                                color: "var(--text-muted)",
                                width: 140,
                                flexShrink: 0,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {factor}
                            </span>
                            <div
                              style={{
                                flex: 1,
                                height: 10,
                                background: "rgba(255,255,255,0.06)",
                                borderRadius: 999,
                                overflow: "hidden",
                              }}
                            >
                              <div
                                style={{
                                  height: "100%",
                                  width: `${Math.min(Math.abs(contribution) * 100, 100)}%`,
                                  background: "#3b82f6",
                                  borderRadius: 999,
                                }}
                              />
                            </div>
                            <span
                              style={{
                                fontSize: 11,
                                color: "var(--text-primary)",
                                width: 40,
                                textAlign: "right",
                                fontVariantNumeric: "tabular-nums",
                                flexShrink: 0,
                              }}
                            >
                              {(contribution * 100).toFixed(0)}%
                            </span>
                          </div>
                        ))}
                    </div>
                    <div
                      style={{
                        marginTop: 12,
                        display: "flex",
                        gap: 12,
                        fontSize: 10,
                        color: "var(--text-muted)",
                      }}
                    >
                      <span>신뢰도: {comparison.causal_attribution.confidence}</span>
                      <span>·</span>
                      <span>방법: {comparison.causal_attribution.method}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div
              style={{
                padding: "12px 24px",
                borderTop: "1px solid var(--border-secondary)",
                fontSize: 10,
                color: "var(--text-muted)",
                fontStyle: "italic",
              }}
            >
              Heuristic 분석 — 단일 실행 기반 추정치. 확률적 변동을 포함합니다.
            </div>
          </>
        )}
      </div>
    </>
  );
}
