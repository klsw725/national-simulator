"use client";

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
      return 0;
    case "simulating:ontology":
      return 1;
    case "simulating:graph_build":
      return 2;
    case "simulating:prepare":
      return 3;
    case "simulating:running":
      return 4;
    case "simulating:report":
      return 5;
    case "completed":
      return 6; // all done
    default:
      return -1;
  }
}

function stepStatus(
  stepIdx: number,
  activeIdx: number,
  isFailed: boolean
): "pending" | "running" | "completed" | "failed" {
  if (isFailed && stepIdx === activeIdx) return "failed";
  if (stepIdx < activeIdx) return "completed";
  if (stepIdx === activeIdx) return "running";
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
};

interface Props {
  pipelineStatus: PipelineStatus | null;
}

export default function PipelineProgress({ pipelineStatus }: Props) {
  if (!pipelineStatus) {
    return (
      <div style={{ padding: "24px 0", textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
        시나리오를 실행하면 진행 상태가 표시됩니다.
      </div>
    );
  }

  const { status } = pipelineStatus;
  const isFailed = status === "failed";
  const activeIdx = activeStepIndex(status);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {STEPS.map(({ label, Icon }, i) => {
        const st = stepStatus(i, activeIdx, isFailed);
        const colors = STATUS_COLORS[st];
        const isLast = i === STEPS.length - 1;

        return (
          <div key={label} style={{ display: "flex", gap: 12, position: "relative" }}>
            {/* Vertical line + icon circle */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                width: 32,
                flexShrink: 0,
              }}
            >
              {/* Icon circle */}
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  border: `2px solid ${colors.line}`,
                  background: colors.bg,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  transition: "border-color 0.3s, background 0.3s",
                  boxShadow: st === "running" ? `0 0 10px rgba(34, 211, 238, 0.3)` : undefined,
                }}
              >
                {st === "completed" ? (
                  <Check size={14} color={colors.icon} />
                ) : st === "failed" ? (
                  <X size={14} color={colors.icon} />
                ) : st === "running" ? (
                  <Loader2
                    size={14}
                    color={colors.icon}
                    style={{ animation: "spin 1s linear infinite" }}
                  />
                ) : (
                  <Icon size={14} color={colors.icon} />
                )}
              </div>
              {/* Connector line */}
              {!isLast && (
                <div
                  style={{
                    width: 2,
                    flexGrow: 1,
                    minHeight: 16,
                    background:
                      stepStatus(i + 1, activeIdx, isFailed) !== "pending"
                        ? "var(--status-connected)"
                        : "var(--border-secondary)",
                    transition: "background 0.3s",
                  }}
                />
              )}
            </div>

            {/* Label */}
            <div
              style={{
                paddingTop: 6,
                paddingBottom: isLast ? 0 : 16,
                fontSize: 13,
                color: st === "pending" ? "var(--text-muted)" : "var(--text-primary)",
                fontWeight: st === "running" ? 600 : 400,
                transition: "color 0.3s",
              }}
            >
              {label}
              {st === "running" && (
                <span
                  style={{
                    marginLeft: 8,
                    fontSize: 10,
                    color: "var(--accent-cyan)",
                    fontWeight: 400,
                  }}
                >
                  진행 중
                </span>
              )}
              {st === "failed" && (
                <span
                  style={{
                    marginLeft: 8,
                    fontSize: 10,
                    color: "var(--accent-red)",
                    fontWeight: 400,
                  }}
                >
                  실패
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
