"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSimulationStream } from "@/hooks/useSimulationStream";
import { useWargame } from "@/hooks/useWargame";
import { resolveWargameDecision, resumeWargame, submitWargameDecisionV2 } from "@/lib/api/wargameApi";
import type { LiveAction } from "@/types/simulation";
import type { DecisionPoint as LegacyDecisionPoint, WargameDecisionPoint, WargameDecisionPointV2 } from "@/types/simulation";
import type { DecisionOption as V2DecisionOption, TriggerDetail } from "@/types/simulation-stream";
import BriefingOverlay from "./BriefingOverlay";
import DecisionCard from "./DecisionCard";
import DebriefView from "./DebriefView";

const PHASE_ACCENT: Record<string, string> = {
  simulation: "var(--accent-cyan)",
  simulating: "var(--accent-cyan)",
  analyzing: "var(--text-muted)",
  building: "var(--text-muted)",
  configuring: "var(--text-muted)",
  reporting: "var(--text-muted)",
  briefing: "var(--text-muted)",
  decision: "#f59e0b",
  confirmation: "var(--text-muted)",
};

interface Props {
  scenarioId: string;
  totalRounds: number;
  actions: LiveAction[];
  onClose: () => void;
  useV2?: boolean;
  onViewReport?: () => void;
  onCreateWhatIf?: (round: number) => void;
  onWargameOverlay?: (lens: string | null, phase: string | null) => void;
}

