"use client";

import { useCallback, useEffect, useState } from "react";
import { GitBranch, ArrowRight, Loader2 } from "lucide-react";
import {
  createWhatIfBranch,
  getWhatIfBranches,
  WhatIfBranch,
} from "@/lib/gatewayApi";

interface Props {
  scenarioId: string | undefined;
  onOpenCompare: (branchId: string) => void;
}

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  pending: { bg: "rgba(156, 163, 175, 0.15)", color: "#9ca3af", label: "대기" },
  running: { bg: "rgba(34, 211, 238, 0.15)", color: "#22d3ee", label: "실행 중" },
  completed: { bg: "rgba(52, 211, 153, 0.15)", color: "#34d399", label: "완료" },
  failed: { bg: "rgba(239, 68, 68, 0.15)", color: "#ef4444", label: "실패" },
};

export default function WhatIfBranchView({ scenarioId, onOpenCompare }: Props) {
  const [branches, setBranches] = useState<WhatIfBranch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modification, setModification] = useState("");
  const [createLoading, setCreateLoading] = useState(false);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);

  const fetchBranches = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getWhatIfBranches(scenarioId);
      setBranches(data);
      setError(null);
      setLoading(false);
    } catch {
      setError("분기 목록을 불러올 수 없습니다");
      setLoading(false);
    }
  }, [scenarioId]);

  useEffect(() => {
    if (!scenarioId) {
      setLoading(false);
      return;
    }

    fetchBranches();

    const interval = setInterval(() => {
      const hasRunning = branches.some((b) => b.status === "running" || b.status === "pending");
      if (!hasRunning) return;
      fetchBranches();
    }, 5000);

    return () => clearInterval(interval);
  }, [scenarioId, fetchBranches, branches]);

  const handleCreate = async () => {
    if (!scenarioId || !modification.trim() || createLoading) return;
    setCreateLoading(true);
    setCreateSuccess(null);
    setError(null);
    try {
      await createWhatIfBranch(scenarioId, { modification: modification.trim() });
      setCreateSuccess("분기가 생성되었습니다");
      setModification("");
      await fetchBranches();
    } catch {
      setError("분기 생성 실패");
    }
    setCreateLoading(false);
  };

  if (!scenarioId) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12 }}>
        시나리오를 선택하세요
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12 }}>
        분기 목록 로딩 중...
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <GitBranch size={14} color="var(--accent-cyan)" />
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
          What-If 분기
        </span>
        {branches.length > 0 && (
          <span
            style={{
              fontSize: 10,
              padding: "2px 8px",
              borderRadius: 999,
              background: "rgba(34, 211, 238, 0.12)",
              color: "var(--accent-cyan)",
              fontWeight: 600,
            }}
          >
            {branches.length}
          </span>
        )}
      </div>

      <div
        style={{
          padding: 12,
          background: "var(--bg-primary)",
          border: "1px solid var(--border-secondary)",
          borderRadius: 4,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "var(--text-primary)",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
          }}
        >
          가설 분기 생성
        </div>

        <textarea
          value={modification}
          onChange={(e) => setModification(e.target.value)}
          placeholder="예: 중국 함대가 철수했다면?"
          rows={3}
          style={{
            width: "100%",
            padding: "7px 10px",
            background: "rgb(12, 14, 18)",
            border: "1px solid var(--border-secondary)",
            borderRadius: 4,
            color: "var(--text-primary)",
            fontSize: 12,
            lineHeight: 1.5,
            outline: "none",
            resize: "vertical",
            fontFamily: "inherit",
          }}
        />

        {createSuccess && (
          <span style={{ fontSize: 11, color: "#34d399" }}>
            {createSuccess}
          </span>
        )}

        <button
          onClick={handleCreate}
          disabled={!modification.trim() || createLoading}
          style={{
            width: "100%",
            padding: "8px 12px",
            background: modification.trim() && !createLoading ? "var(--accent-cyan)" : "var(--border-secondary)",
            border: "none",
            borderRadius: 4,
            color: modification.trim() && !createLoading ? "var(--bg-primary)" : "var(--text-muted)",
            fontSize: 12,
            fontWeight: 700,
            cursor: modification.trim() && !createLoading ? "pointer" : "not-allowed",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            transition: "background 0.15s, color 0.15s",
          }}
        >
          {createLoading ? (
            <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
          ) : (
            <GitBranch size={12} />
          )}
          {createLoading ? "생성 중..." : "분기 실행"}
        </button>
      </div>

      {branches.length > 0 && (
        <div>
          <div
            style={{
              fontSize: 10,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 8,
            }}
          >
            분기 목록
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {branches.map((branch) => {
              const statusStyle = STATUS_STYLES[branch.status] || STATUS_STYLES.pending;
              const truncated = branch.modification.length > 50
                ? branch.modification.slice(0, 50) + "..."
                : branch.modification;

              return (
                <div
                  key={branch.id}
                  style={{
                    padding: "10px 12px",
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border-secondary)",
                    borderRadius: 4,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontSize: 10,
                        padding: "2px 8px",
                        borderRadius: 999,
                        background: statusStyle.bg,
                        color: statusStyle.color,
                        fontWeight: 600,
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        flexShrink: 0,
                      }}
                    >
                      {branch.status === "running" && (
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: statusStyle.color,
                            animation: "pulse 1.5s ease-in-out infinite",
                          }}
                        />
                      )}
                      {statusStyle.label}
                    </span>
                    {branch.branch_point_round !== null && (
                      <span
                        style={{
                          fontSize: 10,
                          color: "var(--text-muted)",
                          fontFamily: "monospace",
                        }}
                      >
                        R{branch.branch_point_round}
                      </span>
                    )}
                    <span style={{ flex: 1 }} />
                    {branch.status === "running" && (
                      <Loader2
                        size={12}
                        color="#22d3ee"
                        style={{ animation: "spin 1s linear infinite" }}
                      />
                    )}
                  </div>

                  <span
                    style={{
                      fontSize: 11,
                      color: "var(--text-primary)",
                      lineHeight: 1.4,
                    }}
                  >
                    {truncated}
                  </span>

                  {branch.status === "completed" && (
                    <button
                      onClick={() => onOpenCompare(branch.id)}
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        background: "rgba(34, 211, 238, 0.1)",
                        border: "1px solid rgba(34, 211, 238, 0.25)",
                        borderRadius: 4,
                        color: "var(--accent-cyan)",
                        fontSize: 11,
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 6,
                      }}
                    >
                      <ArrowRight size={11} />
                      비교 보기
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {error && (
        <div style={{ fontSize: 11, color: "var(--accent-red, #ef4444)", padding: "4px 0" }}>
          {error}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
