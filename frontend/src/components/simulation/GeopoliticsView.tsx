"use client";

import { useEffect, useMemo, useState } from "react";
import { getGeopoliticsSummary, getGeopoliticsTimeline } from "@/lib/gatewayApi";

const ACTION_COLORS: Record<string, string> = {
  military_movement: "#ef4444",
  military_exercise: "#f59e0b",
  diplomatic_statement: "#22d3ee",
  sanction_impose: "#f472b6",
  trade_restriction: "#a78bfa",
  treaty_sign: "#34d399",
  do_nothing: "#6b7280",
};

interface GeopoliticsSummary {
  scenario_id: string;
  total_events: number;
  total_rounds: number;
  actors: string[];
}

interface GeopoliticsEvent {
  action_type: string;
  actor_id: string;
  target_actor_ids: string[];
  content: string;
  magnitude: number;
}

interface TimelineRound {
  round: number;
  events: GeopoliticsEvent[];
}

const ACTOR_LOCATIONS: Record<string, { lat: number; lng: number }> = {
  "United States": { lat: 38.9072, lng: -77.0369 },
  "US": { lat: 38.9072, lng: -77.0369 },
  "China": { lat: 39.9042, lng: 116.4074 },
  "CN": { lat: 39.9042, lng: 116.4074 },
  "Japan": { lat: 35.6762, lng: 139.6503 },
  "JP": { lat: 35.6762, lng: 139.6503 },
  "South Korea": { lat: 37.5665, lng: 126.978 },
  "KR": { lat: 37.5665, lng: 126.978 },
  "North Korea": { lat: 39.0392, lng: 125.7625 },
  "Philippines": { lat: 14.5995, lng: 120.9842 },
  "PH": { lat: 14.5995, lng: 120.9842 },
  "Taiwan": { lat: 25.033, lng: 121.5654 },
  "TW": { lat: 25.033, lng: 121.5654 },
  "Russia": { lat: 55.7558, lng: 37.6173 },
  "RU": { lat: 55.7558, lng: 37.6173 },
  "Australia": { lat: -35.2809, lng: 149.13 },
  "AU": { lat: -35.2809, lng: 149.13 },
  "India": { lat: 28.6139, lng: 77.209 },
  "IN": { lat: 28.6139, lng: 77.209 },
  "United Kingdom": { lat: 51.5074, lng: -0.1278 },
  "UK": { lat: 51.5074, lng: -0.1278 },
  "France": { lat: 48.8566, lng: 2.3522 },
  "FR": { lat: 48.8566, lng: 2.3522 },
  "Germany": { lat: 52.52, lng: 13.405 },
  "Indonesia": { lat: -6.2088, lng: 106.8456 },
  "Vietnam": { lat: 21.0278, lng: 105.8342 },
  "Malaysia": { lat: 3.139, lng: 101.6869 },
  "Singapore": { lat: 1.3521, lng: 103.8198 },
  "Thailand": { lat: 13.7563, lng: 100.5018 },
  "Canada": { lat: 45.4215, lng: -75.6972 },
  "NATO": { lat: 50.8503, lng: 4.3517 },
  "ASEAN": { lat: -6.2088, lng: 106.8456 },
  "United Nations": { lat: 40.7489, lng: -73.968 },
  "QUAD": { lat: 35.6762, lng: 139.6503 },
  "European Union": { lat: 50.8503, lng: 4.3517 },
};

interface Props {
  scenarioId: string;
  onFlyTo?: (lng: number, lat: number) => void;
}

