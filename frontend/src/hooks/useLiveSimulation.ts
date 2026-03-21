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
  getLiveConfig,
  getLiveGraphData,
  getLiveGraphTask,
  getLiveProfiles,
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
  pipelineStatus: string | null
): UseLiveSimulationResult {
  const [stats, setStats] = useState<LiveStats | null>(null);
  const [actions, setActions] = useState<LiveAction[]>([]);
  const [graphTaskStatus, setGraphTaskStatus] = useState<GraphTaskStatus | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [profiles, setProfiles] = useState<LiveProfiles | null>(null);
  const [config, setConfig] = useState<LiveConfig | null>(null);

  const graphTaskIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const graphDataIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const profilesIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const configIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statsIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const actionsIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastOffsetRef = useRef(0);

  const clearIntervals = useCallback(() => {
    if (graphTaskIntervalRef.current) {
      clearInterval(graphTaskIntervalRef.current);
      graphTaskIntervalRef.current = null;
    }
    if (graphDataIntervalRef.current) {
      clearInterval(graphDataIntervalRef.current);
      graphDataIntervalRef.current = null;
    }
    if (profilesIntervalRef.current) {
      clearInterval(profilesIntervalRef.current);
      profilesIntervalRef.current = null;
    }
    if (configIntervalRef.current) {
      clearInterval(configIntervalRef.current);
      configIntervalRef.current = null;
    }
    if (statsIntervalRef.current) {
      clearInterval(statsIntervalRef.current);
      statsIntervalRef.current = null;
    }
    if (actionsIntervalRef.current) {
      clearInterval(actionsIntervalRef.current);
      actionsIntervalRef.current = null;
    }
  }, []);

  const pollGraphTask = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getLiveGraphTask(scenarioId);
      setGraphTaskStatus(data);
    } catch {}
  }, [scenarioId]);

  const pollGraphData = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getLiveGraphData(scenarioId);
      setGraphData(data);
    } catch {}
  }, [scenarioId]);

  const pollProfiles = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getLiveProfiles(scenarioId);
      setProfiles(data);
    } catch {}
  }, [scenarioId]);

  const pollConfig = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getLiveConfig(scenarioId);
      setConfig(data);
    } catch {}
  }, [scenarioId]);

  const pollStats = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getLiveStats(scenarioId);
      setStats(data);
    } catch {}
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
    } catch {}
  }, [scenarioId]);

  useEffect(() => {
    clearIntervals();

    if (!scenarioId || !pipelineStatus?.startsWith("simulating:")) {
      return;
    }

    if (pipelineStatus === "simulating:graph_build") {
      pollGraphTask();
      pollGraphData();
      graphTaskIntervalRef.current = setInterval(pollGraphTask, 2_000);
      graphDataIntervalRef.current = setInterval(pollGraphData, 10_000);
      return;
    }

    if (pipelineStatus === "simulating:prepare") {
      pollProfiles();
      pollConfig();
      profilesIntervalRef.current = setInterval(pollProfiles, 3_000);
      configIntervalRef.current = setInterval(pollConfig, 2_000);
      return;
    }

    if (pipelineStatus === "simulating:running") {
      pollStats();
      pollActions();
      statsIntervalRef.current = setInterval(pollStats, 2_000);
      actionsIntervalRef.current = setInterval(pollActions, 3_000);
    }
  }, [
    scenarioId,
    pipelineStatus,
    clearIntervals,
    pollGraphTask,
    pollGraphData,
    pollProfiles,
    pollConfig,
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
    if (pipelineStatus !== "simulating:running") {
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
    () => Boolean(scenarioId && pipelineStatus?.startsWith("simulating:")),
    [scenarioId, pipelineStatus]
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
