"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  GraphData,
  GraphTaskStatus,
  LiveAction,
  LiveConfig,
  LiveProfiles,
  LiveStats,
} from "@/types/simulation";
import {
  getLiveActions,
  getLiveStats,
} from "@/lib/gatewayApi";

interface UseLiveSimulationResult {
  stats: LiveStats | null;
  actions: LiveAction[];
  graphTaskStatus: GraphTaskStatus | null;
  graphData: GraphData | null;
  profiles: LiveProfiles | null;
  config: LiveConfig | null;
  isLive: boolean;
}

export function useLiveSimulation(
  scenarioId: string | null,
  pipelineStatus: string | null,
  isWargame: boolean = false,
): UseLiveSimulationResult {
  const [stats, setStats] = useState<LiveStats | null>(null);
  const [actions, setActions] = useState<LiveAction[]>([]);
  const [graphTaskStatus, setGraphTaskStatus] = useState<GraphTaskStatus | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [profiles, setProfiles] = useState<LiveProfiles | null>(null);
  const [config, setConfig] = useState<LiveConfig | null>(null);

  const statsIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const actionsIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastOffsetRef = useRef(0);

  const clearIntervals = useCallback(() => {
    if (statsIntervalRef.current) {
      clearInterval(statsIntervalRef.current);
      statsIntervalRef.current = null;
    }
    if (actionsIntervalRef.current) {
      clearInterval(actionsIntervalRef.current);
      actionsIntervalRef.current = null;
    }
  }, []);

  const pollStats = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getLiveStats(scenarioId);
      setStats(data);
    } catch (e) { if (process.env.NODE_ENV === "development") console.warn("pollStats failed", e); }
  }, [scenarioId]);

  const pollActions = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getLiveActions(scenarioId, lastOffsetRef.current, 100);
      const nextActions = Array.isArray(data.actions) ? data.actions : [];

      if (nextActions.length > 0) {
        setActions((prev) => {
          const merged = [...prev, ...nextActions];
          return merged.length > 1000 ? merged.slice(-1000) : merged;
        });
      }

      if (typeof data.count === "number") {
        lastOffsetRef.current += data.count;
      }
    } catch (e) { if (process.env.NODE_ENV === "development") console.warn("pollActions failed", e); }
  }, [scenarioId]);

  useEffect(() => {
    clearIntervals();

    const isRunningPipeline = pipelineStatus?.startsWith("simulating:") || false;
    if (!scenarioId || (!isRunningPipeline && !isWargame)) {
      return;
    }

    pollStats();
    pollActions();
    statsIntervalRef.current = setInterval(pollStats, 2_000);
    actionsIntervalRef.current = setInterval(pollActions, 3_000);
  }, [
    scenarioId,
    pipelineStatus,
    isWargame,
    clearIntervals,
    pollStats,
    pollActions,
  ]);

  useEffect(() => {
    setStats(null);
    setActions([]);
    setGraphTaskStatus(null);
    setGraphData(null);
    setProfiles(null);
    setConfig(null);
    lastOffsetRef.current = 0;
  }, [scenarioId]);

  useEffect(() => {
    if (!pipelineStatus?.startsWith("simulating:")) {
      setActions([]);
      lastOffsetRef.current = 0;
    }
  }, [pipelineStatus]);

  useEffect(() => {
    return () => {
      clearIntervals();
    };
  }, [clearIntervals]);

  const isLive = useMemo(
    () => Boolean(scenarioId && (pipelineStatus?.startsWith("simulating:") || isWargame)),
    [scenarioId, pipelineStatus, isWargame],
  );

  return {
    stats,
    actions,
    graphTaskStatus,
    graphData,
    profiles,
    config,
    isLive,
  };
}
