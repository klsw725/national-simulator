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

const POLL_INTERVAL = 5_000;
const SSE_RECONNECT_DELAY = 3_000;
const SSE_MAX_RECONNECT_ATTEMPTS = 4;
const SSE_HEARTBEAT_TIMEOUT = 300_000;

const MOCK_ACTORS: Record<string, ActorState> = {
  usa: { actor_id: "usa", name: "미국", threat_perception: 0.4, domestic_pressure: 0.3, resource_level: 0.85 },
  chn: { actor_id: "chn", name: "중국", threat_perception: 0.55, domestic_pressure: 0.45, resource_level: 0.7 },
  kor: { actor_id: "kor", name: "한국", threat_perception: 0.6, domestic_pressure: 0.5, resource_level: 0.6 },
  jpn: { actor_id: "jpn", name: "일본", threat_perception: 0.35, domestic_pressure: 0.25, resource_level: 0.75 },
};

function createInitialState(totalRounds: number): WargameState {
  return {
    phase: "simulation",
    round: 1,
    totalRounds,
    role: "actor_role",
    actorId: "usa",
    tension: 0.3,
    actorStates: MOCK_ACTORS,
    briefing: null,
    decisionPoint: null,
  };
}

function createMockBriefing(round: number): RoundBriefing {
  return {
    round,
    key_events: [
      {
        type: "군사 이동",
        description: "중국 해군 함정 3척이 남중국해 스프래틀리 군도 인근으로 이동 중",
        severity: "critical",
      },
      {
        type: "외교 성명",
        description: "필리핀 대통령이 영유권 분쟁에 대한 공식 항의 성명을 발표",
        severity: "high",
      },
      {
        type: "경제",
        description: "ASEAN 긴급 무역 회의가 안보 상황으로 인해 연기됨",
        severity: "medium",
      },
    ],
    state_deltas: {
      tension: 0.15,
      domestic_pressure: 0.05,
      resource_level: 0,
    },
    previous_decision_outcome:
      round > 1
        ? `Round ${round - 1}에서 "외교적 대응"을 선택 → 긴장도 소폭 완화되었으나, 국내 여론은 강경 대응을 요구`
        : null,
    social_media_summary: {
      total_posts: 42 + round * 10,
      top_topics: ["군사훈련", "동맹관계", "영유권분쟁", "경제제재"],
    },
  };
}

function createMockDecisionPoint(sid: string, round: number): DecisionPoint {
  return {
    id: `mock-dp-r${round}`,
    scenario_id: sid,
    type: "geopolitics_actor_response",
    options: [
      {
        id: "military",
        label: "군사 대응",
        description: "합동 순찰 강화 및 군사 자산 전진 배치",
        confidence: 0.7,
        reasoning: "확전 위험이 있지만 동맹 신뢰를 확보할 수 있습니다",
        data: {
          category: "military",
          engine_recommended: true,
          delta_tension: 0.15,
          delta_threat_perception: 0.1,
          delta_resource_level: -0.05,
          narrative:
            "남중국해 일대에서 긴장이 고조되고 있습니다. 중국 해군의 움직임에 대한 대응이 필요합니다.",
        },
      },
      {
        id: "diplomatic",
        label: "외교적 대응",
        description: "다자 외교 채널을 통한 협상 개시",
        confidence: 0.6,
        reasoning: "시간이 걸리지만 장기적 안정을 기대할 수 있습니다",
        data: {
          category: "diplomatic",
          delta_tension: -0.1,
          delta_domestic_pressure: 0.05,
          delta_resource_level: -0.02,
        },
      },
      {
        id: "economic",
        label: "경제적 대응",
        description: "무역 제한 및 경제 압박 강화",
        confidence: 0.5,
        reasoning: "경제적 레버리지를 활용하되, 글로벌 공급망에 영향을 줄 수 있습니다",
        data: {
          category: "economic",
          delta_tension: 0.05,
          delta_domestic_pressure: -0.05,
          delta_resource_level: -0.1,
        },
      },
      {
        id: "maintain",
        label: "현상 유지",
        description: "현재 상황을 관망하며 추가 정보 수집",
        confidence: 0.4,
        reasoning: "리스크는 낮지만 기회를 놓칠 수 있습니다",
        data: {
          category: "maintain",
          delta_tension: 0.02,
          delta_domestic_pressure: 0.08,
          delta_resource_level: 0.05,
        },
      },
    ],
    recommended: "military",
    allow_custom: false,
    status: "pending",
    selected_option_id: null,
    custom_data: null,
    created_at: new Date().toISOString(),
    resolved_at: null,
  };
}

