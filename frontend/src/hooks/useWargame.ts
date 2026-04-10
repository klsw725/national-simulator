"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  WargamePhase,
  WargameState,
  WargameLens,
  ActorState,
  RoundBriefing,
  DecisionPoint,
} from "@/types/simulation";
import { getWargameStatus } from "@/lib/api/wargameApi";

const SSE_RECONNECT_DELAY = 3_000;
const SSE_MAX_RECONNECT_ATTEMPTS = 4;

function createInitialState(totalRounds: number): WargameState {
  return {
    phase: "simulation",
    round: 1,
    totalRounds,
    role: "actor_role",
    actorId: null,
    tension: 0,
    actorStates: {},
    briefing: null,
    decisionPoint: null,
  };
}

function toActorStates(data: unknown): Record<string, ActorState> | null {
  if (!data || typeof data !== "object") return null;
  const payload = data as {
    actorStates?: Record<string, ActorState>;
    actor_states?: Record<string, ActorState>;
  };
  return payload.actorStates ?? payload.actor_states ?? null;
}

function toBriefing(data: unknown): RoundBriefing | null {
  if (!data || typeof data !== "object") return null;
  const payload = data as { briefing?: RoundBriefing };
  return payload.briefing ?? null;
}

function toDecisionPoint(data: unknown): DecisionPoint | null {
  if (!data || typeof data !== "object") return null;
  const payload = data as { decisionPoint?: DecisionPoint; decision_point?: DecisionPoint };
  return payload.decisionPoint ?? payload.decision_point ?? null;
}

function toWargameState(
  prev: WargameState,
  data: Partial<WargameState>,
  totalRounds: number,
): WargameState {
  const phase = data.phase ?? prev.phase;
  const nextRound = data.round ?? prev.round;
  const nextTotalRounds = data.totalRounds ?? prev.totalRounds ?? totalRounds;
  return {
    phase,
    round: nextRound,
    totalRounds: nextTotalRounds,
    role: data.role ?? prev.role,
    actorId: data.actorId ?? prev.actorId,
    tension: typeof data.tension === "number" ? data.tension : prev.tension,
    actorStates: data.actorStates ?? prev.actorStates,
    briefing: data.briefing ?? (phase === "briefing" ? prev.briefing : null),
    decisionPoint: data.decisionPoint ?? (phase === "decision" ? prev.decisionPoint : null),
  };
}

function upsertTension(history: number[], round: number, tension: number): number[] {
  const index = Math.max(0, round - 1);
  const next = history.slice(0, Math.max(history.length, index + 1));
  while (next.length <= index) {
    next.push(next[next.length - 1] ?? tension);
  }
  if (next[index] === tension) return history;
  next[index] = tension;
  return next;
}

export interface DecisionRecord {
  round: number;
  label: string;
  outcome: string;
}

export interface RoundSnapshot {
  round: number;
  tension: number;
  actorStates: WargameState["actorStates"];
}

export interface UseWargameReturn {
  state: WargameState;
  activeLens: WargameLens;
  setActiveLens: (lens: WargameLens) => void;
  isConnected: boolean;
  isMockMode: boolean;
  advancePhase: () => void;
  setPhase: (phase: WargamePhase) => void;
  tensionHistory: number[];
  decisionHistory: DecisionRecord[];
  isComplete: boolean;
  setIsComplete: (v: boolean) => void;
  showDebrief: boolean;
  setShowDebrief: (v: boolean) => void;
  recordDecision: (record: DecisionRecord) => void;
  getSnapshotForRound: (round: number | null) => RoundSnapshot | null;
  refreshState: () => Promise<void>;
}

