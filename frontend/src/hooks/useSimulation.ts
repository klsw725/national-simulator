"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Scenario, ScenarioFormData, PipelineStatus } from "@/types/simulation";
import * as api from "@/lib/gatewayApi";

const POLL_INTERVAL = 5_000;

export interface UseSimulationReturn {
  scenarios: Scenario[];
  activeScenario: Scenario | null;
  pipelineStatus: PipelineStatus | null;
  isRunning: boolean;
  error: string | null;
  createAndRun: (data: ScenarioFormData) => Promise<void>;
  deleteScenario: (id: string) => Promise<void>;
  selectScenario: (scenario: Scenario) => void;
  loadScenarios: () => Promise<void>;
  clearError: () => void;
}

export function useSimulation(): UseSimulationReturn {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearError = useCallback(() => setError(null), []);

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
    } catch {
      // non-critical — list may be empty on first use
    }
  }, []);

  const pollStatus = useCallback(
    (scenarioId: string) => {
      stopPolling();

      const poll = async () => {
        try {
          const st = await api.getStatus(scenarioId);
          setPipelineStatus(st);

          if (st.status === "completed" || st.status === "failed") {
            stopPolling();
            setIsRunning(false);
            await loadScenarios();
          }
        } catch {
          // keep polling on transient errors
        }
      };

      poll();
      pollRef.current = setInterval(poll, POLL_INTERVAL);
    },
    [stopPolling, loadScenarios]
  );

  const createAndRun = useCallback(
    async (data: ScenarioFormData) => {
      setError(null);
      setIsRunning(true);
      setPipelineStatus({ status: "starting", seed_status: "pending", simulation_status: "pending" });

      try {
        const scenario = await api.createScenario(data);
        setActiveScenario(scenario);
        await api.generateSeed(scenario.id);
        await api.startSimulation(scenario.id);
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
      }
    },
    [stopPolling, pollStatus]
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
    createAndRun,
    deleteScenario,
    selectScenario,
    loadScenarios,
    clearError,
  };
}
