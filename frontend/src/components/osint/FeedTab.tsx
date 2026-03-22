"use client";

import { useMemo, useState } from "react";
import type { PollingResult } from "@/hooks/useDataPolling";
import type { OSINTSummary, RecentEvent } from "@/hooks/useOSINTSummary";

type FilterId = "all" | "military" | "info" | "infra" | "environment";

const FILTERS: { id: FilterId; label: string }[] = [
  { id: "all", label: "전체" },
  { id: "military", label: "군사" },
  { id: "info", label: "정보" },
  { id: "infra", label: "인프라" },
  { id: "environment", label: "환경" },
];

const SOURCE_ICONS: Record<string, string> = {
  GDELT: "📰",
  News: "📰",
  "GPS 재밍": "📡",
  지진: "🌍",
  인터넷: "🌐",
  FIRMS: "🔥",
  KiwiSDR: "📡",
  추적: "✈️",
};

interface FeedTabProps {
  summary: OSINTSummary;
  polling: PollingResult;
  onFlyTo?: (lng: number, lat: number) => void;
}

export default function FeedTab({ summary, polling, onFlyTo }: FeedTabProps) {
  const [filter, setFilter] = useState<FilterId>("all");

  const allEvents = useMemo(() => {
    const events: RecentEvent[] = [...summary.recentEvents];

    for (const fire of polling.firmsFires.slice(0, 5)) {
      events.push({
        time: new Date().toISOString().slice(11, 16),
        source: "FIRMS",
        category: "environment",
        title: `FRP ${fire.frp}MW 감지`,
        lat: fire.lat,
        lng: fire.lng,
      });
    }

    for (const tf of polling.trackedFlights.slice(0, 3)) {
      events.push({
        time: new Date().toISOString().slice(11, 16),
        source: "추적",
        category: "military",
        title: `${tf.callsign} — ${tf.country}`,
        lat: tf.lat,
        lng: tf.lng,
      });
    }

    events.sort((a, b) => b.time.localeCompare(a.time));
    return events;
  }, [summary.recentEvents, polling.firmsFires, polling.trackedFlights]);

  const filtered =
    filter === "all" ? allEvents : allEvents.filter((e) => e.category === filter);

  return (
    <div style={{ padding: "12px 16px" }}>
      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              padding: "4px 10px",
              borderRadius: 12,
              fontSize: 11,
              border:
                filter === f.id
                  ? "1px solid var(--accent-cyan)"
                  : "1px solid rgb(55, 65, 81)",
              background:
                filter === f.id ? "rgba(34, 211, 238, 0.1)" : "transparent",
              color: filter === f.id ? "#22d3ee" : "rgb(156, 163, 175)",
              cursor: "pointer",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {filtered.length === 0 && (
          <div style={{ fontSize: 12, color: "rgb(75, 85, 99)", textAlign: "center", padding: 24 }}>
            해당 카테고리의 이벤트가 없습니다
          </div>
        )}
        {filtered.map((event, i) => (
          <div
            key={i}
            onClick={() => {
              if (event.lat != null && event.lng != null) {
                onFlyTo?.(event.lng, event.lat);
              }
            }}
            style={{
              padding: "8px 10px",
              background: "rgba(255,255,255,0.03)",
              borderRadius: 6,
              border: "1px solid rgba(255,255,255,0.05)",
              cursor: event.lat != null ? "pointer" : "default",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <span
                style={{
                  fontSize: 10,
                  color: "rgb(107, 114, 128)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {event.time}
              </span>
              <span style={{ fontSize: 12 }}>
                {SOURCE_ICONS[event.source] ?? "📡"}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#9ca3af",
                }}
              >
                {event.source}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "#d1d5db", lineHeight: 1.4 }}>
              {event.title}
            </div>
            {event.detail && (
              <div style={{ fontSize: 10, color: "rgb(75, 85, 99)", marginTop: 2 }}>
                {event.detail}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
