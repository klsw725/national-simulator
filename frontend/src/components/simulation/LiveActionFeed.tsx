"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
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

function LiveActionFeed({ actions }: Props) {
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
      <div className="h-full border border-[var(--border-secondary)] rounded-md flex items-center justify-center text-[var(--text-muted)] text-xs bg-[var(--bg-secondary)]">
        액션 대기 중...
      </div>
    );
  }

  return (
    <div className="relative h-full border border-[var(--border-secondary)] rounded-md bg-[var(--bg-secondary)] overflow-hidden">
      {!autoScroll && (
        <button
          onClick={scrollToBottom}
          className="absolute right-2.5 bottom-2.5 z-[2] border border-[var(--accent-cyan)] bg-[rgba(34,211,238,0.12)] text-[var(--accent-cyan)] text-[11px] font-semibold rounded px-2 py-1 cursor-pointer"
        >
          최신으로
        </button>
      )}

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto p-2 flex flex-col gap-2"
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

          const prevRound = idx > 0 ? visibleActions[idx - 1].round_num : -1;
          const isNewRound = action.round_num !== prevRound;

          return (
            <div key={`${action.timestamp}-${action.agent_id}-${idx}`}>
              {isNewRound && (
                <div
                  className="flex items-center gap-2"
                  style={{ margin: idx === 0 ? "0 0 6px" : "10px 0 6px" }}
                >
                  <div className="flex-1 h-px bg-[var(--border-secondary)]" />
                  <span className="text-[10px] font-bold text-[var(--accent-cyan)] tracking-wider whitespace-nowrap">
                    ROUND {action.round_num}
                  </span>
                  <div className="flex-1 h-px bg-[var(--border-secondary)]" />
                </div>
              )}
              <div
                className="max-w-[95%] min-w-[65%] rounded-md px-2.5 py-2 bg-[var(--bg-tertiary)]"
                style={{
                  alignSelf: action.agent_id % 2 === 0 ? "flex-start" : "flex-end",
                  border: `1px solid ${meta.color}`,
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs leading-none">{meta.icon}</span>
                  <span className="text-xs font-semibold text-[var(--text-primary)]">
                    {action.agent_name}
                  </span>
                  <span
                    className="ml-auto text-[10px] rounded-full px-1.5 py-px uppercase"
                    style={{
                      color: meta.color,
                      border: `1px solid ${meta.color}`,
                    }}
                  >
                    {actionLabel}
                  </span>
                </div>

                {content && (
                  <div className="text-[11px] text-[var(--text-muted)] leading-[1.45]">
                    {truncate(content, 100)}
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

export default memo(LiveActionFeed);
