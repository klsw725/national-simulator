"use client";

import { useEffect, useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import type { DecisionRecord } from "@/types/simulation";

interface DebriefViewProps {
  totalRounds: number;
  tensionCurve: number[];
  decisions: DecisionRecord[];
  finalTension: number;
  onViewReport: () => void;
  onNewSimulation: () => void;
  onWhatIf: (round: number) => void;
  onClose: () => void;
}

export default function DebriefView({
  totalRounds,
  tensionCurve,
  decisions,
  finalTension,
  onViewReport,
  onNewSimulation,
  onWhatIf,
  onClose,
}: DebriefViewProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const chartData = useMemo(
    () =>
      tensionCurve.map((val, i) => ({
        round: `R${i + 1}`,
        tension: val,
      })),
    [tensionCurve],
  );

  const decisionRoundSet = useMemo(
    () => new Set(decisions.map((d) => d.round)),
    [decisions],
  );

  const peakTension = useMemo(
    () => Math.max(...tensionCurve, 0),
    [tensionCurve],
  );

  const lastWhatIfRound = decisions.length > 0
    ? decisions[decisions.length - 1].round
    : 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-auto">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm cursor-pointer"
        onClick={onClose}
      />

      <div
        className="relative z-10 flex flex-col gap-6 w-[min(90vw,860px)] max-h-[88vh] overflow-y-auto rounded-xl border border-[var(--border-secondary)]"
        style={{ background: "var(--bg-secondary)", padding: "32px 36px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-7 h-7 rounded-full bg-[rgba(0,0,0,0.4)] border border-[var(--border-secondary)] text-[var(--text-muted)] text-xs font-bold flex items-center justify-center cursor-pointer transition-colors hover:bg-[rgba(0,0,0,0.7)] hover:text-[var(--text-primary)]"
        >
          ✕
        </button>

        <div>
          <h2
            className="text-lg font-bold"
            style={{ color: "var(--text-primary)" }}
          >
            📊 시뮬레이션 디브리프
          </h2>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
            {totalRounds}라운드 완료 · 최종 긴장도 {finalTension.toFixed(2)}
          </p>
        </div>

        <div>
          <div
            className="text-[11px] font-semibold uppercase tracking-wider mb-3"
            style={{ color: "var(--text-muted)" }}
          >
            긴장도 곡선
          </div>
          <div
            className="rounded-lg border border-[var(--border-secondary)]"
            style={{
              background: "var(--bg-tertiary)",
              padding: "16px 12px 8px",
            }}
          >
            <ResponsiveContainer width="100%" height={220}>
              <LineChart
                data={chartData}
                margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
              >
                <CartesianGrid
                  stroke="var(--border-secondary)"
                  strokeDasharray="3 3"
                />
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
                  labelStyle={{
                    color: "var(--text-muted)",
                    fontSize: 10,
                    marginBottom: 4,
                  }}
                  formatter={(value) => [Number(value).toFixed(3), "긴장도"]}
                />
                {decisions.map((d) => (
                  <ReferenceLine
                    key={`ref-${d.round}`}
                    x={`R${d.round}`}
                    stroke="#f59e0b"
                    strokeDasharray="4 3"
                    strokeOpacity={0.6}
                    label={{
                      value: `⚡ R${d.round}`,
                      position: "top",
                      fill: "#f59e0b",
                      fontSize: 9,
                    }}
                  />
                ))}
                <Line
                  type="monotone"
                  dataKey="tension"
                  name="긴장도"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3, fill: "#22d3ee" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div
            className="rounded-lg border border-[var(--border-secondary)] p-4 flex flex-col gap-3"
            style={{ background: "var(--bg-tertiary)" }}
          >
            <div
              className="text-[11px] font-semibold uppercase tracking-wider"
              style={{ color: "var(--text-muted)" }}
            >
              최종 상태
            </div>
            <StatRow label="총 라운드" value={String(totalRounds)} />
            <StatRow label="결정 횟수" value={String(decisions.length)} />
            <StatRow label="최종 긴장도" value={finalTension.toFixed(2)} accent />
            <StatRow label="최고 긴장도" value={peakTension.toFixed(2)} />
          </div>

          <div
            className="rounded-lg border border-[var(--border-secondary)] p-4 flex flex-col gap-2"
            style={{ background: "var(--bg-tertiary)" }}
          >
            <div
              className="text-[11px] font-semibold uppercase tracking-wider mb-1"
              style={{ color: "var(--text-muted)" }}
            >
              결정 히스토리
            </div>
            {decisions.length === 0 ? (
              <div
                className="text-xs flex-1 flex items-center justify-center"
                style={{ color: "var(--text-muted)" }}
              >
                결정 기록 없음
              </div>
            ) : (
              <div className="flex flex-col gap-1.5 overflow-y-auto max-h-[140px]">
                {decisions.map((d, i) => (
                  <button
                    key={i}
                    onClick={() => onWhatIf(d.round)}
                    className="flex items-start gap-2 text-[11px] leading-snug text-left bg-transparent border-none p-0 cursor-pointer group"
                    title={`R${d.round}에서 What-If 분기`}
                  >
                    <span
                      className="shrink-0 font-bold tabular-nums"
                      style={{ color: "#f59e0b" }}
                    >
                      R{d.round}
                    </span>
                    <span
                      className="group-hover:text-[var(--accent-cyan)] transition-colors"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {d.label}
                    </span>
                    <span style={{ color: "var(--text-muted)" }}>
                      → {d.outcome}
                    </span>
                    <span className="text-[9px] text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity ml-auto shrink-0">
                      ↗ What-If
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <ActionButton label="전체 리포트 보기" onClick={onViewReport} />
          <ActionButton label="새 시뮬레이션" onClick={onNewSimulation} variant="primary" />
          <ActionButton label="What-If 분기" onClick={() => onWhatIf(lastWhatIfRound)} />
        </div>
      </div>
    </div>
  );
}

function StatRow({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-[11px]">
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span
        className="font-semibold tabular-nums"
        style={{ color: accent ? "var(--accent-cyan)" : "var(--text-primary)" }}
      >
        {value}
      </span>
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  variant,
}: {
  label: string;
  onClick: () => void;
  variant?: "primary";
}) {
  const isPrimary = variant === "primary";
  return (
    <button
      onClick={onClick}
      className="px-4 py-2 rounded-md text-xs font-semibold cursor-pointer transition-colors"
      style={{
        background: isPrimary ? "rgba(34,211,238,0.15)" : "rgba(255,255,255,0.05)",
        border: `1px solid ${isPrimary ? "var(--accent-cyan)" : "var(--border-secondary)"}`,
        color: isPrimary ? "var(--accent-cyan)" : "var(--text-muted)",
      }}
    >
      {label}
    </button>
  );
}
