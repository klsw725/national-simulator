"use client";

import { useState } from "react";
import { Trash2, ChevronRight, Inbox } from "lucide-react";
import type { Scenario } from "@/types/simulation";

const STATUS_BADGE: Record<string, { label: string; color: string; bg: string }> = {
  created: { label: "대기", color: "var(--text-muted)", bg: "rgba(107, 114, 128, 0.15)" },
  starting: { label: "시작", color: "var(--accent-cyan)", bg: "rgba(34, 211, 238, 0.1)" },
  completed: { label: "완료", color: "var(--status-connected)", bg: "rgba(34, 197, 94, 0.1)" },
  failed: { label: "실패", color: "var(--accent-red)", bg: "rgba(239, 68, 68, 0.1)" },
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

export default function ScenarioList({ scenarios, activeId, onSelect, onDelete }: Props) {
  const [confirmId, setConfirmId] = useState<string | null>(null);

  if (scenarios.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "48px 16px",
          color: "var(--text-muted)",
          gap: 12,
        }}
      >
        <Inbox size={32} strokeWidth={1.5} />
        <span style={{ fontSize: 13 }}>생성된 시나리오가 없습니다.</span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {scenarios.map((s) => {
        const badge = getBadge(s.status);
        const isActive = s.id === activeId;
        const isConfirming = confirmId === s.id;

        return (
          <div
            key={s.id}
            style={{
              padding: "10px 12px",
              background: isActive ? "rgba(34, 211, 238, 0.06)" : "var(--bg-primary)",
              border: `1px solid ${isActive ? "rgba(34, 211, 238, 0.2)" : "var(--border-secondary)"}`,
              borderRadius: 6,
              cursor: "pointer",
              transition: "background 0.15s, border-color 0.15s",
            }}
            onClick={() => onSelect(s)}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <ChevronRight
                  size={14}
                  color={isActive ? "var(--accent-cyan)" : "var(--text-muted)"}
                />
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: isActive ? 600 : 400,
                    color: "var(--text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {s.name}
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                {/* Status badge */}
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    padding: "2px 8px",
                    borderRadius: 3,
                    color: badge.color,
                    background: badge.bg,
                    whiteSpace: "nowrap",
                  }}
                >
                  {badge.label}
                </span>

                {/* Delete */}
                {isConfirming ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmId(null);
                      onDelete(s.id);
                    }}
                    style={{
                      background: "rgba(239, 68, 68, 0.15)",
                      border: "1px solid var(--accent-red)",
                      borderRadius: 3,
                      padding: "2px 8px",
                      fontSize: 10,
                      color: "var(--accent-red)",
                      cursor: "pointer",
                      fontWeight: 600,
                    }}
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
                    style={{
                      background: "transparent",
                      border: "none",
                      padding: 4,
                      cursor: "pointer",
                      color: "var(--text-muted)",
                      display: "flex",
                      alignItems: "center",
                    }}
                    title="삭제"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            </div>

            {/* Meta */}
            <div
              style={{
                marginTop: 4,
                paddingLeft: 22,
                fontSize: 11,
                color: "var(--text-muted)",
              }}
            >
              {s.region_name} · {new Date(s.created_at).toLocaleDateString("ko-KR")}
            </div>
          </div>
        );
      })}
    </div>
  );
}
