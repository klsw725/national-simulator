"use client";

import { memo } from "react";
import {
  FileText,
  Network,
  GitBranch,
  Settings,
  Play,
  FileCheck,
  Check,
  X,
  Loader2,
  Pause,
  Eye,
} from "lucide-react";
import type { PipelineStatus } from "@/types/simulation";

const STEPS = [
  { label: "시드 문서 생성", Icon: FileText },
  { label: "온톨로지 생성", Icon: Network },
  { label: "그래프 빌드", Icon: GitBranch },
  { label: "시뮬레이션 준비", Icon: Settings },
  { label: "시뮬레이션 실행", Icon: Play },
  { label: "보고서 생성", Icon: FileCheck },
] as const;

/**
 * Map API status string → which step index is currently running.
 * Returns -1 if no step is actively running (e.g. "created").
 */
function activeStepIndex(status: string): number {
  switch (status) {
    case "starting":
    case "generating_options":
    case "checkpoint:seed":
    case "checkpoint:decision":
      return 0;
    case "simulating:ontology":
    case "checkpoint:ontology":
      return 1;
    case "simulating:graph_build":
    case "checkpoint:graph":
      return 2;
    case "simulating:prepare":
    case "checkpoint:profiles":
      return 3;
    case "simulating:running":
    case "checkpoint:config":
      return 4;
    case "simulating:report":
      return 5;
    case "completed":
      return 6;
    default:
      return -1;
  }
}

function isCheckpointStatus(status: string): boolean {
  return status.startsWith("checkpoint:");
}

function stepStatus(
  stepIdx: number,
  activeIdx: number,
  isFailed: boolean,
  isPaused: boolean
): "pending" | "running" | "completed" | "failed" | "paused" {
  if (isFailed && stepIdx === activeIdx) return "failed";
  if (stepIdx < activeIdx) return "completed";
  if (stepIdx === activeIdx) return isPaused ? "paused" : "running";
  return "pending";
}

const STATUS_COLORS: Record<string, { line: string; icon: string; bg: string }> = {
  pending: {
    line: "var(--border-secondary)",
    icon: "var(--text-muted)",
    bg: "transparent",
  },
  running: {
    line: "var(--accent-cyan)",
    icon: "var(--accent-cyan)",
    bg: "rgba(34, 211, 238, 0.1)",
  },
  completed: {
    line: "var(--status-connected)",
    icon: "var(--status-connected)",
    bg: "rgba(34, 197, 94, 0.1)",
  },
  failed: {
    line: "var(--accent-red)",
    icon: "var(--accent-red)",
    bg: "rgba(239, 68, 68, 0.1)",
  },
  paused: {
    line: "var(--accent-amber, #f59e0b)",
    icon: "var(--accent-amber, #f59e0b)",
    bg: "rgba(245, 158, 11, 0.1)",
  },
};

interface Props {
  pipelineStatus: PipelineStatus | null;
  onReview?: () => void;
}

function PipelineProgress({ pipelineStatus, onReview }: Props) {
  if (!pipelineStatus) {
    return (
      <div className="py-6 text-center text-[var(--text-muted)] text-[13px]">
        시나리오를 실행하면 진행 상태가 표시됩니다.
    </div>
  );
}

  const { status } = pipelineStatus;
  const isFailed = status === "failed";
  const isPaused = isCheckpointStatus(status);
  const activeIdx = activeStepIndex(status);

  return (
    <div aria-live="polite" className="flex flex-col gap-0">
      {STEPS.map(({ label, Icon }, i) => {
        const st = stepStatus(i, activeIdx, isFailed, isPaused);
        const colors = STATUS_COLORS[st];
        const isLast = i === STEPS.length - 1;

        return (
          <div key={label} className="flex gap-3 relative">
            {/* Vertical line + icon circle */}
            <div className="flex flex-col items-center w-8 shrink-0">
              {/* Icon circle */}
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-[border-color,background] duration-300"
                style={{
                  border: `2px solid ${colors.line}`,
                  background: colors.bg,
                  boxShadow:
                    st === "running"
                      ? "0 0 10px rgba(34, 211, 238, 0.3)"
                      : st === "paused"
                        ? "0 0 10px rgba(245, 158, 11, 0.3)"
                        : undefined,
                }}
              >
                {st === "completed" ? (
                  <Check size={14} color={colors.icon} aria-hidden="true" />
                ) : st === "failed" ? (
                  <X size={14} color={colors.icon} aria-hidden="true" />
                ) : st === "paused" ? (
                  <Pause size={14} color={colors.icon} aria-hidden="true" />
                ) : st === "running" ? (
                  <Loader2
                    size={14}
                    color={colors.icon}
                    aria-hidden="true"
                    className="animate-spin"
                  />
                ) : (
                  <Icon size={14} color={colors.icon} aria-hidden="true" />
                )}
              </div>
              {/* Connector line */}
              {!isLast && (
                <div
                  className="w-0.5 grow min-h-4 transition-[background] duration-300"
                  style={{
                    background:
                      stepStatus(i + 1, activeIdx, isFailed, isPaused) !== "pending"
                        ? "var(--status-connected)"
                        : "var(--border-secondary)",
                  }}
                />
              )}
            </div>

            {/* Label */}
            <div
              className="pt-1.5 text-[13px] transition-[color] duration-300 flex items-center gap-2 flex-wrap"
              style={{
                paddingBottom: isLast ? 0 : 16,
                color: st === "pending" ? "var(--text-muted)" : "var(--text-primary)",
                fontWeight: st === "running" || st === "paused" ? 600 : 400,
              }}
            >
              {label}
              {st === "running" && (
                <span className="text-[10px] text-[var(--accent-cyan)] font-normal">
                  진행 중
                </span>
              )}
              {st === "failed" && (
                <span className="text-[10px] text-[var(--accent-red)] font-normal">
                  실패
                </span>
              )}
              {st === "paused" && (
                <>
                  <span className="text-[10px] text-[var(--accent-amber,#f59e0b)] font-normal">
                    검토 대기
                  </span>
                  {onReview && (
                    <button
                      onClick={onReview}
                      className="px-2 py-0.5 bg-[rgba(245,158,11,0.15)] border border-[var(--accent-amber,#f59e0b)] rounded-[3px] text-[var(--accent-amber,#f59e0b)] text-[10px] font-semibold cursor-pointer inline-flex items-center gap-1"
                    >
                      <Eye size={10} aria-hidden="true" />
                      검토
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default memo(PipelineProgress);
