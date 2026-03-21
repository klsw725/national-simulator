"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Scenario, ScenarioFormData, PipelineStatus, SimulationAction, PipelineMode, CheckpointData } from "@/types/simulation";
import * as api from "@/lib/gatewayApi";

const POLL_INTERVAL = 5_000;

export interface UseSimulationReturn {
  scenarios: Scenario[];
  activeScenario: Scenario | null;
  pipelineStatus: PipelineStatus | null;
  isRunning: boolean;
  error: string | null;
  simulationGeoJSON: GeoJSON.FeatureCollection | null;
  simulationResults: SimulationAction[];
  reportMarkdown: string;
  checkpointData: CheckpointData | null;
  pipelineMode: PipelineMode;
  createAndRun: (data: ScenarioFormData) => Promise<void>;
  deleteScenario: (id: string) => Promise<void>;
  selectScenario: (scenario: Scenario) => void;
  loadScenarios: () => Promise<void>;
  loadResults: (scenarioId: string) => Promise<void>;
  clearError: () => void;
  continueCheckpoint: (edits?: Record<string, unknown>) => Promise<void>;
  setPipelineMode: (mode: PipelineMode) => void;
}

export function useSimulation(): UseSimulationReturn {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [simulationGeoJSON, setSimulationGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);
  const [simulationResults, setSimulationResults] = useState<SimulationAction[]>([]);
  const [reportMarkdown, setReportMarkdown] = useState("");
  const [checkpointData, setCheckpointData] = useState<CheckpointData | null>(null);
  const [pipelineMode, setPipelineMode] = useState<PipelineMode>("auto");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const loadResults = useCallback(async (scenarioId: string) => {
    try {
      const [geoRes, resultsRes, reportRes] = await Promise.allSettled([
        api.getGeoJSON(scenarioId),
        api.getResults(scenarioId),
        api.getReport(scenarioId),
      ]);

      if (geoRes.status === "fulfilled" && geoRes.value) {
        setSimulationGeoJSON(geoRes.value as GeoJSON.FeatureCollection);
      }

      if (resultsRes.status === "fulfilled" && resultsRes.value) {
        const data = resultsRes.value as { results?: { actions?: SimulationAction[] } };
        setSimulationResults(data.results?.actions ?? []);
      }

      if (reportRes.status === "fulfilled" && reportRes.value) {
        const data = reportRes.value as { report?: string };
        setReportMarkdown(data.report ?? "");
      }
    } catch (e) {
      if (process.env.NODE_ENV === "development") console.warn("loadResults failed", e);
    }
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadScenarios = useCallback(async () => {
    try {
      const list = await api.getScenarios();
      setScenarios(Array.isArray(list) ? list : []);
    } catch (e) {
      if (process.env.NODE_ENV === "development") console.warn("loadScenarios failed", e);
    }
  }, []);

  const pollStatus = useCallback(
    (scenarioId: string) => {
      stopPolling();

      const poll = async () => {
        try {
          const st = await api.getStatus(scenarioId);
          setPipelineStatus(st);

          if (st.status.startsWith("checkpoint:")) {
            stopPolling();
            setIsRunning(false);
            const cpData = await api.getCheckpoint(scenarioId);
            setCheckpointData(cpData);
            return;
          }

          if (st.status === "completed" || st.status === "failed") {
            stopPolling();
            setIsRunning(false);
            await loadScenarios();
            if (st.status === "completed") {
              await loadResults(scenarioId);
            }
            if (st.status === "failed" && st.error_message) {
              setError(st.error_message);
            }
          }
        } catch (e) {
          if (process.env.NODE_ENV === "development") console.warn("pollStatus failed", e);
        }
      };

      poll();
      pollRef.current = setInterval(poll, POLL_INTERVAL);
    },
    [stopPolling, loadScenarios, loadResults]
  );

  const createAndRun = useCallback(
    async (data: ScenarioFormData) => {
      setError(null);
      setIsRunning(true);
      setCheckpointData(null);
      setPipelineStatus({ status: "starting", seed_status: "pending", simulation_status: "pending" });

      const mode = data.mode ?? "auto";
      setPipelineMode(mode);

      try {
        const scenario = await api.createScenario(data);
        setActiveScenario(scenario);
        await api.generateSeed(scenario.id);
        await api.startSimulation(scenario.id, mode);
        pollStatus(scenario.id);
        await loadScenarios();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        setError(msg);
        setIsRunning(false);
        setPipelineStatus(null);
      }
    },
    [pollStatus, loadScenarios]
  );

  const continueCheckpoint = useCallback(
    async (edits?: Record<string, unknown>) => {
      const scenarioId = activeScenario?.id;
      if (!scenarioId) return;

      setError(null);
      setCheckpointData(null);
      setIsRunning(true);

      try {
        await api.continueSimulation(scenarioId, edits);
        pollStatus(scenarioId);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Continue failed";
        setError(msg);
        setIsRunning(false);
      }
    },
    [activeScenario, pollStatus]
  );

  const deleteScenario = useCallback(
    async (id: string) => {
      try {
        await api.deleteScenario(id);
        if (activeScenario?.id === id) {
          setActiveScenario(null);
          setPipelineStatus(null);
          stopPolling();
          setIsRunning(false);
        }
        await loadScenarios();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Delete failed";
        setError(msg);
      }
    },
    [activeScenario, stopPolling, loadScenarios]
  );

  const selectScenario = useCallback(
    (scenario: Scenario) => {
      stopPolling();
      setActiveScenario(scenario);
      setError(null);
      setSimulationGeoJSON(null);
      setSimulationResults([]);
      setReportMarkdown("");

      const isActive =
        scenario.status !== "completed" && scenario.status !== "failed" && scenario.status !== "created";

      if (isActive) {
        setIsRunning(true);
        pollStatus(scenario.id);
      } else {
        setIsRunning(false);
        setPipelineStatus({
          status: scenario.status,
          seed_status: scenario.seed_status,
          simulation_status: scenario.simulation_status,
        });
        if (scenario.status === "completed") {
          loadResults(scenario.id);
        }
        if (scenario.status === "failed") {
          api.getStatus(scenario.id).then((st) => {
            if (st.error_message) setError(st.error_message);
          }).catch(() => {});
        }
      }
    },
    [stopPolling, pollStatus, loadResults]
  );

  // Load scenarios on mount
  useEffect(() => {
    loadScenarios();
  }, [loadScenarios]);

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return {
    scenarios,
    activeScenario,
    pipelineStatus,
    isRunning,
    error,
    simulationGeoJSON,
    simulationResults,
    reportMarkdown,
    checkpointData,
    pipelineMode,
    createAndRun,
    deleteScenario,
    selectScenario,
    loadScenarios,
    loadResults,
    clearError,
    continueCheckpoint,
    setPipelineMode,
  };
}
