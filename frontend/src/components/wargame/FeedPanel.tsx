"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { LiveAction } from "@/types/simulation";
import type { AgentAction } from "@/types/simulation-stream";
import type { DecisionRecord } from "@/types/simulation";
import RoundTimeline from "./RoundTimeline";

export interface SelectedFeedEntity {
  agentId: number;
  agentName: string;
  actionType: string;
  content: string;
  round: number;
  platform: string;
}

interface Props {
  actions: LiveAction[];
  currentRound: number;
  totalRounds: number;
  decisionRounds: number[];
  decisions?: DecisionRecord[];
  v2Actions?: AgentAction[];
  selectedRound: number | null;
  onScrub: (round: number) => void;
  phaseAccent?: string;
  onActionClick?: (entity: SelectedFeedEntity) => void;
}

const ACTION_META: Record<string, { icon: string; color: string }> = {
  CREATE_POST: { icon: "🗣️", color: "var(--accent-cyan)" },
  QUOTE_POST: { icon: "💬", color: "#a78bfa" },
  REPOST: { icon: "🔄", color: "#4ade80" },
  LIKE_POST: { icon: "❤️", color: "#f472b6" },
  DO_NOTHING: { icon: "⏸️", color: "var(--text-muted)" },
  FOLLOW: { icon: "👁️", color: "#f59e0b" },
};

const V2_CATEGORY_COLOR: Record<string, string> = {
  diplomatic: "#60a5fa",
  economic: "#4ade80",
  military: "#ef4444",
  intelligence: "#a78bfa",
  meta: "var(--text-muted)",
};

const V2_CATEGORY_ICON: Record<string, string> = {
  diplomatic: "🗣️",
  economic: "💰",
  military: "⚔️",
  intelligence: "🔍",
  meta: "⏸️",
};

const ACTION_CATEGORY_MAP: Record<string, string> = {
  issue_statement: "diplomatic",
  propose_negotiation: "diplomatic",
  recall_ambassador: "diplomatic",
  strengthen_alliance: "diplomatic",
  condemn_action: "diplomatic",
  request_mediation: "diplomatic",
  sign_agreement: "diplomatic",
  impose_sanction: "economic",
  lift_sanction: "economic",
  restrict_trade: "economic",
  offer_aid: "economic",
  currency_intervention: "economic",
  deploy_forces: "military",
  conduct_exercise: "military",
  mobilize_reserves: "military",
  withdraw_forces: "military",
  establish_no_fly_zone: "military",
  naval_patrol: "military",
  cyber_operation: "military",
  increase_surveillance: "intelligence",
  share_intelligence: "intelligence",
  conduct_recon: "intelligence",
  electronic_warfare: "intelligence",
  do_nothing: "meta",
  internal_focus: "meta",
};

function getV2Category(actionType: string): string {
  return ACTION_CATEGORY_MAP[actionType] ?? "diplomatic";
}

function truncate(text: string, max = 80): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

function FeedPanel({ actions, currentRound, totalRounds, decisionRounds, decisions, v2Actions, selectedRound, onScrub, phaseAccent, onActionClick }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const visibleActions = useMemo(() => {
    if (selectedRound !== null) {
      return actions.filter((a) => a.round_num === selectedRound);
    }
    return actions.slice(-150);
  }, [actions, selectedRound]);

  const visibleV2Actions = useMemo(() => {
    if (!v2Actions) return [];
    if (selectedRound !== null) {
      return v2Actions.filter((a) => (a.round ?? currentRound) === selectedRound);
    }
    return v2Actions.slice(-150);
  }, [currentRound, selectedRound, v2Actions]);

  useEffect(() => {
    if (!autoScroll || !containerRef.current) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [visibleActions, visibleV2Actions, autoScroll]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoScroll(distFromBottom < 24);
  };

  return (
    <div
      className="flex h-[200px] shrink-0 border-t bg-[var(--bg-secondary)] transition-colors duration-500"
      style={{ borderColor: phaseAccent ?? "var(--border-secondary)" }}
    >
      <div className="flex-[7] flex flex-col min-w-0 border-r border-[var(--border-secondary)]">
        <div className="px-3 py-1.5 border-b border-[var(--border-secondary)] flex items-center justify-between">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest">
            에이전트 행동 피드
            {selectedRound !== null && (
              <span className="ml-1.5 text-[var(--accent-cyan)] normal-case tracking-normal">
                · R{selectedRound}
              </span>
            )}
          </span>
          {selectedRound !== null && (
            <button
              onClick={() => onScrub(0)}
              className="text-[10px] font-semibold text-[var(--accent-cyan)] bg-[rgba(34,211,238,0.12)] border border-[var(--accent-cyan)] rounded px-1.5 py-0.5 cursor-pointer"
            >
              전체 보기
            </button>
          )}
          {selectedRound === null && !autoScroll && (
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
          {(v2Actions ? visibleV2Actions.length === 0 : visibleActions.length === 0) && (
            <div className="flex-1 flex items-center justify-center text-[var(--text-muted)] text-xs">
              피드 대기 중…
            </div>
          )}
          {v2Actions
            ? visibleV2Actions.map((action, idx) => {
                const category = getV2Category(action.action_type);
                const color = V2_CATEGORY_COLOR[category] ?? "var(--text-muted)";
                const content = `${action.target} · ${action.reasoning}`;
                const currentActionRound = action.round ?? currentRound;
                const prevRound = idx > 0 ? (visibleV2Actions[idx - 1].round ?? currentRound) : -1;
                const isNewRound = currentActionRound !== prevRound;

                return (
                  <div key={`${action.actor}-${action.action_type}-${idx}`}>
                    {isNewRound && (
                      <div className="flex items-center gap-2 my-1">
                        <div className="flex-1 h-px bg-[var(--border-secondary)]" />
                        <span className="text-[9px] font-bold text-[var(--accent-cyan)] tracking-wider">
                          R{currentActionRound}
                        </span>
                        <div className="flex-1 h-px bg-[var(--border-secondary)]" />
                      </div>
                    )}
                    <div
                      className="flex items-start gap-1.5 py-0.5 cursor-pointer rounded px-0.5 transition-colors hover:bg-[rgba(34,211,238,0.06)]"
                      onClick={() => onActionClick?.({
                        agentId: idx,
                        agentName: action.actor,
                        actionType: action.action_type,
                        content,
                        round: currentActionRound,
                        platform: "wargame_v2",
                      })}
                    >
                      <span className="text-xs leading-none mt-px shrink-0">{V2_CATEGORY_ICON[category] ?? "•"}</span>
                      <span className="text-[10px] font-semibold shrink-0" style={{ color }}>
                        {action.actor}
                      </span>
                      <span className="text-[10px] font-medium shrink-0" style={{ color, opacity: 0.7 }}>
                        {action.action_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-[10px] leading-snug truncate text-[var(--text-muted)]">
                        → {action.target} · {truncate(action.reasoning ?? "", 60)}
                      </span>
                    </div>
                  </div>
                );
              })
            : visibleActions.map((action, idx) => {
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
                    <div
                      className="flex items-start gap-1.5 py-0.5 cursor-pointer rounded px-0.5 transition-colors hover:bg-[rgba(34,211,238,0.06)]"
                      onClick={() => onActionClick?.({
                        agentId: action.agent_id,
                        agentName: action.agent_name,
                        actionType: action.action_type,
                        content,
                        round: action.round_num,
                        platform: action.platform,
                      })}
                    >
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
            decisions={decisions}
            selectedRound={selectedRound}
            onScrub={onScrub}
          />
        </div>
      </div>
    </div>
  );
}

export default memo(FeedPanel);