export default function GeopoliticsView({ scenarioId, onFlyTo }: Props) {
  const [summary, setSummary] = useState<GeopoliticsSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelineRound[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    Promise.all([
      getGeopoliticsSummary(scenarioId),
      getGeopoliticsTimeline(scenarioId),
    ])
      .then(([sum, tl]) => {
        if (cancelled) return;
        setSummary(sum);
        setTimeline(tl.timeline ?? []);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setError(true);
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, [scenarioId]);

  const actorActionCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const round of timeline) {
      for (const ev of round.events) {
        counts[ev.actor_id] = (counts[ev.actor_id] ?? 0) + 1;
      }
    }
    return counts;
  }, [timeline]);

  if (loading) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12 }}>
        지정학 데이터 로딩 중...
      </div>
    );
  }

  if (error || (!summary && timeline.length === 0)) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12 }}>
        (지정학 분석 데이터 없음)
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {summary && (
        <div
          style={{
            display: "flex",
            gap: 8,
          }}
        >
          {[
            { label: "이벤트", value: summary.total_events },
            { label: "라운드", value: summary.total_rounds },
            { label: "행위자", value: summary.actors.length },
          ].map((stat) => (
            <div
              key={stat.label}
              style={{
                flex: 1,
                padding: "8px 10px",
                background: "var(--bg-primary)",
                borderRadius: 4,
                border: "1px solid var(--border-secondary)",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 700, color: "var(--accent-cyan)", fontFamily: "monospace" }}>
                {stat.value}
              </div>
              <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {summary && summary.actors.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {summary.actors.map((actor) => {
            const actorLoc = ACTOR_LOCATIONS[actor];
            const actorClickable = !!actorLoc && !!onFlyTo;
            return (
            <span
              key={actor}
              onClick={actorClickable ? () => onFlyTo!(actorLoc.lng, actorLoc.lat) : undefined}
              style={{
                padding: "3px 10px",
                fontSize: 11,
                borderRadius: 12,
                border: "1px solid var(--accent-cyan)",
                background: "rgba(34,211,238,0.08)",
                color: "var(--accent-cyan)",
                whiteSpace: "nowrap",
                cursor: actorClickable ? "pointer" : "default",
              }}
            >
              {actor}
              {actorActionCounts[actor] != null && (
                <span style={{ marginLeft: 4, opacity: 0.6 }}>
                  {actorActionCounts[actor]}
                </span>
              )}
            </span>
            );
          })}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {timeline.map((round) => (
          <div key={round.round}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--text-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 6,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ color: "var(--accent-cyan)", fontFamily: "monospace", fontWeight: 700, fontSize: 12 }}>
                R{round.round}
              </span>
              <span style={{ flex: 1, height: 1, background: "var(--border-secondary)" }} />
              <span style={{ fontSize: 10, fontWeight: 400 }}>
                {round.events.length}건
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {round.events.map((ev, i) => {
                const color = ACTION_COLORS[ev.action_type] ?? "#6b7280";
                const actionLabel = ev.action_type.replace(/_/g, " ");
                const magnitudePct = Math.min(Math.max(ev.magnitude * 100, 0), 100);

                const loc = ACTOR_LOCATIONS[ev.actor_id];
                const clickable = !!loc && !!onFlyTo;

                return (
                  <div
                    key={i}
                    onClick={clickable ? () => onFlyTo!(loc.lng, loc.lat) : undefined}
                    style={{
                      padding: "6px 8px",
                      background: "var(--bg-primary)",
                      borderRadius: 4,
                      borderLeft: `3px solid ${color}`,
                      cursor: clickable ? "pointer" : "default",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={clickable ? (e) => { (e.currentTarget as HTMLElement).style.background = "var(--bg-tertiary)"; } : undefined}
                    onMouseLeave={clickable ? (e) => { (e.currentTarget as HTMLElement).style.background = "var(--bg-primary)"; } : undefined}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 2 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-primary)" }}>
                        {ev.actor_id}
                      </span>
                      <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
                        →
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 500,
                          color,
                          textTransform: "uppercase",
                        }}
                      >
                        {actionLabel}
                      </span>
                      {ev.target_actor_ids.length > 0 && (
                        <>
                          <span style={{ fontSize: 10, color: "var(--text-muted)" }}>→</span>
                          <span style={{ fontSize: 10, color: "var(--text-primary)" }}>
                            {ev.target_actor_ids.join(", ")}
                          </span>
                        </>
                      )}
                    </div>

                    {ev.content && (
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--text-muted)",
                          lineHeight: 1.4,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          marginBottom: 4,
                        }}
                      >
                        {ev.content}
                      </div>
                    )}

                    <div
                      style={{
                        height: 3,
                        background: "var(--border-secondary)",
                        borderRadius: 2,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${magnitudePct}%`,
                          height: "100%",
                          background: color,
                          borderRadius: 2,
                          transition: "width 0.3s ease",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
