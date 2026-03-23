"use client";

import { useCallback, useEffect, useState } from "react";
import { Pause, Play, AlertTriangle, Send } from "lucide-react";
import {
  getInteractiveStatus,
  pauseSimulation,
  resumeSimulation,
  injectEvent,
} from "@/lib/gatewayApi";

interface InteractiveStatus {
  scenario_id: string;
  simulation_status: string;
  current_round: number;
  max_rounds: number;
  is_paused: boolean;
  pause_reason: string | null;
  injected_events_count: number;
  tension_alerts: number;
}

interface Props {
  scenarioId: string | undefined;
}

const EVENT_TYPES = [
  { value: "news_announcement", label: "뉴스 발표" },
  { value: "military_action", label: "군사 행동" },
  { value: "diplomatic_statement", label: "외교 성명" },
] as const;

export default function InteractiveSimulationView({ scenarioId }: Props) {
  const [status, setStatus] = useState<InteractiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const [eventContent, setEventContent] = useState("");
  const [eventType, setEventType] = useState<string>("news_announcement");
  const [injectLoading, setInjectLoading] = useState(false);
  const [injectSuccess, setInjectSuccess] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getInteractiveStatus(scenarioId);
      setStatus(data);
      setError(null);
      setLoading(false);
    } catch {
      setError("상태를 불러올 수 없습니다");
      setLoading(false);
    }
  }, [scenarioId]);

  useEffect(() => {
    if (!scenarioId) {
      setLoading(false);
      return;
    }

    fetchStatus();

    const interval = setInterval(() => {
      if (status?.simulation_status === "completed") return;
      fetchStatus();
    }, 5000);

    return () => clearInterval(interval);
  }, [scenarioId, fetchStatus, status?.simulation_status]);

  const handlePause = async () => {
    if (!scenarioId || actionLoading) return;
    setActionLoading(true);
    try {
      await pauseSimulation(scenarioId);
      await fetchStatus();
    } catch {
      setError("일시정지 실패");
    }
    setActionLoading(false);
  };

  const handleResume = async () => {
    if (!scenarioId || actionLoading) return;
    setActionLoading(true);
    try {
      await resumeSimulation(scenarioId);
      await fetchStatus();
    } catch {
      setError("재개 실패");
    }
    setActionLoading(false);
  };

  const handleInject = async () => {
    if (!scenarioId || !eventContent.trim() || injectLoading) return;
    setInjectLoading(true);
    setInjectSuccess(null);
    try {
      const result = await injectEvent(scenarioId, {
        event_type: eventType,
        content: eventContent.trim(),
        target_agents: [],
      });
      setInjectSuccess(`라운드 ${result.injected_at_round}에 주입됨`);
      setEventContent("");
      await fetchStatus();
    } catch {
      setError("이벤트 주입 실패");
    }
    setInjectLoading(false);
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
        인터랙티브 상태 로딩 중...
      </div>
    );
  }

  if (error && !status) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12 }}>
        {error}
      </div>
    );
  }

  if (!status) return null;

  const isRunning = status.simulation_status === "running" && !status.is_paused;
  const isPaused = status.is_paused;
  const isCompleted = status.simulation_status === "completed";
  const progressPct = status.max_rounds > 0 ? (status.current_round / status.max_rounds) * 100 : 0;

  const statusColor = isCompleted
    ? "#34d399"
    : isPaused
      ? "#f59e0b"
      : "#22d3ee";

  const statusLabel = isCompleted
    ? "완료"
    : isPaused
      ? "일시정지"
      : "진행 중";

  const rounds = Array.from({ length: status.max_rounds }, (_, i) => i + 1);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
          인터랙티브 시뮬레이션
        </span>
        <span
          style={{
            fontSize: 10,
            padding: "2px 8px",
            borderRadius: 999,
            background: `${statusColor}18`,
            color: statusColor,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          {isRunning && (
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: statusColor,
                animation: "pulse 1.5s ease-in-out infinite",
              }}
            />
          )}
          {statusLabel}
        </span>
        {status.injected_events_count > 0 && (
          <span
            style={{
              fontSize: 10,
              padding: "2px 6px",
              borderRadius: 999,
              background: "rgba(168, 85, 247, 0.15)",
              color: "#a855f7",
              fontWeight: 600,
            }}
          >
            주입 {status.injected_events_count}
          </span>
        )}
      </div>

      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            라운드 진행
          </span>
          <span style={{ fontSize: 11, color: "var(--text-primary)", fontFamily: "monospace", fontWeight: 700 }}>
            {status.current_round} / {status.max_rounds}
          </span>
        </div>
        <div
          style={{
            height: 6,
            background: "var(--border-secondary)",
            borderRadius: 3,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${progressPct}%`,
              height: "100%",
              background: isCompleted
                ? "linear-gradient(90deg, #34d399, #22d3ee)"
                : isPaused
                  ? "linear-gradient(90deg, #f59e0b, #f97316)"
                  : "linear-gradient(90deg, #22d3ee, #3b82f6)",
              borderRadius: 3,
              transition: "width 0.5s ease",
            }}
          />
        </div>
      </div>

      {status.tension_alerts > 0 && (
        <div
          style={{
            padding: "8px 10px",
            background: "rgba(245, 158, 11, 0.08)",
            border: "1px solid rgba(245, 158, 11, 0.2)",
            borderRadius: 4,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <AlertTriangle size={14} color="#f59e0b" />
          <span style={{ fontSize: 11, color: "#f59e0b", fontWeight: 500, flex: 1 }}>
            긴장도 경고 {status.tension_alerts}건 — 결정 탭 확인 필요
          </span>
        </div>
      )}

      {!isCompleted && (
        <div style={{ display: "flex", gap: 8 }}>
          {isRunning && (
            <button
              onClick={handlePause}
              disabled={actionLoading}
              style={{
                flex: 1,
                padding: "8px 12px",
                background: "rgba(245, 158, 11, 0.1)",
                border: "1px solid rgba(245, 158, 11, 0.25)",
                borderRadius: 4,
                color: "#f59e0b",
                fontSize: 12,
                fontWeight: 600,
                cursor: actionLoading ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                opacity: actionLoading ? 0.5 : 1,
              }}
            >
              <Pause size={13} />
              일시정지
            </button>
          )}
          {isPaused && (
            <button
              onClick={handleResume}
              disabled={actionLoading}
              style={{
                flex: 1,
                padding: "8px 12px",
                background: "rgba(34, 211, 238, 0.1)",
                border: "1px solid rgba(34, 211, 238, 0.25)",
                borderRadius: 4,
                color: "var(--accent-cyan)",
                fontSize: 12,
                fontWeight: 600,
                cursor: actionLoading ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                opacity: actionLoading ? 0.5 : 1,
              }}
            >
              <Play size={13} />
              시뮬레이션 재개
            </button>
          )}
        </div>
      )}

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
          라운드 타임라인
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          {rounds.map((r) => {
            const isCurrentRound = r === status.current_round;
            const isCompletedRound = r < status.current_round;
            const isPending = r > status.current_round;
            const hasTension = isCurrentRound && status.tension_alerts > 0;

            return (
              <div
                key={r}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "4px 0",
                }}
              >
                <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <div
                    style={{
                      width: isCurrentRound ? 12 : 8,
                      height: isCurrentRound ? 12 : 8,
                      borderRadius: "50%",
                      background: isCompletedRound
                        ? "var(--accent-cyan)"
                        : isCurrentRound
                          ? isPaused ? "#f59e0b" : "var(--accent-cyan)"
                          : "transparent",
                      border: isPending
                        ? "1.5px solid var(--border-secondary)"
                        : isCurrentRound
                          ? `2px solid ${isPaused ? "#f59e0b" : "var(--accent-cyan)"}`
                          : "none",
                      transition: "all 0.3s ease",
                      ...(isCurrentRound && isRunning
                        ? {
                            boxShadow: "0 0 0 3px rgba(34, 211, 238, 0.2)",
                            animation: "pulse 1.5s ease-in-out infinite",
                          }
                        : {}),
                    }}
                  />
                  {r < status.max_rounds && (
                    <div
                      style={{
                        width: 1.5,
                        height: 12,
                        background: isCompletedRound ? "var(--accent-cyan)" : "var(--border-secondary)",
                        opacity: isCompletedRound ? 0.4 : 1,
                      }}
                    />
                  )}
                </div>

                <span
                  style={{
                    fontSize: 11,
                    fontFamily: "monospace",
                    color: isCurrentRound
                      ? "var(--text-primary)"
                      : isCompletedRound
                        ? "var(--text-muted)"
                        : "var(--border-secondary)",
                    fontWeight: isCurrentRound ? 700 : 400,
                  }}
                >
                  라운드 {r}
                </span>

                <span style={{ flex: 1, height: 1, background: "var(--border-secondary)", opacity: 0.3 }} />

                <span
                  style={{
                    fontSize: 10,
                    color: isCompletedRound
                      ? "var(--text-muted)"
                      : isCurrentRound
                        ? isPaused ? "#f59e0b" : "var(--accent-cyan)"
                        : "var(--border-secondary)",
                    fontWeight: isCurrentRound ? 600 : 400,
                  }}
                >
                  {isCompletedRound && "completed"}
                  {isCurrentRound && isPaused && "PAUSED"}
                  {isCurrentRound && isRunning && "running"}
                  {isCurrentRound && isCompleted && "completed"}
                  {isPending && "pending"}
                </span>

                {hasTension && (
                  <AlertTriangle size={11} color="#f59e0b" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {isPaused && (
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
            이벤트 주입
          </div>

          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            style={{
              width: "100%",
              padding: "7px 10px",
              background: "rgb(12, 14, 18)",
              border: "1px solid var(--border-secondary)",
              borderRadius: 4,
              color: "var(--text-primary)",
              fontSize: 12,
              outline: "none",
            }}
          >
            {EVENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>

          <textarea
            value={eventContent}
            onChange={(e) => setEventContent(e.target.value)}
            placeholder="이벤트 내용을 입력하세요..."
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

          {injectSuccess && (
            <span style={{ fontSize: 11, color: "#34d399" }}>
              {injectSuccess}
            </span>
          )}

          <button
            onClick={handleInject}
            disabled={!eventContent.trim() || injectLoading}
            style={{
              width: "100%",
              padding: "8px 12px",
              background: eventContent.trim() && !injectLoading ? "var(--accent-cyan)" : "var(--border-secondary)",
              border: "none",
              borderRadius: 4,
              color: eventContent.trim() && !injectLoading ? "var(--bg-primary)" : "var(--text-muted)",
              fontSize: 12,
              fontWeight: 700,
              cursor: eventContent.trim() && !injectLoading ? "pointer" : "not-allowed",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              transition: "background 0.15s, color 0.15s",
            }}
          >
            <Send size={12} />
            이벤트 주입
          </button>
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
      `}</style>
    </div>
  );
}
