"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { useAnalytics } from "@/hooks/useAnalytics";
import AnomalyList from "./AnomalyList";

const AssetTrendChart = dynamic(
  () => import("@/components/charts/AssetTrendChart"),
  { ssr: false },
);

const PERIODS = [
  { label: "24h", hours: 24 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
];

const SOURCE_OPTIONS = [
  { value: "ships", label: "선박", color: "#22d3ee" },
  { value: "military_flights", label: "군용기", color: "#f97316" },
  { value: "uavs", label: "UAV", color: "#eab308" },
  { value: "satellites", label: "위성", color: "#a855f7" },
  { value: "military_bases", label: "기지", color: "#ef4444" },
];

export default function TrendTab() {
  const [periodIdx, setPeriodIdx] = useState(0);
  const [sourceType, setSourceType] = useState("ships");
  const period = PERIODS[periodIdx];
  const sourceColor =
    SOURCE_OPTIONS.find((s) => s.value === sourceType)?.color ?? "#22d3ee";

  const { trend, anomalies, loading } = useAnalytics({
    sourceType,
    hours: period.hours,
  });

  return (
    <div
      style={{
        padding: "12px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      <div style={{ display: "flex", gap: 4 }}>
        {PERIODS.map((p, i) => (
          <button
            key={p.label}
            onClick={() => setPeriodIdx(i)}
            style={{
              padding: "4px 12px",
              borderRadius: 12,
              fontSize: 11,
              border:
                periodIdx === i
                  ? "1px solid var(--accent-cyan)"
                  : "1px solid rgb(55, 65, 81)",
              background:
                periodIdx === i ? "rgba(34, 211, 238, 0.1)" : "transparent",
              color: periodIdx === i ? "#22d3ee" : "rgb(156, 163, 175)",
              cursor: "pointer",
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {SOURCE_OPTIONS.map((s) => (
          <button
            key={s.value}
            onClick={() => setSourceType(s.value)}
            style={{
              padding: "3px 8px",
              borderRadius: 4,
              fontSize: 10,
              border:
                sourceType === s.value
                  ? `1px solid ${s.color}`
                  : "1px solid rgb(55, 65, 81)",
              background:
                sourceType === s.value ? `${s.color}15` : "transparent",
              color:
                sourceType === s.value ? s.color : "rgb(107, 114, 128)",
              cursor: "pointer",
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      <Section title={`자산 추이 (${period.label})`}>
        {loading ? (
          <div
            style={{
              fontSize: 12,
              color: "rgb(75, 85, 99)",
              textAlign: "center",
              padding: 24,
            }}
          >
            불러오는 중...
          </div>
        ) : trend && trend.data_points.length > 0 ? (
          <>
            <AssetTrendChart
              data={trend.data_points}
              color={sourceColor}
              height={180}
            />
            <div
              style={{
                display: "flex",
                gap: 16,
                fontSize: 10,
                color: "rgb(107, 114, 128)",
                marginTop: 6,
              }}
            >
              <span>최소: {trend.summary.min}</span>
              <span>최대: {trend.summary.max}</span>
              <span>평균: {trend.summary.avg}</span>
              <span
                style={{
                  color:
                    trend.summary.trend === "increasing"
                      ? "#22c55e"
                      : trend.summary.trend === "decreasing"
                        ? "#ef4444"
                        : "rgb(107, 114, 128)",
                }}
              >
                {trend.summary.trend === "increasing"
                  ? "▲ 증가"
                  : trend.summary.trend === "decreasing"
                    ? "▼ 감소"
                    : "━ 안정"}
              </span>
            </div>
          </>
        ) : (
          <div
            style={{
              fontSize: 12,
              color: "rgb(75, 85, 99)",
              textAlign: "center",
              padding: 24,
            }}
          >
            데이터 없음
          </div>
        )}
      </Section>

      <Section title="이상 탐지">
        {anomalies ? (
          <AnomalyList anomalies={anomalies.anomalies} />
        ) : (
          <div
            style={{
              fontSize: 12,
              color: "rgb(75, 85, 99)",
              textAlign: "center",
              padding: 16,
            }}
          >
            불러오는 중...
          </div>
        )}
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          color: "rgb(107, 114, 128)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 8,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}
