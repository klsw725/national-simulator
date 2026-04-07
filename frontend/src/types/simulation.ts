export interface ScenarioRegion {
  bbox: [number, number, number, number];
  name: string;
}

export type GeopoliticsMode = "auto" | "actor_role" | "game_master";

export interface SimulationParams {
  platform: string;
  simulation_hours: number;
  simulation_requirement: string | null;
  geopolitics_enabled: boolean;
  web_search_enabled: boolean;
  geopolitics_mode: GeopoliticsMode;
  geopolitics_player_actor_id: string | null;
  geopolitics_rounds: number;
  geopolitics_pause_threshold: number;
  wargame_enabled?: boolean;
  wargame_idle_ttl_minutes?: number;
}

export interface SimulationParamsInput {
  platform?: string;
  simulation_hours?: number;
  simulation_requirement?: string | null;
  geopolitics_enabled?: boolean;
  web_search_enabled?: boolean;
  geopolitics_mode?: GeopoliticsMode;
  geopolitics_player_actor_id?: string | null;
  geopolitics_rounds?: number;
  geopolitics_pause_threshold?: number;
  wargame_enabled?: boolean;
  wargame_idle_ttl_minutes?: number;
}

export interface ScenarioCreate {
  name: string;
  region: ScenarioRegion;
  question: string;
  max_rounds: number;
  data_sources: string[];
  simulation_params?: SimulationParamsInput;
}

export interface ScenarioCreatedResponse {
  id: string;
  status: string;
  seed_status: string;
  simulation_status: string;
}

export interface ScenarioResponse {
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

export interface Scenario extends ScenarioResponse {}

export type PipelineMode = 'auto' | 'checkpoint';

export interface ScenarioFormData {
  name: string;
  region: ScenarioRegion;
  question: string;
  max_rounds: number;
  data_sources: string[];
  mode: PipelineMode;
  simulation_params?: SimulationParamsInput;
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

export interface SimulationResultResponse {
  id: string;
  scenario_id: string;
  mirofish_simulation_id: string | null;
  mirofish_project_id: string | null;
  status: string;
  platform: string;
  results: Record<string, unknown> | null;
  geojson: Record<string, unknown> | null;
  report: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface CheckpointResponse {
  scenario_id: string;
  result_id: string;
  status: string;
  step: string;      // "seed" | "ontology" | "graph" | "profiles" | "config"
  editable: boolean;
  data: Record<string, unknown> | null;
  pipeline_mode: string;
}

export type CheckpointData = CheckpointResponse;

export interface SimulateRequest {
  mode?: string;
}

export interface ContinueRequest {
  edits?: Record<string, unknown> | null;
}

export interface SeedMetadata {
  vessels_count: number;
  actors_identified: string[];
  military_flights_count: number;
  satellites_count: number;
  gdelt_events_count: number;
  tension_score: number;
  osint_sources_used: number;
  web_search_count: number;
  resolved_entity_count: number;
  used_observation_ids: string[];
  data_timestamp: string;
}

export interface SeedResponse {
  id: string;
  scenario_id: string;
  text: string;
  metadata: SeedMetadata;
  created_at: string;
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

export interface DecisionPointCreate {
  type: DecisionPointType;
  options: DecisionOption[];
  recommended: string;
  allow_custom?: boolean;
}

export interface DecisionPointResponse {
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

export type DecisionPoint = DecisionPointResponse;

export interface WargameDecisionPointV2Option {
  action_type: string;
  target: string;
  intensity: "low" | "medium" | "high";
  description: string;
  estimated_effect: {
    tension_delta: number;
    resource_cost: number;
  };
}

export interface WargameDecisionPointV2 {
  id: string;
  round: number;
  trigger: string;
  options: WargameDecisionPointV2Option[];
}

export type WargameDecisionPoint = DecisionPoint | WargameDecisionPointV2;

export interface DecisionPointResolveRequest {
  selected_option_id?: string | null;
  custom_data?: Record<string, unknown> | null;
}

export interface WhatIfCreateRequest {
  modification: string;
  branch_point_round?: number | null;
  execution_mode?: string;
  max_rounds_override?: number | null;
}

export interface WhatIfComparison {
  branch_id: string;
  tension_advantage: number;
  tension_curves: Record<string, unknown> & { original: number[]; branch: number[] };
  step_variance: Record<string, unknown> & { original: number; branch: number };
  slope_variance: Record<string, unknown> & { original: number; branch: number };
  actor_diff: Record<string, unknown> & { only_original: string[]; only_branch: string[]; common: string[] };
  action_count_delta: number;
  geopolitics_delta: number;
  causal_attribution: {
    tension_advantage_explained: Record<string, number>;
    confidence: string;
    method: string;
  } | null;
}

export interface WhatIfBranch {
  id: string;
  scenario_id: string;
  parent_result_id: string;
  branch_result_id: string | null;
  branch_point_round: number | null;
  modification: string;
  execution_mode: string;
  world_model_strategy: string;
  status: string;
  comparison_data: Record<string, unknown> | null;
  created_at: string;
  completed_at: string | null;
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

// ── Wargame (v11) ──────────────────────────────────────────

export type WargamePhase = "simulation" | "briefing" | "decision" | "confirmation";

export interface WargameState {
  phase: WargamePhase;
  round: number;
  totalRounds: number;
  role: "actor_role" | "game_master";
  actorId: string | null;
  tension: number;
  actorStates: Record<string, ActorState>;
  briefing: RoundBriefing | null;
  decisionPoint: WargameDecisionPoint | null;
}

export interface ActorState {
  actor_id: string;
  name: string;
  threat_perception: number;
  domestic_pressure: number;
  resource_level: number;
}

export interface RoundBriefing {
  round: number;
  key_events: Array<{
    type: string;
    description: string;
    severity: "low" | "medium" | "high" | "critical";
  }>;
  state_deltas: Record<string, number>;
  previous_decision_outcome: string | null;
  social_media_summary: { total_posts: number; top_topics: string[] };
}

export type WargameLens = "info_warfare" | "diplomacy" | "military" | "economy" | "relations" | "whatif";

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