export default function WarRoom({
  scenarioId,
  totalRounds,
  actions,
  onClose,
  useV2 = true,
  onViewReport,
  onCreateWhatIf,
  onWargameOverlay,
}: Props) {
  const isV2DecisionPoint = (decisionPoint: WargameDecisionPoint | null): decisionPoint is WargameDecisionPointV2 => {
    return Boolean(decisionPoint && "trigger" in decisionPoint);
  };

  const isLegacyDecisionPoint = (decisionPoint: WargameDecisionPoint | null): decisionPoint is LegacyDecisionPoint => {
    return Boolean(decisionPoint && !isV2DecisionPoint(decisionPoint));
  };

  const toLegacyDecisionPoint = (decisionPoint: WargameDecisionPointV2, scenarioIdValue: string): LegacyDecisionPoint => ({
    id: decisionPoint.id,
    scenario_id: scenarioIdValue,
    type: "geopolitics_actor_response",
    options: [],
    recommended: "",
    allow_custom: false,
    status: "pending",
    selected_option_id: null,
    custom_data: null,
    created_at: new Date().toISOString(),
    resolved_at: null,
  });

  const wargame = useWargame(scenarioId, totalRounds);
  const streamState = useSimulationStream(useV2 ? scenarioId : null);
  const [selectedRound, setSelectedRound] = useState<number | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<SelectedFeedEntity | null>(null);
  const [dismissedDpId, setDismissedDpId] = useState<string | null>(null);
  const resumePollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const wargameDp = wargame.state.decisionPoint;
  const activeDecisionPoint = (wargameDp && isV2DecisionPoint(wargameDp) && wargameDp.id !== dismissedDpId)
    ? wargameDp
    : null;
  const activePhase = useV2
    ? (activeDecisionPoint ? "decision" : (streamState.phase || wargame.state.phase))
    : wargame.state.phase;
  const activeRound = useV2
    ? (streamState.currentRound || activeDecisionPoint?.round || wargame.state.round)
    : wargame.state.round;
  const activeIsConnected = useV2 ? streamState.isConnected : wargame.isConnected;

  const contextPhase = useMemo(() => {
    if (!useV2) return wargame.state.phase;
    if (streamState.phase === "briefing" || streamState.phase === "decision" || streamState.phase === "confirmation") {
      return streamState.phase;
    }
    return "simulation";
  }, [streamState.phase, useV2, wargame.state.phase]);

  useEffect(() => {
    return () => {
      if (resumePollRef.current) clearInterval(resumePollRef.current);
    };
  }, []);

  useEffect(() => {
    if (activePhase !== "confirmation" && resumePollRef.current) {
      clearInterval(resumePollRef.current);
      resumePollRef.current = null;
    }
  }, [activePhase]);

  useEffect(() => {
    onWargameOverlay?.(wargame.activeLens, activePhase);
  }, [wargame.activeLens, activePhase, onWargameOverlay]);

  useEffect(() => {
    return () => onWargameOverlay?.(null, null);
  }, [onWargameOverlay]);

  const phaseAccent = PHASE_ACCENT[activePhase] ?? "var(--text-muted)";

  const handleScrub = (round: number) => {
    setSelectedRound(round === 0 ? null : round);
  };

  const decisionRounds = useMemo(
    () => wargame.decisionHistory.map((d) => d.round),
    [wargame.decisionHistory],
  );

  const displaySnapshot = useMemo(
    () => wargame.getSnapshotForRound(selectedRound),
    [selectedRound, wargame],
  );

  const displayState = useMemo(() => {
    if (useV2) {
      return {
        ...wargame.state,
        phase: activePhase,
        round: activeRound,
        totalRounds: streamState.maxRounds || wargame.state.totalRounds,
      };
    }
    return displaySnapshot
      ? {
          ...wargame.state,
          round: displaySnapshot.round,
          tension: displaySnapshot.tension,
          actorStates: displaySnapshot.actorStates,
        }
      : wargame.state;
  }, [activePhase, activeRound, displaySnapshot, streamState.maxRounds, useV2, wargame.state]);

  const handleDecisionConfirm = async (selectedOptionId: string) => {
    if (useV2 && activeDecisionPoint) {
      const selectedOption = activeDecisionPoint.options.find((option, index) => {
        const optionId = `${option.action_type}-${option.target}-${index}`;
        return optionId === selectedOptionId;
      });
      if (!selectedOption) return;

      wargame.recordDecision({
        round: activeRound,
        label: selectedOption.action_type,
        outcome: selectedOption.description,
      });
      setDismissedDpId(activeDecisionPoint.id);
      wargame.setPhase("confirmation");

      await submitWargameDecisionV2(scenarioId, {
        decision_point_id: activeDecisionPoint.id,
        actor: inferDecisionActor(selectedOption, activeDecisionPoint.options),
        action_type: selectedOption.action_type,
        target: selectedOption.target,
        intensity: selectedOption.intensity,
        reasoning: selectedOption.description,
      }, selectedOptionId);
      return;
    }

    const dp = wargame.state.decisionPoint;
    if (!isLegacyDecisionPoint(dp)) return;

    const selectedOption = dp.options.find((o) => o.id === selectedOptionId);
    wargame.recordDecision({
      round: wargame.state.round,
      label: selectedOption?.label ?? selectedOptionId,
      outcome: selectedOption?.reasoning ?? "결정 반영됨",
    });

    wargame.setPhase("confirmation");

    if (resumePollRef.current) {
      clearInterval(resumePollRef.current);
      resumePollRef.current = null;
    }

    try {
      await resolveWargameDecision(scenarioId, dp.id, selectedOptionId);
    } catch (err) {
      const is409 = err instanceof Error && err.message.includes("409");
      if (!is409) {
        if (process.env.NODE_ENV === "development") {
          console.error("Failed to resolve wargame decision:", err);
        }
        return;
      }
    }

    try {
      await resumeWargame(scenarioId);
    } catch {
      void wargame.refreshState();
    }

    if (!activeIsConnected) {
      resumePollRef.current = setInterval(() => {
        wargame.refreshState().catch(() => {});
      }, 3000);
      setTimeout(() => {
        if (resumePollRef.current) {
          clearInterval(resumePollRef.current);
          resumePollRef.current = null;
        }
      }, 120_000);
    }
  };

  const handleWhatIf = (round?: number) => {
    if (onCreateWhatIf) {
      onCreateWhatIf(round ?? wargame.state.round);
    }
  };

  const handleViewReport = () => {
    wargame.setShowDebrief(false);
    if (onViewReport) {
      onViewReport();
    }
    onClose();
  };

  const handleNewSimulation = () => {
    wargame.setIsComplete(false);
    wargame.setShowDebrief(false);
    onClose();
  };

  return (
    <div
      className="fixed inset-y-0 left-0 z-20 pointer-events-none transition-colors duration-500"
      style={{ "--war-room-accent": phaseAccent, right: 400 } as React.CSSProperties}
    >
      {!useV2 && wargame.state.phase === "briefing" && wargame.state.briefing && (
        <BriefingOverlay
          briefing={wargame.state.briefing}
            round={displayState.round}
            onProceedToDecision={() => wargame.setPhase("decision")}
          />
        )}

      {((!useV2 && wargame.state.phase === "decision" && wargame.state.decisionPoint) || (useV2 && activeDecisionPoint)) && (
        <DecisionCard
          decisionPoint={useV2 && activeDecisionPoint
            ? toLegacyDecisionPoint(activeDecisionPoint, scenarioId)
            : (isLegacyDecisionPoint(wargame.state.decisionPoint)
              ? wargame.state.decisionPoint
              : toLegacyDecisionPoint(activeDecisionPoint!, scenarioId))}
          v2Options={useV2 ? activeDecisionPoint?.options : undefined}
          triggerInfo={useV2 && activeDecisionPoint ? {
            trigger: activeDecisionPoint.trigger,
            trigger_detail: (activeDecisionPoint as { trigger_detail?: TriggerDetail | null }).trigger_detail,
          } : null}
          round={activeRound}
          onConfirm={handleDecisionConfirm}
          onWhatIf={handleWhatIf}
        />
      )}

      {(activePhase === "simulation" || activePhase === "simulating" || activePhase === "confirmation") && !wargame.isComplete && (
        <RoundProgressOverlay
          round={activeRound}
          totalRounds={totalRounds}
          tension={wargame.state.tension}
        />
      )}

      {wargame.isComplete && !wargame.showDebrief && (
        <div className="fixed bottom-56 right-4 z-30 pointer-events-auto">
          <button
            onClick={() => wargame.setShowDebrief(true)}
            className="px-3 py-2 rounded-md text-xs font-semibold bg-[rgba(34,211,238,0.12)] border border-[var(--accent-cyan)] text-[var(--accent-cyan)] cursor-pointer transition-colors hover:bg-[rgba(34,211,238,0.2)]"
          >
            📊 디브리프 보기
          </button>
        </div>
      )}

      {wargame.showDebrief && (
        <DebriefView
          totalRounds={totalRounds}
          tensionCurve={wargame.tensionHistory}
          decisions={wargame.decisionHistory}
          finalTension={wargame.state.tension}
          onViewReport={handleViewReport}
          onNewSimulation={handleNewSimulation}
          onWhatIf={handleWhatIf}
          onClose={() => wargame.setShowDebrief(false)}
        />
      )}
    </div>
  );
}

