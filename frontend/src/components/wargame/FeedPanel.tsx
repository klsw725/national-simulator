"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { LiveAction } from "@/types/simulation";
import RoundTimeline from "./RoundTimeline";

interface Props {
  actions: LiveAction[];
  currentRound: number;
  totalRounds: number;
  decisionRounds: number[];
  selectedRound: number | null;
  onScrub: (round: number) => void;
}

const ACTION_META: Record<string, { icon: string; color: string }> = {
  CREATE_POST: { icon: "🗣️", color: "var(--accent-cyan)" },
  QUOTE_POST: { icon: "💬", color: "#a78bfa" },
  REPOST: { icon: "🔄", color: "#4ade80" },
  LIKE_POST: { icon: "❤️", color: "#f472b6" },
  DO_NOTHING: { icon: "⏸️", color: "var(--text-muted)" },
  FOLLOW: { icon: "👁️", color: "#f59e0b" },
};

function truncate(text: string, max = 80): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

function FeedPanel({ actions, currentRound, totalRounds, decisionRounds, selectedRound, onScrub }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const visibleActions = useMemo(() => actions.slice(-150), [actions]);

  useEffect(() => {
    if (!autoScroll || !containerRef.current) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [visibleActions, autoScroll]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoScroll(distFromBottom < 24);
  };

  return (
    <div className="flex h-[200px] shrink-0 border-t border-[var(--border-secondary)] bg-[var(--bg-secondary)]">
      <div className="flex-[7] flex flex-col min-w-0 border-r border-[var(--border-secondary)]">
        <div className="px-3 py-1.5 border-b border-[var(--border-secondary)] flex items-center justify-between">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest">
            소셜 미디어 피드
          </span>
          {!autoScroll && (
            <button
              onClick={() => {
                if (containerRef.current) {
                  containerRef.current.scrollTop = containerRef.current.scrollHeight;
                  setAutoScroll(true);
                }
              }}
              className="text-[10px] font-semibold text-[var(--accent-cyan)] bg-[rgba(34,211,238,0.12)] border border-[var(--accent-cyan)] rounded px-1.5 py-0.5 cursor-pointer"
            >
              최신으로 ↓
            </button>
          )}
        </div>

        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto px-2.5 py-1.5 flex flex-col gap-1"
        >
          {visibleActions.length === 0 && (
            <div className="flex-1 flex items-center justify-center text-[var(--text-muted)] text-xs">
              피드 대기 중…
            </div>
          )}
          {visibleActions.map((action, idx) => {
            const meta = ACTION_META[action.action_type] ?? { icon: "•", color: "var(--text-muted)" };
            const content = typeof action.action_args?.content === "string" ? action.action_args.content : "";
            const prevRound = idx > 0 ? visibleActions[idx - 1].round_num : -1;
            const isNewRound = action.round_num !== prevRound;

            return (
              <div key={`${action.timestamp}-${action.agent_id}-${idx}`}>
                {isNewRound && (
                  <div className="flex items-center gap-2 my-1">
                    <div className="flex-1 h-px bg-[var(--border-secondary)]" />
                    <span className="text-[9px] font-bold text-[var(--accent-cyan)] tracking-wider">
                      R{action.round_num}
                    </span>
                    <div className="flex-1 h-px bg-[var(--border-secondary)]" />
                  </div>
                )}
                <div className="flex items-start gap-1.5 py-0.5">
                  <span className="text-xs leading-none mt-px shrink-0">{meta.icon}</span>
                  <span className="text-[10px] font-semibold text-[var(--text-primary)] shrink-0">
                    {action.agent_name}
                  </span>
                  {content && (
                    <span className="text-[10px] text-[var(--text-muted)] leading-snug truncate">
                      {truncate(content)}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex-[3] flex flex-col min-w-0">
        <div className="px-3 py-1.5 border-b border-[var(--border-secondary)]">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest">
            타임라인
          </span>
        </div>
        <div className="flex-1 flex items-center min-w-0">
          <RoundTimeline
            currentRound={currentRound}
            totalRounds={totalRounds}
            decisionRounds={decisionRounds}
            selectedRound={selectedRound}
            onScrub={onScrub}
          />
        </div>
      </div>
    </div>
  );
}

export default memo(FeedPanel);
