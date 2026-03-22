"use client";

import type { PollingResult } from "@/hooks/useDataPolling";
import type { OSINTSummary } from "@/hooks/useOSINTSummary";

interface OverviewTabProps {
  summary: OSINTSummary;
  polling: PollingResult;
}

const CATEGORY_ICONS: Record<string, string> = {
  military: "🎯",
  info: "📰",
  infra: "🌐",
  environment: "🌍",
};

export default function OverviewTab({ summary, polling }: OverviewTabProps) {
  const tensionPct = (summary.tensionScore / 10) * 100;
  const tensionColor =
    summary.tensionScore > 7
      ? "#ef4444"
      : summary.tensionScore > 4
        ? "#facc15"
        : "#22c55e";

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <Section title="긴장도">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div
              style={{
                height: 8,
                borderRadius: 4,
                background: "rgba(255,255,255,0.08)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${tensionPct}%`,
                  borderRadius: 4,
                  background: tensionColor,
                  transition: "width 0.3s",
                }}
              />
            </div>
          </div>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: tensionColor,
              fontVariantNumeric: "tabular-nums",
              minWidth: 55,
              textAlign: "right",
            }}
          >
            {summary.tensionScore.toFixed(1)} / 10
          </span>
        </div>
      </Section>

      <Section title="자산 현황">
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <AssetRow icon="🚢" label="군함" count={summary.totalShips} />
          <AssetRow icon="✈️" label="군용기" count={summary.totalFlights} />
          <AssetRow icon="🛸" label="UAV" count={summary.totalUavs} />
          <AssetRow icon="🛰️" label="정찰위성" count={summary.totalSatellites} />
          <AssetRow icon="🏗️" label="군사기지" count={summary.totalBases} />
          {summary.totalGpsJamming > 0 && (
            <AssetRow icon="⚡" label="GPS 재밍" count={summary.totalGpsJamming} />
          )}
        </div>
      </Section>

      {summary.recentEvents.length > 0 && (
        <Section title={`최근 이벤트 (${summary.recentEvents.length}건)`}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {summary.recentEvents.slice(0, 5).map((event, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 8,
                  fontSize: 11,
                  lineHeight: 1.4,
                }}
              >
                <span
                  style={{
                    color: "rgb(107, 114, 128)",
                    fontVariantNumeric: "tabular-nums",
                    flexShrink: 0,
                  }}
                >
                  {event.time}
                </span>
                <span style={{ flexShrink: 0 }}>
                  {CATEGORY_ICONS[event.category] ?? "📡"}
                </span>
                <div style={{ flex: 1, color: "#d1d5db" }}>
                  <span style={{ color: "rgb(107, 114, 128)" }}>
                    {event.source}:
                  </span>{" "}
                  {event.title}
                  {event.detail && (
                    <span style={{ color: "rgb(75, 85, 99)", marginLeft: 4 }}>
                      | {event.detail}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {(polling.stocks as Array<Record<string, unknown>>).length > 0 && (
        <Section title="경제 지표">
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "6px 14px",
              fontSize: 11,
            }}
          >
            {(polling.stocks as Array<Record<string, unknown>>)
              .slice(0, 8)
              .map((stock, i) => {
                const change = Number(stock.change_percent ?? 0);
                const color = change >= 0 ? "#22c55e" : "#ef4444";
                const sign = change >= 0 ? "+" : "";
                return (
                  <span key={i}>
                    <span style={{ color: "#9ca3af" }}>
                      {(stock.symbol as string) ?? (stock.name as string) ?? ""}
                    </span>{" "}
                    <span style={{ color, fontVariantNumeric: "tabular-nums" }}>
                      {sign}
                      {change.toFixed(1)}%
                    </span>
                  </span>
                );
              })}
          </div>
        </Section>
      )}

      <div
        style={{
          fontSize: 10,
          color: "rgb(75, 85, 99)",
          textAlign: "right",
          paddingTop: 4,
        }}
      >
        마지막 갱신: {new Date().toLocaleTimeString("ko-KR", { hour12: false })} UTC
      </div>
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
    <div
      style={{
        background: "rgba(255,255,255,0.03)",
        borderRadius: 6,
        padding: "10px 12px",
        border: "1px solid rgba(255,255,255,0.05)",
      }}
    >
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

function AssetRow({
  icon,
  label,
  count,
}: {
  icon: string;
  label: string;
  count: number;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        fontSize: 12,
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 6, color: "#d1d5db" }}>
        <span>{icon}</span>
        {label}
      </span>
      <span style={{ fontVariantNumeric: "tabular-nums", color: "#f3f4f6", fontWeight: 600 }}>
        {count}
      </span>
    </div>
  );
}