function extractFinalTension(data: unknown): number | null {
  if (!data || typeof data !== "object") return null;
  const payload = data as { final_tension?: unknown; final_state?: { tension?: unknown } };
  if (typeof payload.final_tension === "number") return payload.final_tension;
  if (typeof payload.final_state?.tension === "number") return payload.final_state.tension;
  return null;
}

function mergeBackendState(prev: WargameState, data: Partial<WargameState>): WargameState {
  const phase = data.phase ?? prev.phase;
  const isDecisionPhase = phase === "briefing" || phase === "decision";
  return {
    ...prev,
    ...data,
    phase,
    briefing: isDecisionPhase ? (data.briefing ?? prev.briefing) : null,
    decisionPoint: isDecisionPhase ? (data.decisionPoint ?? prev.decisionPoint) : null,
  };
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
  const [isMockMode, setIsMockMode] = useState(true);
  const [tensionHistory, setTensionHistory] = useState<number[]>([0.3]);
  const [decisionHistory, setDecisionHistory] = useState<DecisionRecord[]>([]);
  const [isComplete, setIsCompleteRaw] = useState(false);
  const [showDebrief, setShowDebrief] = useState(false);
  const [roundSnapshots, setRoundSnapshots] = useState<Record<number, RoundSnapshot>>({});

  const setIsComplete = useCallback((v: boolean) => {
    setIsCompleteRaw(v);
    if (v) setShowDebrief(true);
  }, []);

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hydrationDoneRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (reconnectRef.current) {
      clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
    if (heartbeatRef.current) {
      clearTimeout(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const hydrateFromBackend = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const data = await getWargameStatus(scenarioId);
      setState((prev) => mergeBackendState(prev, data));
      if (typeof data.tension === "number") {
        setTensionHistory((prev) => {
          if (prev.length <= 1) return [data.tension];
          return prev;
        });
      }
      if (
        data.phase === "confirmation" &&
        !data.decisionPoint &&
        data.round >= data.totalRounds
      ) {
        setIsComplete(true);
      }
      setIsMockMode(false);
      hydrationDoneRef.current = true;
    } catch {
      // backend not ready yet — stay in mock mode
    }
  }, [scenarioId]);

  const handleSSEEvent = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      const eventType = (event as MessageEvent & { type: string }).type || data.type;

      switch (eventType) {
        case "phase_change":
          setState((prev) => ({
            ...prev,
            phase: data.phase as WargamePhase,
            round: data.round ?? prev.round,
            tension: data.tension ?? prev.tension,
            // FIX: phase_change arrives before decision_required — clear stale data to prevent flash
            ...(data.phase === "briefing" || data.phase === "simulation"
              ? { briefing: null, decisionPoint: null }
              : {}),
          }));
          break;

        case "round_complete":
          setState((prev) => {
            const nextTension = data.tension ?? prev.tension;
            const nextRound = data.round ?? prev.round + 1;
            const nextActorStates = data.actor_states ?? prev.actorStates;
            setRoundSnapshots((snapshots) => ({
              ...snapshots,
              [nextRound]: {
                round: nextRound,
                tension: nextTension,
                actorStates: nextActorStates,
              },
            }));
            return {
              ...prev,
              round: nextRound,
              tension: nextTension,
              actorStates: nextActorStates,
            };
          });
          setTensionHistory((prev) => [...prev, data.tension ?? prev[prev.length - 1] ?? 0.3]);
          break;

        case "decision_required":
          if (data.decision_point || data.briefing) {
            setState((prev) => ({
              ...prev,
              phase: data.briefing ? "briefing" : "decision",
              briefing: data.briefing ?? prev.briefing,
              decisionPoint: data.decision_point ?? prev.decisionPoint,
            }));
          } else {
            void hydrateFromBackend();
          }
          break;

        case "decision_resolved": {
          const resolvedLabel = data.label ?? "결정";
          const resolvedOutcome = data.outcome ?? "결정 반영됨";
          const resolvedRound = data.round ?? 0;
          setState((prev) => ({
            ...prev,
            phase: "confirmation",
            decisionPoint: null,
          }));
          setDecisionHistory((prev) => {
            const effectiveRound = resolvedRound || prev.length + 1;
            if (prev.some((d) => d.round === effectiveRound)) return prev;
            return [...prev, { round: effectiveRound, label: resolvedLabel, outcome: resolvedOutcome }];
          });
          break;
        }

        case "decision_auto_completed": {
          const resolvedRound = data.round ?? 0;
          setState((prev) => ({
            ...prev,
            phase: "confirmation",
            briefing: null,
            decisionPoint: null,
          }));
          setDecisionHistory((prev) => {
            const effectiveRound = resolvedRound || prev.length + 1;
            if (prev.some((d) => d.round === effectiveRound)) return prev;
            return [
              ...prev,
              {
                round: effectiveRound,
                label: data.selected ?? "자동 결정",
                outcome: data.outcome ?? "TTL 만료로 자동 결정되었습니다.",
              },
            ];
          });
          break;
        }

        case "round_stats":
          setState((prev) => ({
            ...prev,
            tension: data.tension ?? prev.tension,
            actorStates: data.actor_states ?? prev.actorStates,
          }));
          break;

        case "simulation_complete":
          {
            const finalTension = extractFinalTension(data);
          setState((prev) => ({
            ...prev,
            phase: "confirmation",
            round: data.total_rounds ?? data.final_state?.round ?? prev.totalRounds,
            totalRounds: data.total_rounds ?? data.final_state?.total_rounds ?? prev.totalRounds,
            tension: finalTension ?? prev.tension,
            actorStates:
              (data.final_state && typeof data.final_state === "object" && data.final_state.actor_states) ??
              prev.actorStates,
          }));
          if (finalTension !== null) {
            setTensionHistory((prev) => {
              const last = prev[prev.length - 1];
              return last === finalTension ? prev : [...prev, finalTension];
            });
          }
          setIsComplete(true);
          break;
          }
      }
    } catch {
      if (process.env.NODE_ENV === "development") {
        console.warn("useWargame: failed to parse SSE event");
      }
    }
  }, [hydrateFromBackend]);

  const startPollingFallback = useCallback(() => {
    if (pollRef.current || !scenarioId) return;

    pollRef.current = setInterval(() => {
      getWargameStatus(scenarioId)
        .then((data) => {
          setState((prev) => mergeBackendState(prev, data));
          if (typeof data.tension === "number") {
            setTensionHistory((prev) => {
              const last = prev[prev.length - 1];
              if (last !== data.tension) return [...prev, data.tension];
              return prev;
            });
          }
          if (
            data.phase === "confirmation" &&
            !data.decisionPoint &&
            data.round >= data.totalRounds
          ) {
            setIsComplete(true);
          }
          setIsMockMode(false);
        })
        .catch(() => {});
    }, POLL_INTERVAL);
  }, [scenarioId]);

  const resetHeartbeatTimer = useCallback(() => {
    if (heartbeatRef.current) clearTimeout(heartbeatRef.current);
    heartbeatRef.current = setTimeout(() => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsConnected(false);
      reconnectAttemptsRef.current += 1;
      if (reconnectAttemptsRef.current <= SSE_MAX_RECONNECT_ATTEMPTS) {
        const delay = SSE_RECONNECT_DELAY * reconnectAttemptsRef.current;
        reconnectRef.current = setTimeout(() => connectSSE(), delay);
      } else {
        setIsMockMode(true);
        startPollingFallback();
      }
    }, SSE_HEARTBEAT_TIMEOUT);
  }, [startPollingFallback]);

  const connectSSE = useCallback(() => {
    if (!scenarioId) return;

    cleanup();

    void hydrateFromBackend();

    try {
      const es = new EventSource(`/api/scenario/${scenarioId}/events`);
      eventSourceRef.current = es;

      const eventTypes = [
        "phase_change",
        "round_complete",
        "decision_required",
        "decision_resolved",
        "decision_auto_completed",
        "round_stats",
        "simulation_complete",
      ];
      for (const type of eventTypes) {
        es.addEventListener(type, (event: Event) => {
          resetHeartbeatTimer();
          handleSSEEvent(event as MessageEvent);
        });
      }

      es.addEventListener("heartbeat", () => {
        resetHeartbeatTimer();
      });

      es.onmessage = () => {
        resetHeartbeatTimer();
      };

      es.onopen = () => {
        setIsConnected(true);
        setIsMockMode(false);
        reconnectAttemptsRef.current = 0;
        resetHeartbeatTimer();
      };

      es.onerror = () => {
        setIsConnected(false);
        es.close();
        eventSourceRef.current = null;

        reconnectAttemptsRef.current += 1;
        if (reconnectAttemptsRef.current <= SSE_MAX_RECONNECT_ATTEMPTS) {
          const delay = SSE_RECONNECT_DELAY * reconnectAttemptsRef.current;
          reconnectRef.current = setTimeout(() => connectSSE(), delay);
        } else {
          setIsMockMode(true);
          startPollingFallback();
        }
      };
    } catch {
      setIsMockMode(true);
      startPollingFallback();
    }
  }, [scenarioId, cleanup, handleSSEEvent, hydrateFromBackend, startPollingFallback, resetHeartbeatTimer]);

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
    return roundSnapshots[round] ?? null;
  }, [roundSnapshots]);

  const advancePhase = useCallback(() => {
    setState((prev) => {
      const phases: WargamePhase[] = ["simulation", "briefing", "decision", "confirmation"];
      const idx = phases.indexOf(prev.phase);
      const nextPhase = phases[(idx + 1) % phases.length];
      const nextRound = nextPhase === "simulation" ? Math.min(prev.round + 1, prev.totalRounds) : prev.round;
      const enteringBriefing = nextPhase === "briefing";
      const backToSimulation = nextPhase === "simulation";
      const newTension = Math.min(1, prev.tension + (Math.random() * 0.1 - 0.03));

      if (backToSimulation) {
        setTensionHistory((h) => [...h, newTension]);
      }

      if (nextRound >= prev.totalRounds && backToSimulation) {
        setIsComplete(true);
      }

      return {
        ...prev,
        phase: nextPhase,
        round: nextRound,
        tension: newTension,
        briefing: enteringBriefing
          ? createMockBriefing(prev.round)
          : backToSimulation
            ? null
            : prev.briefing,
        decisionPoint: enteringBriefing
          ? createMockDecisionPoint(scenarioId ?? "mock", prev.round)
          : backToSimulation
            ? null
            : prev.decisionPoint,
      };
    });
  }, [scenarioId]);

  useEffect(() => {
    if (!scenarioId) {
      cleanup();
      setIsConnected(false);
      setIsMockMode(true);
      hydrationDoneRef.current = false;
      return;
    }

    connectSSE();
    return cleanup;
  }, [scenarioId, connectSSE, cleanup]);

  useEffect(() => {
    setState(createInitialState(totalRounds));
    setTensionHistory([0.3]);
    setDecisionHistory([]);
    setIsCompleteRaw(false);
    setShowDebrief(false);
    setRoundSnapshots({});
    hydrationDoneRef.current = false;
  }, [totalRounds]);

  useEffect(() => {
    if (!isMockMode || state.phase !== "confirmation" || isComplete) return;

    const timer = setTimeout(() => {
      setState((prev) => {
        const nextRound = Math.min(prev.round + 1, prev.totalRounds);
        if (prev.round >= prev.totalRounds) {
          setIsComplete(true);
          return prev;
        }
        return {
          ...prev,
          phase: "simulation",
          round: nextRound,
          briefing: null,
          decisionPoint: null,
        };
      });
    }, 2000);

    return () => clearTimeout(timer);
  }, [isMockMode, state.phase, state.round, isComplete, setIsComplete]);

  const briefingRound = state.briefing?.round ?? -1;
  useEffect(() => {
    if (!isMockMode || state.phase !== "simulation" || state.round < 3) return;
    if (briefingRound === state.round) return;

    const timer = setTimeout(() => {
      setState((prev) => {
        if (prev.phase !== "simulation") return prev;
        return {
          ...prev,
          phase: "briefing",
          briefing: createMockBriefing(prev.round),
          decisionPoint: createMockDecisionPoint(scenarioId ?? "mock", prev.round),
        };
      });
    }, 2000);

    return () => clearTimeout(timer);
  }, [isMockMode, state.phase, state.round, briefingRound, scenarioId]);

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
    refreshState: hydrateFromBackend,
  };
}