function inferDecisionActor(option: V2DecisionOption, options: V2DecisionOption[]): string {
  void options;
  return option.target;
}

function RoundProgressOverlay({
  round,
  totalRounds,
  tension,
}: {
  round: number;
  totalRounds: number;
  tension: number;
}) {
  const [dots, setDots] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const dotTimer = setInterval(() => setDots((d) => (d + 1) % 4), 500);
    const elapsedTimer = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => {
      clearInterval(dotTimer);
      clearInterval(elapsedTimer);
    };
  }, []);

  const pct = Math.round((round / totalRounds) * 100);
  const tensionPct = Math.round(tension * 100);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}분 ${sec}초` : `${sec}초`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
      <div
        className="pointer-events-auto rounded-2xl border px-10 py-8 flex flex-col items-center gap-5 min-w-[360px] max-w-[480px]"
        style={{
          background: "linear-gradient(135deg, rgba(6,30,42,0.97) 0%, rgba(8,20,32,0.98) 100%)",
          borderColor: "var(--accent-cyan)",
          boxShadow: "0 0 40px rgba(34,211,238,0.12), 0 4px 24px rgba(0,0,0,0.5)",
        }}
      >
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest" style={{ color: "var(--accent-cyan)" }}>
          <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          시뮬레이션 진행 중
        </div>

        <div className="text-center">
          <div className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            라운드 {round + 1} / {totalRounds}
          </div>
          <div className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            에이전트가 행동을 결정하고 있습니다{".".repeat(dots)}
          </div>
        </div>

        <div className="w-full space-y-3">
          <div>
            <div className="flex justify-between text-[11px] mb-1" style={{ color: "var(--text-muted)" }}>
              <span>전체 진행률</span>
              <span>{pct}%</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
              <div
                className="h-full rounded-full transition-all duration-700 relative overflow-hidden"
                style={{
                  width: `${pct}%`,
                  background: "linear-gradient(90deg, #22d3ee, #06b6d4)",
                }}
              >
                <div
                  className="absolute inset-0 animate-pulse"
                  style={{ background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)" }}
                />
              </div>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-[11px] mb-1" style={{ color: "var(--text-muted)" }}>
              <span>긴장도</span>
              <span>{tensionPct}%</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${tensionPct}%`,
                  background: tensionPct > 70
                    ? "linear-gradient(90deg, #ef4444, #dc2626)"
                    : tensionPct > 40
                    ? "linear-gradient(90deg, #f59e0b, #d97706)"
                    : "linear-gradient(90deg, #22c55e, #16a34a)",
                }}
              />
            </div>
          </div>
        </div>

        <div className="text-[11px] tabular-nums" style={{ color: "var(--text-muted)" }}>
          경과 시간: {formatTime(elapsed)}
        </div>
      </div>
    </div>
  );
}

function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="pointer-events-auto absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-[rgba(0,0,0,0.6)] border border-[var(--border-secondary)] text-[var(--text-muted)] text-sm font-bold cursor-pointer flex items-center justify-center transition-colors duration-150 hover:bg-[rgba(0,0,0,0.8)] hover:text-[var(--text-primary)]"
      title="상황실 닫기"
    >
      ✕
    </button>
  );
}
