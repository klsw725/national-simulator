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

interface Props {
  scenarioId: string;
}

export default function GeopoliticsView({ scenarioId }: Props) {
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
          {summary.actors.map((actor) => (
            <span
              key={actor}
              style={{
                padding: "3px 10px",
                fontSize: 11,
                borderRadius: 12,
                border: "1px solid var(--accent-cyan)",
                background: "rgba(34,211,238,0.08)",
                color: "var(--accent-cyan)",
                whiteSpace: "nowrap",
              }}
            >
              {actor}
              {actorActionCounts[actor] != null && (
                <span style={{ marginLeft: 4, opacity: 0.6 }}>
                  {actorActionCounts[actor]}
                </span>
              )}
            </span>
          ))}
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

                return (
                  <div
                    key={i}
                    style={{
                      padding: "6px 8px",
                      background: "var(--bg-primary)",
                      borderRadius: 4,
                      borderLeft: `3px solid ${color}`,
                    }}
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
