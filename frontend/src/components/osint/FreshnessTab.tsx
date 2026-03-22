"use client";

import type { PollingResult } from "@/hooks/useDataPolling";

interface FreshnessTabProps {
  polling: PollingResult;
}

interface SourceEntry {
  key: string;
  label: string;
  count: number | string;
  group: "fast" | "slow";
}

function getSourceEntries(polling: PollingResult): SourceEntry[] {
  return [
    { key: "ships", label: "ships", count: polling.ships.length, group: "fast" },
    { key: "military_flights", label: "mil_flights", count: polling.militaryFlights.length, group: "fast" },
    { key: "uavs", label: "uavs", count: polling.uavs.length, group: "fast" },
    { key: "tracked_flights", label: "tracked", count: polling.trackedFlights.length, group: "fast" },
    { key: "satellites", label: "satellites", count: polling.satellites.length, group: "fast" },
    { key: "cctv", label: "cctv", count: polling.cctv.length, group: "fast" },
    { key: "gps_jamming", label: "gps_jamming", count: polling.gpsJamming.length, group: "fast" },
    { key: "liveuamap", label: "liveuamap", count: (polling.liveuamap as unknown[]).length, group: "fast" },
    { key: "gdelt", label: "gdelt", count: (polling.gdelt as unknown[]).length, group: "slow" },
    { key: "news", label: "news", count: (polling.news as unknown[]).length, group: "slow" },
    { key: "military_bases", label: "mil_bases", count: polling.militaryBases.length, group: "slow" },
    { key: "earthquakes", label: "earthquakes", count: polling.earthquakes.length, group: "slow" },
    { key: "firms_fires", label: "fires", count: polling.firmsFires.length, group: "slow" },
    { key: "internet_outages", label: "outages", count: polling.internetOutages.length, group: "slow" },
    { key: "kiwisdr", label: "kiwisdr", count: polling.kiwisdr.length, group: "slow" },
    { key: "stocks", label: "stocks", count: (polling.stocks as unknown[]).length, group: "slow" },
    { key: "power_plants", label: "power_plants", count: polling.powerPlants.length, group: "slow" },
    { key: "datacenters", label: "datacenters", count: polling.datacenters.length, group: "slow" },
    {
      key: "space_weather",
      label: "space_wx",
      count: polling.spaceWeather?.kp_text ?? "—",
      group: "slow",
    },
    { key: "frontlines", label: "frontlines", count: polling.frontlines ? "✓" : "—", group: "slow" },
  ];
}

function getElapsedText(isoStr: string | undefined): string {
  if (!isoStr) return "—";
  const diff = Date.now() - new Date(isoStr).getTime();
  if (diff < 0) return "0s ago";
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ago`;
}

function getStatusColor(
  isoStr: string | undefined,
  thresholdMs: number
): string {
  if (!isoStr) return "#ef4444";
  const diff = Date.now() - new Date(isoStr).getTime();
  if (diff <= thresholdMs) return "#22c55e";
  if (diff <= thresholdMs * 2) return "#facc15";
  return "#ef4444";
}

export default function FreshnessTab({ polling }: FreshnessTabProps) {
  const entries = getSourceEntries(polling);
  const fastEntries = entries.filter((e) => e.group === "fast");
  const slowEntries = entries.filter((e) => e.group === "slow");

  const FAST_THRESHOLD = 30_000;
  const SLOW_THRESHOLD = 240_000;

  return (
    <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
      <GroupSection
        title="빠른 갱신 (15초)"
        entries={fastEntries}
        freshness={polling.freshness}
        thresholdMs={FAST_THRESHOLD}
      />
      <GroupSection
        title="느린 갱신 (2분)"
        entries={slowEntries}
        freshness={polling.freshness}
        thresholdMs={SLOW_THRESHOLD}
      />

      <div style={{ fontSize: 10, color: "rgb(75, 85, 99)", paddingTop: 8 }}>
        <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "#22c55e", marginRight: 4, verticalAlign: "middle" }} />
        정상 (&lt; 2배 주기){" "}
        <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "#facc15", marginRight: 4, marginLeft: 8, verticalAlign: "middle" }} />
        지연 (&gt; 2배 주기){" "}
        <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "#ef4444", marginRight: 4, marginLeft: 8, verticalAlign: "middle" }} />
        오류/미수신
      </div>
    </div>
  );
}

function GroupSection({
  title,
  entries,
  freshness,
  thresholdMs,
}: {
  title: string;
  entries: SourceEntry[];
  freshness: Record<string, string>;
  thresholdMs: number;
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
          marginBottom: 6,
          borderBottom: "1px solid rgba(255,255,255,0.05)",
          paddingBottom: 4,
        }}
      >
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {entries.map((entry) => {
          const ts = freshness[entry.key];
          const color = getStatusColor(ts, thresholdMs);
          const elapsed = getElapsedText(ts);

          return (
            <div
              key={entry.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 11,
                fontFamily: "monospace",
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: color,
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  color: "#d1d5db",
                  width: 110,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {entry.label}
              </span>
              <span
                style={{
                  color: "rgb(107, 114, 128)",
                  width: 70,
                  textAlign: "right",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {elapsed}
              </span>
              <span
                style={{
                  color: "rgb(107, 114, 128)",
                  width: 50,
                  textAlign: "right",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {entry.count}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
