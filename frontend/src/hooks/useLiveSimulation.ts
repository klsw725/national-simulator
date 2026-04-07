"use client";

import { useEffect, useMemo, useState } from "react";
import { useSimulationStream } from "@/hooks/useSimulationStream";
import { getLiveGraphData } from "@/lib/api/liveApi";
import type {
  GraphData,
  GraphTaskStatus,
  LiveAction,
  LiveConfig,
  LiveProfiles,
  LiveStats,
} from "@/types/simulation";

interface UseLiveSimulationResult {
  stats: LiveStats | null;
  actions: LiveAction[];
  graphTaskStatus: GraphTaskStatus | null;
  graphData: GraphData | null;
  profiles: LiveProfiles | null;
  config: LiveConfig | null;
  isLive: boolean;
}

const GRAPH_POLL_MS = 3_000;
const GRAPH_PHASES = new Set([
  "simulating:graph_build",
  "simulating:prepare",
  "simulating:running",
  "simulating:report",
]);

export function useLiveSimulation(
  scenarioId: string | null,
  pipelineStatus: string | null,
  isWargame: boolean = false,
): UseLiveSimulationResult {
  const stream = useSimulationStream(scenarioId);
  const [graphData, setGraphData] = useState<GraphData | null>(null);

  const isLive = useMemo(
    () => Boolean(scenarioId && (pipelineStatus?.startsWith("simulating:") || isWargame)),
    [scenarioId, pipelineStatus, isWargame],
  );

  useEffect(() => {
    if (!scenarioId || !pipelineStatus || !GRAPH_PHASES.has(pipelineStatus)) return;

    let cancelled = false;

    const fetch = () => {
      getLiveGraphData(scenarioId)
        .then((data) => {
          if (!cancelled) setGraphData(data);
        })
        .catch(() => {});
    };

    fetch();

    let timer: ReturnType<typeof setInterval> | null = null;
    if (pipelineStatus === "simulating:graph_build") {
      timer = setInterval(fetch, GRAPH_POLL_MS);
    }

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [scenarioId, pipelineStatus]);

  const actions = useMemo<LiveAction[]>(() => {
    return stream.recentActions.map((action, index) => ({
      round_num: action.round ?? stream.currentRound,
      timestamp: `${action.round ?? stream.currentRound}-${action.actor}-${index}`,
      platform: "geopolitics",
      agent_id: index,
      agent_name: action.actor,
      action_type: action.action_type,
      action_args: {
        content: action.reasoning,
        target: action.target,
        intensity: action.intensity,
      },
      success: true,
      geopolitics_label: action.action_type.replace(/_/g, " "),
    }));
  }, [stream.currentRound, stream.recentActions]);

  const stats = useMemo<LiveStats | null>(() => {
    if (!isLive) {
      return null;
    }
    const totalRounds = stream.maxRounds || 0;
    const currentRound = stream.currentRound;
    return {
      runner_status: stream.status,
      current_round: currentRound,
      total_rounds: totalRounds,
      progress_percent: totalRounds > 0 ? Math.min(100, Math.round((currentRound / totalRounds) * 100)) : 0,
      twitter_actions_count: 0,
      total_actions_count: actions.length,
    };
  }, [actions.length, isLive, stream.currentRound, stream.maxRounds, stream.status]);

  return {
    stats,
    actions,
    graphTaskStatus: null,
    graphData,
    profiles: null,
    config: null,
    isLive,
  };
}
