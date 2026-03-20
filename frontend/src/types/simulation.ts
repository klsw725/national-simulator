export interface Scenario {
  id: string;
  name: string;
  region_bbox: number[];
  region_name: string;
  question: string;
  max_rounds: number;
  data_sources: string[];
  status: string;
  seed_status: string;
  simulation_status: string;
  created_at: string;
  updated_at: string;
}

export interface ScenarioFormData {
  name: string;
  region: { bbox: [number, number, number, number]; name: string };
  question: string;
  max_rounds: number;
  data_sources: string[];
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
  action_args: { content?: string; [key: string]: unknown };
  round_num: number;
}