export function useWargame(
  scenarioId: string | null,
  totalRounds: number = 8,
): UseWargameReturn {
  const [state, setState] = useState<WargameState>(() => createInitialState(totalRounds));
  const [activeLens, setActiveLens] = useState<WargameLens>("military");
  const [isConnected, setIsConnected] = useState(false);
  const [tensionHistory, setTensionHistory] = useState<number[]>([]);
  const [decisionHistory, setDecisionHistory] = useState<DecisionRecord[]>([]);
  const [isComplete, setIsCompleteRaw] = useState(false);
  const [showDebrief, setShowDebrief] = useState(false);
  const [roundSnapshots, setRoundSnapshots] = useState<Record<number, RoundSnapshot>>({});

  const setIsComplete = useCallback((v: boolean) => {
    setIsCompleteRaw(v);
    if (v) setShowDebrief(true);
  }, []);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isMockMode = false;

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectRef.current) {
      clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
  }, []);

  const applyIncomingState = useCallback((data: Partial<WargameState>) => {
    setState((prev) => {
      const next = toWargameState(prev, data, totalRounds);
      setRoundSnapshots((snapshots) => ({
        ...snapshots,
        [next.round]: {
          round: next.round,
          tension: next.tension,
          actorStates: next.actorStates,
        },
      }));
      setTensionHistory((prevHistory) => upsertTension(prevHistory, next.round, next.tension));
      if (next.phase === "confirmation" && next.round >= next.totalRounds) {
        setIsComplete(true);
      }
      return next;
    });
  }, [setIsComplete, totalRounds]);

  const refreshState = useCallback(async () => {
    if (!scenarioId) return;
    const data = await getWargameStatus(scenarioId);
    if ((data.phase as string) === "completed") {
      setIsComplete(true);
      setShowDebrief(true);
      return;
    }
    applyIncomingState(data);
  }, [scenarioId, applyIncomingState, setIsComplete]);

  const handleSSEEvent = useCallback((eventType: string, payload: Record<string, unknown>) => {
    try {
      switch (eventType) {
        case "phase_change": {
          applyIncomingState({
            phase: payload.phase as WargamePhase,
            round: typeof payload.round === "number" ? payload.round : undefined,
            tension: typeof payload.tension === "number" ? payload.tension : undefined,
            actorStates: toActorStates(payload) ?? undefined,
          });
          break;
        }

        case "round_complete": {
          applyIncomingState({
            phase: "simulation",
            round: typeof payload.round === "number" ? payload.round : undefined,
            tension: typeof payload.max_tension === "number" ? payload.max_tension : undefined,
            actorStates: toActorStates(payload) ?? undefined,
          });
          void refreshState().catch(() => {});
          break;
        }

        case "intervention_required": {
          const briefing = toBriefing(payload);
          const decisionPoint = toDecisionPoint(payload);
          applyIncomingState({
            phase: briefing ? "briefing" : "decision",
            round: typeof payload.round === "number" ? payload.round : undefined,
            tension: typeof payload.tension === "number" ? payload.tension : undefined,
            actorStates: toActorStates(payload) ?? undefined,
            briefing: briefing ?? undefined,
            decisionPoint: decisionPoint ?? undefined,
          });
          void refreshState().catch(() => {});
          break;
        }

        case "agent_action":
          if (typeof payload.tension === "number" || toActorStates(payload)) {
            applyIncomingState({
              tension: typeof payload.tension === "number" ? payload.tension : undefined,
              actorStates: toActorStates(payload) ?? undefined,
            });
          }
          break;

        case "report_ready":
          applyIncomingState({
            phase: "confirmation",
            round: typeof payload.round === "number" ? payload.round : undefined,
            totalRounds: typeof payload.totalRounds === "number" ? payload.totalRounds : undefined,
            tension: typeof payload.tension === "number" ? payload.tension : undefined,
            actorStates: toActorStates(payload) ?? undefined,
          });
          setIsComplete(true);
          setShowDebrief(true);
          break;

        default:
          break;
      }
    } catch {
      if (process.env.NODE_ENV === "development") {
        console.warn("useWargame: failed to parse SSE event");
      }
    }
  }, [applyIncomingState, setIsComplete]);

  const connectSSE = useCallback(() => {
    if (!scenarioId) return;

    try {
      const es = new EventSource(`/api/scenario/${scenarioId}/stream`);
      eventSourceRef.current = es;

      const eventTypes = [
        "phase_change",
        "round_complete",
        "agent_action",
        "intervention_required",
        "report_ready",
      ];

      for (const type of eventTypes) {
        es.addEventListener(type, (event: Event) => {
          const message = event as MessageEvent;
          try {
            const payload = message.data ? (JSON.parse(message.data) as Record<string, unknown>) : {};
            handleSSEEvent(type, payload);
          } catch {
            if (process.env.NODE_ENV === "development") {
              console.warn("useWargame: invalid SSE payload");
            }
          }
        });
      }

      es.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        void refreshState().catch(() => {});
      };

      es.onerror = () => {
        setIsConnected(false);
        es.close();
        eventSourceRef.current = null;

        reconnectAttemptsRef.current += 1;
        if (reconnectAttemptsRef.current <= SSE_MAX_RECONNECT_ATTEMPTS) {
          const delay = SSE_RECONNECT_DELAY * reconnectAttemptsRef.current;
          reconnectRef.current = setTimeout(() => connectSSE(), delay);
        }
      };
    } catch {
      setIsConnected(false);
    }
  }, [scenarioId, handleSSEEvent, refreshState]);

  const setPhase = useCallback((phase: WargamePhase) => {
    setState((prev) => ({ ...prev, phase }));
  }, []);

  const recordDecision = useCallback((record: DecisionRecord) => {
    setDecisionHistory((prev) => {
      if (prev.some((d) => d.round === record.round)) return prev;
      return [...prev, record];
    });
  }, []);

  const getSnapshotForRound = useCallback((round: number | null) => {
    if (round == null) return null;
    const index = round - 1;
    const tension = tensionHistory[index];
    if (typeof tension !== "number") {
      return roundSnapshots[round] ?? null;
    }
    return {
      round,
      tension,
      actorStates: roundSnapshots[round]?.actorStates ?? state.actorStates,
    };
  }, [roundSnapshots, state.actorStates, tensionHistory]);

  const advancePhase = useCallback(() => {
    void refreshState().catch(() => {});
  }, [refreshState]);

  useEffect(() => {
    cleanup();
    if (!scenarioId) {
      setIsConnected(false);
      return;
    }

    void refreshState().catch(() => {});
    connectSSE();
    return cleanup;
  }, [scenarioId, connectSSE, cleanup, refreshState]);

  useEffect(() => {
    setState(createInitialState(totalRounds));
    setTensionHistory([]);
    setDecisionHistory([]);
    setIsCompleteRaw(false);
    setShowDebrief(false);
    setRoundSnapshots({});
  }, [totalRounds]);

  return {
    state,
    activeLens,
    setActiveLens,
    isConnected,
    isMockMode,
    advancePhase,
    setPhase,
    tensionHistory,
    decisionHistory,
    isComplete,
    setIsComplete,
    showDebrief,
    setShowDebrief,
    recordDecision,
    getSnapshotForRound,
    refreshState,
  };
}
