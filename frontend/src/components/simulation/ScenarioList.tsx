"use client";

import { memo, useState } from "react";
import { Trash2, ChevronRight, Inbox } from "lucide-react";
import type { Scenario } from "@/types/simulation";

const STATUS_BADGE: Record<string, { label: string; color: string; bg: string }> = {
  created: { label: "대기", color: "var(--text-muted)", bg: "rgba(107, 114, 128, 0.15)" },
  starting: { label: "시작", color: "var(--accent-cyan)", bg: "rgba(34, 211, 238, 0.1)" },
  running: { label: "실행 중", color: "var(--accent-cyan)", bg: "rgba(34, 211, 238, 0.1)" },
  completed: { label: "완료", color: "var(--status-connected)", bg: "rgba(34, 197, 94, 0.1)" },
  failed: { label: "실패", color: "var(--accent-red)", bg: "rgba(239, 68, 68, 0.1)" },
  cancelled: { label: "취소", color: "var(--text-muted)", bg: "rgba(107, 114, 128, 0.15)" },
};

function getBadge(status: string) {
  if (status.startsWith("simulating")) {
    return { label: "실행 중", color: "var(--accent-cyan)", bg: "rgba(34, 211, 238, 0.1)" };
  }
  return STATUS_BADGE[status] ?? STATUS_BADGE.created;
}

interface Props {
  scenarios: Scenario[];
  activeId: string | null;
  onSelect: (s: Scenario) => void;
  onDelete: (id: string) => Promise<void>;
}

function ScenarioList({ scenarios, activeId, onSelect, onDelete }: Props) {
  const [confirmId, setConfirmId] = useState<string | null>(null);

  if (scenarios.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center px-4 py-12 text-[var(--text-muted)] gap-3">
        <Inbox size={32} strokeWidth={1.5} aria-hidden="true" />
        <span className="text-[13px]">생성된 시나리오가 없습니다.</span>
      </div>
    );
  }

  return (
    <div role="list" className="flex flex-col gap-1.5">
      {scenarios.map((s) => {
        const badge = getBadge(s.status);
        const isActive = s.id === activeId;
        const isConfirming = confirmId === s.id;

        return (
          <div
            key={s.id}
            role="listitem"
            tabIndex={0}
            aria-current={isActive ? "true" : undefined}
            className="px-3 py-2.5 rounded-md cursor-pointer transition-[background,border-color] duration-150"
            style={{
              background: isActive ? "rgba(34, 211, 238, 0.06)" : "var(--bg-primary)",
              border: `1px solid ${isActive ? "rgba(34, 211, 238, 0.2)" : "var(--border-secondary)"}`,
            }}
            onClick={() => onSelect(s)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(s); } }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <ChevronRight
                  size={14}
                  color={isActive ? "var(--accent-cyan)" : "var(--text-muted)"}
                  aria-hidden="true"
                />
                <span
                  className="text-[13px] text-[var(--text-primary)] truncate"
                  style={{ fontWeight: isActive ? 600 : 400 }}
                >
                  {s.name}
                </span>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <span
                  className="text-[10px] font-semibold px-2 py-0.5 rounded-[3px] whitespace-nowrap"
                  style={{ color: badge.color, background: badge.bg }}
                >
                  {badge.label}
                </span>

                {isConfirming ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmId(null);
                      onDelete(s.id);
                    }}
                    className="bg-[rgba(239,68,68,0.15)] border border-[var(--accent-red)] rounded-[3px] px-2 py-0.5 text-[10px] text-[var(--accent-red)] cursor-pointer font-semibold"
                  >
                    확인
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmId(s.id);
                      setTimeout(() => setConfirmId(null), 3000);
                    }}
                    className="bg-transparent border-none p-1 cursor-pointer text-[var(--text-muted)] flex items-center"
                    title="삭제"
                    aria-label="삭제"
                  >
                    <Trash2 size={13} aria-hidden="true" />
                  </button>
                )}
              </div>
            </div>

            <div className="mt-1 pl-[22px] text-[11px] text-[var(--text-muted)]">
              {s.region_name} · {new Date(s.created_at).toLocaleDateString("ko-KR")}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default memo(ScenarioList);
