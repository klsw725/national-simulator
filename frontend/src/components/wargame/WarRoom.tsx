"use client";

import { useMemo, useState } from "react";
import { useWargame } from "@/hooks/useWargame";
import type { LiveAction } from "@/types/simulation";
import PhaseBar from "./PhaseBar";
import LensPanel from "./LensPanel";
import ContextPanel from "./ContextPanel";
import FeedPanel from "./FeedPanel";
import BriefingOverlay from "./BriefingOverlay";
import DecisionCard from "./DecisionCard";
import DebriefView from "./DebriefView";

interface Props {
  scenarioId: string;
  totalRounds: number;
  actions: LiveAction[];
  onClose: () => void;
}

export default function WarRoom({ scenarioId, totalRounds, actions, onClose }: Props) {
  const wargame = useWargame(scenarioId, totalRounds);
  const [selectedRound, setSelectedRound] = useState<number | null>(null);

  const decisionRounds = useMemo(
    () => wargame.decisionHistory.map((d) => d.round),
    [wargame.decisionHistory],
  );

  const handleDecisionConfirm = async (selectedOptionId: string) => {
    const dp = wargame.state.decisionPoint;
    if (!dp) return;

    const selectedOption = dp.options.find((o) => o.id === selectedOptionId);
    wargame.recordDecision({
      round: wargame.state.round,
      label: selectedOption?.label ?? selectedOptionId,
      outcome: selectedOption?.reasoning ?? "결정 반영됨",
    });

    try {
      await fetch(`/api/scenario/${scenarioId}/decision_points/${dp.id}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_option_id: selectedOptionId }),
      });
    } catch (err) {
      console.error("Failed to resolve decision:", err);
    }
    wargame.setPhase("confirmation");
    setTimeout(() => wargame.setPhase("simulation"), 2000);
  };

  const handleWhatIf = (_round?: number) => {
    console.log("What-If branch requested", _round);
  };

  const handleViewReport = () => {
    console.log("View report requested");
  };

  const handleNewSimulation = () => {
    wargame.setIsComplete(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-20 flex flex-col pointer-events-none">
      <div className="pointer-events-auto">
        <PhaseBar state={wargame.state} isMockMode={wargame.isMockMode} />
      </div>

      <div className="flex flex-1 min-h-0">
        <div className="pointer-events-auto">
          <LensPanel
            activeLens={wargame.activeLens}
            onLensChange={wargame.setActiveLens}
          />
        </div>

        <div className="flex-1 min-w-0 relative">
          <CloseButton onClick={onClose} />
        </div>

        <div className="pointer-events-auto">
          <ContextPanel
            actorStates={wargame.state.actorStates}
            phase={wargame.state.phase}
            playerActorId={wargame.state.actorId}
          />
        </div>
      </div>

      <div className="pointer-events-auto">
        <FeedPanel
          actions={actions}
          currentRound={wargame.state.round}
          totalRounds={totalRounds}
          decisionRounds={decisionRounds}
          selectedRound={selectedRound}
          onScrub={setSelectedRound}
        />
      </div>

      {wargame.state.phase === "briefing" && wargame.state.briefing && (
        <BriefingOverlay
          briefing={wargame.state.briefing}
          round={wargame.state.round}
          onProceedToDecision={() => wargame.setPhase("decision")}
        />
      )}

      {wargame.state.phase === "decision" && wargame.state.decisionPoint && (
        <DecisionCard
          decisionPoint={wargame.state.decisionPoint}
          round={wargame.state.round}
          onConfirm={handleDecisionConfirm}
          onWhatIf={handleWhatIf}
        />
      )}

      {wargame.state.phase === "confirmation" && !wargame.isComplete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
          <div className="bg-emerald-900/90 text-emerald-100 px-8 py-4 rounded-lg text-lg font-medium">
            결정이 반영되었습니다. 다음 라운드를 준비합니다...
          </div>
        </div>
      )}

      {wargame.isComplete && (
        <DebriefView
          totalRounds={totalRounds}
          tensionCurve={wargame.tensionHistory}
          decisions={wargame.decisionHistory}
          finalTension={wargame.state.tension}
          onViewReport={handleViewReport}
          onNewSimulation={handleNewSimulation}
          onWhatIf={handleWhatIf}
          onClose={() => wargame.setIsComplete(false)}
        />
      )}
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
