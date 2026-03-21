"use client";

import { useMemo, useState } from "react";
import {
  MessageSquare,
  Quote,
  Repeat,
  Heart,
  UserPlus,
  Minus,
} from "lucide-react";
import type { SimulationAction } from "@/types/simulation";

const ACTION_ICONS: Record<string, typeof MessageSquare> = {
  CREATE_POST: MessageSquare,
  QUOTE_POST: Quote,
  REPOST: Repeat,
  LIKE: Heart,
  FOLLOW: UserPlus,
  DO_NOTHING: Minus,
};

const ACTION_COLORS: Record<string, string> = {
  CREATE_POST: "var(--accent-cyan)",
  QUOTE_POST: "#a78bfa",
  REPOST: "var(--accent-yellow)",
  LIKE: "#f472b6",
  FOLLOW: "var(--status-connected)",
  DO_NOTHING: "var(--text-muted)",
};

interface Props {
  actions: SimulationAction[];
}

export default function SimulationTimeline({ actions }: Props) {
  const rounds = useMemo(() => {
    const map = new Map<number, SimulationAction[]>();
    for (const a of actions) {
      const list = map.get(a.round_num) ?? [];
      list.push(a);
      map.set(a.round_num, list);
    }
    return map;
  }, [actions]);

  const roundNums = useMemo(
    () => Array.from(rounds.keys()).sort((a, b) => a - b),
    [rounds]
  );

  const [selectedRound, setSelectedRound] = useState(0);

  const currentRound = roundNums[selectedRound] ?? roundNums[0];
  const currentActions = rounds.get(currentRound) ?? [];

  if (!actions.length) {
    return (
      <div
        style={{
          padding: 24,
          textAlign: "center",
          color: "var(--text-muted)",
          fontSize: 13,
        }}
      >
        시뮬레이션 결과가 없습니다
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Round slider */}
      <div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 6,
          }}
        >
          <span
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            라운드
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--accent-cyan)",
              fontFamily: "monospace",
            }}
          >
            {currentRound} / {roundNums[roundNums.length - 1]}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={roundNums.length - 1}
          value={selectedRound}
          onChange={(e) => setSelectedRound(Number(e.target.value))}
          style={{
            width: "100%",
            accentColor: "var(--accent-cyan)",
            cursor: "pointer",
          }}
        />
      </div>

      {/* Actions list */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
          maxHeight: 320,
          overflow: "auto",
        }}
      >
        {currentActions.map((action, i) => {
          const Icon = ACTION_ICONS[action.action_type] ?? Minus;
          const color = ACTION_COLORS[action.action_type] ?? "var(--text-muted)";
          const content = action.action_args?.content ?? "";
          const actionLabel = action.geopolitics_label ?? action.action_type.replace(/_/g, " ");

          return (
            <div
              key={i}
              style={{
                padding: "8px 10px",
                background: "var(--bg-tertiary)",
                borderRadius: 4,
                borderLeft: `3px solid ${color}`,
                display: "flex",
                gap: 8,
                alignItems: "flex-start",
              }}
            >
              <Icon
                size={14}
                color={color}
                style={{ marginTop: 2, flexShrink: 0 }}
              />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--text-primary)",
                    marginBottom: 2,
                  }}
                >
                  {action.agent_name}
                  <span
                    style={{
                      marginLeft: 6,
                      fontSize: 10,
                      fontWeight: 400,
                      color,
                      textTransform: "uppercase",
                    }}
                  >
                    {actionLabel}
                  </span>
                </div>
                {content && (
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
                    }}
                  >
                    {content}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
