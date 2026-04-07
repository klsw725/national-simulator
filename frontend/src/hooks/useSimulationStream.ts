"use client";

import { useEffect, useReducer, useRef } from "react";
import type {
  SimulationStreamState,
  SimulationStreamAction,
  AgentAction,
} from "@/types/simulation-stream";

const INITIAL_STATE: SimulationStreamState = {
  phase: "",
  status: "idle",
  currentRound: 0,
  maxRounds: 0,
  recentActions: [],
  tensionLevels: {},
  decisionPoint: null,
  latestGeopoliticalEvent: null,
  reportId: null,
  error: null,
  isConnected: false,
};

const MAX_RECENT_ACTIONS = 100;

function reducer(
  state: SimulationStreamState,
  action: SimulationStreamAction,
): SimulationStreamState {
  switch (action.type) {
    case "PHASE_CHANGE":
      return {
        ...state,
        phase: action.payload.phase,
        status: action.payload.phase === "confirmation" ? "completed" : "running",
      };
    case "ROUND_COMPLETE":
      return {
        ...state,
        currentRound: action.payload.round,
        tensionLevels: { ...state.tensionLevels, max: action.payload.max_tension },
      };
    case "AGENT_ACTION": {
      const next = [...state.recentActions, action.payload];
      return {
        ...state,
        recentActions: next.length > MAX_RECENT_ACTIONS ? next.slice(-MAX_RECENT_ACTIONS) : next,
      };
    }
    case "INTERVENTION":
      return {
        ...state,
        phase: "decision",
        decisionPoint: action.payload.decision_point,
        status: "paused",
      };
    case "GEOPOLITICAL_EVENT":
      return {
        ...state,
        latestGeopoliticalEvent: action.payload,
      };
    case "REPORT_READY":
      return {
        ...state,
        phase: "confirmation",
        reportId: action.payload.report_id,
        status: "completed",
      };
    case "ERROR":
      return { ...state, error: action.payload.error, status: "failed" };
    case "CONNECTED":
      return { ...state, isConnected: true };
    case "DISCONNECTED":
      return { ...state, isConnected: false };
    default:
      return state;
  }
}

export function useSimulationStream(scenarioId: string | null) {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!scenarioId) return;

    const es = new EventSource(`/api/scenario/${scenarioId}/stream`);
    esRef.current = es;

    es.onopen = () => dispatch({ type: "CONNECTED" });
    es.onerror = () => dispatch({ type: "DISCONNECTED" });

    es.addEventListener("phase_change", (e) => {
      dispatch({ type: "PHASE_CHANGE", payload: JSON.parse(e.data) });
    });

    es.addEventListener("round_complete", (e) => {
      dispatch({ type: "ROUND_COMPLETE", payload: JSON.parse(e.data) });
    });

    es.addEventListener("agent_action", (e) => {
      const data = JSON.parse(e.data) as AgentAction;
      dispatch({ type: "AGENT_ACTION", payload: data });
    });

    es.addEventListener("intervention_required", (e) => {
      dispatch({ type: "INTERVENTION", payload: JSON.parse(e.data) });
    });

    es.addEventListener("geopolitical_event", (e) => {
      dispatch({ type: "GEOPOLITICAL_EVENT", payload: JSON.parse(e.data) });
    });

    es.addEventListener("report_ready", (e) => {
      dispatch({ type: "REPORT_READY", payload: JSON.parse(e.data) });
    });

    es.addEventListener("error", (e) => {
      if (e instanceof MessageEvent) {
        dispatch({ type: "ERROR", payload: JSON.parse(e.data) });
      }
    });

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [scenarioId]);

  return state;
}
