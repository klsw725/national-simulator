"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { LiveAction } from "@/types/simulation";

interface Props {
  actions: LiveAction[];
}

const ACTION_META: Record<string, { icon: string; color: string }> = {
  CREATE_POST: { icon: "🗣️", color: "var(--accent-cyan)" },
  QUOTE_POST: { icon: "💬", color: "#a78bfa" },
  REPOST: { icon: "🔄", color: "#4ade80" },
  LIKE_POST: { icon: "❤️", color: "#f472b6" },
  DO_NOTHING: { icon: "⏸️", color: "var(--text-muted)" },
  FOLLOW: { icon: "👁️", color: "#f59e0b" },
};

function truncate(text: string, max = 100): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}...`;
}

export default function LiveActionFeed({ actions }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const visibleActions = useMemo(() => actions.slice(-200), [actions]);

  useEffect(() => {
    if (!autoScroll || !containerRef.current) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [visibleActions, autoScroll]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoScroll(distanceFromBottom < 24);
  };

  const scrollToBottom = () => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    el.scrollTop = el.scrollHeight;
    setAutoScroll(true);
  };

  if (!visibleActions.length) {
    return (
      <div
        style={{
          height: "100%",
          border: "1px solid var(--border-secondary)",
          borderRadius: 6,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-muted)",
          fontSize: 12,
          background: "var(--bg-secondary)",
        }}
      >
        액션 대기 중...
      </div>
    );
  }

  return (
    <div
      style={{
        position: "relative",
        height: "100%",
        border: "1px solid var(--border-secondary)",
        borderRadius: 6,
        background: "var(--bg-secondary)",
        overflow: "hidden",
      }}
    >
      {!autoScroll && (
        <button
          onClick={scrollToBottom}
          style={{
            position: "absolute",
            right: 10,
            bottom: 10,
            zIndex: 2,
            border: "1px solid var(--accent-cyan)",
            background: "rgba(34, 211, 238, 0.12)",
            color: "var(--accent-cyan)",
            fontSize: 11,
            fontWeight: 600,
            borderRadius: 4,
            padding: "4px 8px",
            cursor: "pointer",
          }}
        >
          최신으로
        </button>
      )}

      <div
        ref={containerRef}
        onScroll={handleScroll}
        style={{
          height: "100%",
          overflowY: "auto",
          padding: 8,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        {visibleActions.map((action, idx) => {
          const meta = ACTION_META[action.action_type] ?? {
            icon: "•",
            color: "var(--text-muted)",
          };
          const content = typeof action.action_args?.content === "string" ? action.action_args.content : "";
          const actionLabel = (
            action as LiveAction & { geopolitics_label?: string }
          ).geopolitics_label ?? action.action_type.replace(/_/g, " ");

          return (
            <div
              key={`${action.timestamp}-${action.agent_id}-${idx}`}
              style={{
                alignSelf: action.agent_id % 2 === 0 ? "flex-start" : "flex-end",
                maxWidth: "95%",
                minWidth: "65%",
                border: `1px solid ${meta.color}`,
                borderRadius: 6,
                padding: "8px 10px",
                background: "var(--bg-tertiary)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 12, lineHeight: 1 }}>{meta.icon}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                  {action.agent_name}
                </span>
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 10,
                    color: meta.color,
                    border: `1px solid ${meta.color}`,
                    borderRadius: 999,
                    padding: "1px 6px",
                    textTransform: "uppercase",
                  }}
                >
                  {actionLabel}
                </span>
              </div>

              {content && (
                <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.45 }}>
                  {truncate(content, 100)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
