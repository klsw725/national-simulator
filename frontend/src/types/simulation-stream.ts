export interface AgentAction {
  actor: string;
  action_type: string;
  target: string;
  intensity: "low" | "medium" | "high";
  reasoning: string;
  round?: number;
}

export interface DecisionOption {
  action_type: string;
  target: string;
  intensity: "low" | "medium" | "high";
  description: string;
  estimated_effect: {
    tension_delta: number;
    resource_cost: number;
  };
}

export interface CascadeChainEntry {
  from: string;
  to: string;
  depth: number;
}

export interface TriggerDetail {
  event_type: string;
  source_actor: string;
  target_actors: string[];
  magnitude: number;
  description: string;
  cascade_chain?: CascadeChainEntry[];
}

export interface GeopoliticalEventPayload {
  round: number;
  trigger_type: "cascade_reaction" | "high_intensity_military" | "tension_threshold_exceeded" | "direction_checkpoint" | "round_events";
  events: Array<{
    event_type: string;
    source_actor_id: string;
    target_actor_ids: string[];
    magnitude: number;
    description: string;
  }>;
}

export interface DecisionPointV2 {
  id: string;
  round: number;
  trigger: string;
  trigger_detail?: TriggerDetail | null;
  options: DecisionOption[];
}

export interface SimulationStreamState {
  phase: string;
  status: string;
  currentRound: number;
  maxRounds: number;
  recentActions: AgentAction[];
  tensionLevels: Record<string, number>;
  decisionPoint: DecisionPointV2 | null;
  latestGeopoliticalEvent: GeopoliticalEventPayload | null;
  reportId: string | null;
  error: string | null;
  isConnected: boolean;
}

export type SimulationStreamAction =
  | { type: "PHASE_CHANGE"; payload: { phase: string; progress: number } }
  | { type: "ROUND_COMPLETE"; payload: { round: number; actions_count: number; max_tension: number } }
  | { type: "AGENT_ACTION"; payload: AgentAction }
  | { type: "INTERVENTION"; payload: { decision_point: DecisionPointV2 } }
  | { type: "GEOPOLITICAL_EVENT"; payload: GeopoliticalEventPayload }
  | { type: "REPORT_READY"; payload: { report_id: string } }
  | { type: "ERROR"; payload: { error: string } }
  | { type: "CONNECTED" }
  | { type: "DISCONNECTED" };
