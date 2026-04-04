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

export interface DecisionPointV2 {
  id: string;
  round: number;
  trigger: string;
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
  reportId: string | null;
  error: string | null;
  isConnected: boolean;
}

export type SimulationStreamAction =
  | { type: "PHASE_CHANGE"; payload: { phase: string; progress: number } }
  | { type: "ROUND_COMPLETE"; payload: { round: number; actions_count: number; max_tension: number } }
  | { type: "AGENT_ACTION"; payload: AgentAction }
  | { type: "INTERVENTION"; payload: { decision_point: DecisionPointV2 } }
  | { type: "REPORT_READY"; payload: { report_id: string } }
  | { type: "ERROR"; payload: { error: string } }
  | { type: "CONNECTED" }
  | { type: "DISCONNECTED" };
