"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CheckpointData,
  PipelineMode,
  PipelineStatus,
  Scenario,
  ScenarioFormData,
  SimulationAction,
} from "@/types/simulation";
import * as api from "@/lib/gatewayApi";

const CHECKPOINT_NEXT_STATUS: Record<string, string> = {
  "checkpoint:seed": "simulating:ontology",
  "checkpoint:decision": "simulating:ontology",
  "checkpoint:ontology": "simulating:graph_build",
  "checkpoint:graph": "simulating:prepare",
  "checkpoint:profiles": "simulating:prepare",
  "checkpoint:config": "simulating:running",
  "checkpoint:geopolitics": "simulating:running",
};

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
  filteredScenarios: Scenario[] | null;
  setFilteredScenarios: (scenarios: Scenario[] | null) => void;
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
  const [filteredScenarios, setFilteredScenarios] = useState<Scenario[] | null>(null);
  const streamRef = useRef<EventSource | null>(null);

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
        const data = resultsRes.value as {
          events?: SimulationAction[];
          results?: { actions?: SimulationAction[] };
        };
        setSimulationResults(data.events ?? data.results?.actions ?? []);
      }

      if (reportRes.status === "fulfilled" && reportRes.value) {
        const data = reportRes.value as { content?: string; report?: string };
        setReportMarkdown(data.content ?? data.report ?? "");
      }
    } catch (e) {
      if (process.env.NODE_ENV === "development") console.warn("loadResults failed", e);
    }
  }, []);

  const stopStreaming = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
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

  const attachStream = useCallback((scenarioId: string) => {
    stopStreaming();
    const es = new EventSource(`/api/scenario/${scenarioId}/stream`);
    streamRef.current = es;
    setIsRunning(true);

    es.addEventListener("phase_change", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { phase: string };
      const statusMap: Record<string, string> = {
        analyzing: "simulating:ontology",
        building: "simulating:graph_build",
        configuring: "simulating:prepare",
        simulating: "simulating:running",
        reporting: "simulating:report",
        confirmation: "completed",
      };
      setPipelineStatus((prev) => ({
        status: statusMap[payload.phase] ?? "simulating:running",
        seed_status: prev?.seed_status ?? "completed",
        simulation_status: payload.phase === "confirmation" ? "completed" : "running",
      }));
    });

    es.addEventListener("intervention_required", () => {
      setPipelineStatus((prev) => ({
        status: "simulating:wargame:decision",
        seed_status: prev?.seed_status ?? "completed",
        simulation_status: "paused",
      }));
      setIsRunning(false);
    });

    es.addEventListener("report_ready", async () => {
      setPipelineStatus((prev) => ({
        status: "completed",
        seed_status: prev?.seed_status ?? "completed",
        simulation_status: "completed",
      }));
      setIsRunning(false);
      stopStreaming();
      await loadScenarios();
      await loadResults(scenarioId);
    });

    es.addEventListener("error", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { error?: string };
      setError(payload.error ?? "Simulation failed");
      setPipelineStatus((prev) => ({
        status: "failed",
        seed_status: prev?.seed_status ?? "completed",
        simulation_status: "failed",
      }));
      setIsRunning(false);
      stopStreaming();
    });

    es.onerror = () => {
      setIsRunning(false);
    };
  }, [loadResults, loadScenarios, stopStreaming]);

  const createAndRun = useCallback(async (data: ScenarioFormData) => {
    setError(null);
    setIsRunning(true);
    setCheckpointData(null);
    setPipelineStatus({ status: "starting", seed_status: "pending", simulation_status: "pending" });

    const mode = data.mode ?? "auto";
    setPipelineMode(mode);

    try {
      const scenario = await api.createScenario(data);
      setActiveScenario(scenario);
      setPipelineStatus({ status: "starting", seed_status: "generating", simulation_status: "pending" });
      await api.generateSeed(scenario.id);
      setPipelineStatus({ status: "starting", seed_status: "completed", simulation_status: "pending" });
      await api.startSimulation(scenario.id, mode);
      attachStream(scenario.id);
      await loadScenarios();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
      setIsRunning(false);
      setPipelineStatus(null);
    }
  }, [attachStream, loadScenarios]);

  const continueCheckpoint = useCallback(async (edits?: Record<string, unknown>) => {
    const scenarioId = activeScenario?.id;
    if (!scenarioId) return;

    setError(null);

    const nextStatus = CHECKPOINT_NEXT_STATUS[pipelineStatus?.status ?? ""];
    if (nextStatus) {
      setPipelineStatus((prev) => prev ? { ...prev, status: nextStatus } : prev);
    }

    setCheckpointData(null);
    setIsRunning(true);

    try {
      await api.continueSimulation(scenarioId, edits);
      attachStream(scenarioId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Continue failed";
      setError(msg);
      setIsRunning(false);
    }
  }, [activeScenario, attachStream, pipelineStatus]);

  const deleteScenario = useCallback(async (id: string) => {
    try {
      await api.deleteScenario(id);
      if (activeScenario?.id === id) {
        setActiveScenario(null);
        setPipelineStatus(null);
        stopStreaming();
        setIsRunning(false);
      }
      await loadScenarios();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      setError(msg);
    }
  }, [activeScenario, loadScenarios, stopStreaming]);

  const selectScenario = useCallback((scenario: Scenario) => {
    stopStreaming();
    setActiveScenario(scenario);
    setError(null);
    setSimulationGeoJSON(null);
    setSimulationResults([]);
    setReportMarkdown("");

    const isActive = scenario.status !== "completed" && scenario.status !== "failed" && scenario.status !== "created";

    if (isActive) {
      setIsRunning(true);
      api.getStatus(scenario.id).then((st) => {
        setPipelineStatus(st);
        attachStream(scenario.id);
      }).catch((e) => {
        if (process.env.NODE_ENV === "development") console.warn("Failed to load live status", e);
      });
      return;
    }

    setIsRunning(false);
    setPipelineStatus({
      status: scenario.status,
      seed_status: scenario.seed_status,
      simulation_status: scenario.simulation_status,
    });
    if (scenario.status === "completed") {
      void loadResults(scenario.id);
    }
    if (scenario.status === "failed") {
      api.getStatus(scenario.id).then((st) => {
        if (st.error_message) setError(st.error_message);
      }).catch((e) => {
        if (process.env.NODE_ENV === "development") console.warn("Failed to fetch error detail:", e);
      });
    }
  }, [attachStream, loadResults, stopStreaming]);

  useEffect(() => {
    loadScenarios();
  }, [loadScenarios]);

  useEffect(() => {
    return () => stopStreaming();
  }, [stopStreaming]);

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
    filteredScenarios,
    setFilteredScenarios,
  };
}
