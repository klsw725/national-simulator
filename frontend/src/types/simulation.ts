export interface SimulationParams {
  platform: string;
  simulation_hours: number;
  simulation_requirement: string | null;
  geopolitics_enabled: boolean;
  geopolitics_mode?: GeopoliticsMode;
  player_actor_id?: string;
  web_search_enabled: boolean;
}

export interface Scenario {
  id: string;
  name: string;
  region_bbox: number[];
  region_name: string;
  question: string;
  max_rounds: number;
  data_sources: string[];
  simulation_params: SimulationParams;
  status: string;
  seed_status: string;
  simulation_status: string;
  created_at: string;
  updated_at: string;
}

export type PipelineMode = 'auto' | 'checkpoint' | 'interactive';

export interface ScenarioFormData {
  name: string;
  region: { bbox: [number, number, number, number]; name: string };
  question: string;
  max_rounds: number;
  data_sources: string[];
  mode: PipelineMode;
  simulation_params?: {
    platform: string;
    simulation_hours: number;
    simulation_requirement?: string;
    geopolitics_enabled: boolean;
    geopolitics_mode?: GeopoliticsMode;
    player_actor_id?: string;
    web_search_enabled: boolean;
  };
}

export interface PipelineStep {
  label: string;
  icon: string;
  status: "pending" | "running" | "completed" | "failed";
}

export interface PipelineStatus {
  status: string;
  seed_status: string;
  simulation_status: string;
}

export interface SimulationAction {
  agent_name: string;
  action_type: string;
  geopolitics_action?: string;
  geopolitics_label?: string;
  action_args: { content?: string; [key: string]: unknown };
  round_num: number;
}

export interface CheckpointData {
  scenario_id: string;
  result_id: string;
  status: string;
  step: string;      // "seed" | "ontology" | "graph" | "profiles" | "config"
  editable: boolean;
  data: Record<string, unknown> | null;
  pipeline_mode: string;
}

export interface LiveStats {
  simulation_id?: string;
  runner_status: string;
  current_round: number;
  total_rounds: number;
  progress_percent: number;
  twitter_actions_count: number;
  total_actions_count: number;
}

export interface LiveAction {
  round_num: number;
  timestamp: string;
  platform: string;
  agent_id: number;
  agent_name: string;
  action_type: string;
  action_args: { content?: string; [key: string]: unknown };
  success: boolean;
}

export interface GraphNode {
  uuid: string;
  name: string;
  entityType?: string;
  labels: string[];
  attributes: Record<string, unknown>;
  summary?: string;
}

export interface GraphEdge {
  uuid?: string;
  source_node_uuid: string;
  target_node_uuid: string;
  name: string;
  fact?: string;
  fact_type?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
}

export interface GraphTaskStatus {
  task_id?: string;
  status: string;
  progress: number;
  message?: string;
}

export interface LiveProfiles {
  simulation_id?: string;
  platform: string;
  count: number;
  total_expected: number;
  is_generating: boolean;
  profiles: Array<Record<string, unknown>>;
}

export interface LiveConfig {
  simulation_id?: string;
  file_exists: boolean;
  is_generating: boolean;
  generation_stage?: string;
  config_generated?: boolean;
  summary?: {
    total_agents: number;
    simulation_hours: number;
    initial_posts_count: number;
  };
}

export interface NodeDetail {
  id: string;
  name: string;
  type: string;
  labels: string[];
  attributes: Record<string, unknown>;
  relationships: {
    targetName: string;
    type: string;
    direction: "outgoing" | "incoming";
  }[];
}

export interface GraphFilters {
  entityTypes: string[];
  relationTypes: string[];
}

export interface DecisionOption {
  id: string;
  label: string;
  description: string;
  confidence: number;
  reasoning: string;
  data: Record<string, unknown>;
}

export type DecisionPointType =
  | "seed_selection"
  | "actor_configuration"
  | "parameter_recommendation"
  | "geopolitics_actor_response"
  | "geopolitics_direction";

export type GeopoliticsMode = "auto" | "actor_role" | "game_master";

export interface DecisionPoint {
  id: string;
  scenario_id: string;
  type: DecisionPointType;
  options: DecisionOption[];
  recommended: string;
  allow_custom: boolean;
  status: "pending" | "resolved";
  selected_option_id: string | null;
  custom_data: Record<string, unknown> | null;
  created_at: string;
  resolved_at: string | null;
}

export interface InterviewRequest {
  agent_id?: number;
  prompt: string;
  platform?: string;
  timeout?: number;
}

export interface InterviewResult {
  agent_id: number;
  agent_name?: string;
  prompt: string;
  response?: string;
  platform?: string;
  timestamp?: string;
  platforms?: Record<string, { agent_id: number; response: string; platform: string }>;
}

export interface InterviewHistoryItem {
  command_id: string;
  agent_id: number;
  prompt: string;
  result: InterviewResult;
  timestamp: string;
}

export interface EnvStatus {
  simulation_id: string;
  env_alive: boolean;
  reddit_available: boolean;
  twitter_available: boolean;
  message: string;
}
