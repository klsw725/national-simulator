import type {
  Scenario,
  ScenarioFormData,
  PipelineMode,
  CheckpointData,
  LiveStats,
  LiveAction,
  GraphTaskStatus,
  GraphData,
  LiveProfiles,
  LiveConfig,
  DecisionPoint,
} from "@/types/simulation";

const JSON_HEADERS = { "Content-Type": "application/json" };

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ── Scenario CRUD ──

export function createScenario(
  data: ScenarioFormData
): Promise<Scenario> {
  return fetchJSON("/api/scenario", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      name: data.name,
      region: { bbox: data.region.bbox, name: data.region.name },
      question: data.question,
      max_rounds: data.max_rounds,
      data_sources: data.data_sources,
      ...(data.simulation_params && { simulation_params: data.simulation_params }),
    }),
  });
}

export function getScenarios(): Promise<Scenario[]> {
  return fetchJSON("/api/scenario");
}

export function deleteScenario(id: string): Promise<void> {
  return fetchJSON(`/api/scenario/${id}`, {
    method: "DELETE",
    headers: JSON_HEADERS,
  });
}

// ── Pipeline actions ──

export function generateSeed(
  scenarioId: string
): Promise<{ status: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/seed`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}

export function getHealthDetailed(): Promise<{
  status: string;
  services: Record<string, { status: string; latency_ms?: number; circuit_breaker?: string; failure_count?: number }>;
}> {
  return fetchJSON("/api/health/detailed");
}

export function retrySimulation(
  scenarioId: string,
): Promise<{ scenario_id: string; result_id: string; recovery_point: string; message: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/retry`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}

export function recommendParams(
  scenarioId: string,
): Promise<{
  scenario_id: string;
  decision_point_id: string;
  recommended: string;
  decision_point: DecisionPoint;
  metadata: Record<string, unknown>;
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/recommend_params`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}

export function generateSeedOptions(
  scenarioId: string,
  numOptions: number = 3,
): Promise<{
  scenario_id: string;
  decision_point_id: string;
  options_count: number;
  recommended: string;
  decision_point: DecisionPoint;
  metadata: Record<string, unknown>;
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/seed_options?num_options=${numOptions}`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}

export function getSeed(
  scenarioId: string
): Promise<{
  id: string;
  text: string;
  metadata: {
    vessels_count: number;
    actors_identified: string[];
    resolved_entity_count: number;
    used_observation_ids: string[];
    web_search_count: number;
    tension_score: number;
  };
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/seed`);
}

export function startSimulation(
  scenarioId: string,
  mode: PipelineMode = "auto"
): Promise<{ status: string; pipeline_mode: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulate`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ mode }),
  });
}

export function getCheckpoint(
  scenarioId: string
): Promise<CheckpointData> {
  return fetchJSON(`/api/scenario/${scenarioId}/checkpoint`);
}

export function continueSimulation(
  scenarioId: string,
  edits?: Record<string, unknown>
): Promise<{ status: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/continue`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ edits: edits || null }),
  });
}

// ── Status & results ──

export function getStatus(
  scenarioId: string
): Promise<{ status: string; seed_status: string; simulation_status: string; error_message?: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/status`);
}

export function getResults(
  scenarioId: string
): Promise<unknown> {
  return fetchJSON(`/api/scenario/${scenarioId}/results`);
}

export function getGeoJSON(
  scenarioId: string
): Promise<unknown> {
  return fetchJSON(`/api/scenario/${scenarioId}/geojson`);
}

export function getReport(
  scenarioId: string
): Promise<unknown> {
  return fetchJSON(`/api/scenario/${scenarioId}/report`);
}

export function getLiveStats(scenarioId: string): Promise<LiveStats> {
  return fetchJSON(`/api/scenario/${scenarioId}/live/stats`);
}

export function getLiveActions(
  scenarioId: string, offset = 0, limit = 100
): Promise<{ actions: LiveAction[]; count: number }> {
  return fetchJSON(`/api/scenario/${scenarioId}/live/actions?offset=${offset}&limit=${limit}`);
}

export function getLiveGraphTask(scenarioId: string): Promise<GraphTaskStatus> {
  return fetchJSON(`/api/scenario/${scenarioId}/live/graph_task`);
}

export function getLiveGraphData(scenarioId: string): Promise<GraphData> {
  return fetchJSON(`/api/scenario/${scenarioId}/live/graph_data`);
}

export function getLiveProfiles(scenarioId: string): Promise<LiveProfiles> {
  return fetchJSON(`/api/scenario/${scenarioId}/live/profiles`);
}

export function getLiveConfig(scenarioId: string): Promise<LiveConfig> {
  return fetchJSON(`/api/scenario/${scenarioId}/live/config`);
}

// ── Geopolitics ──

export function getGeopoliticsSummary(scenarioId: string): Promise<{
  scenario_id: string; total_events: number; total_rounds: number; actors: string[];
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/geopolitics`);
}

// ── Decision Points ──

export function getDecisionPoints(
  scenarioId: string,
  status?: string,
): Promise<{ scenario_id: string; count: number; decision_points: DecisionPoint[] }> {
  const qs = status ? `?status=${status}` : "";
  return fetchJSON(`/api/scenario/${scenarioId}/decision_points${qs}`);
}

export function getDecisionPoint(
  scenarioId: string,
  dpId: string,
): Promise<DecisionPoint> {
  return fetchJSON(`/api/scenario/${scenarioId}/decision_points/${dpId}`);
}

export function resolveDecisionPoint(
  scenarioId: string,
  dpId: string,
  data: { selected_option_id?: string; custom_data?: Record<string, unknown> },
): Promise<DecisionPoint> {
  return fetchJSON(`/api/scenario/${scenarioId}/decision_points/${dpId}/resolve`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(data),
  });
}

// ── Geopolitics ──

export function getGeopoliticsTimeline(scenarioId: string): Promise<{
  scenario_id: string;
  timeline: Array<{
    round: number;
    events: Array<{
      action_type: string; actor_id: string; target_actor_ids: string[];
      content: string; magnitude: number;
    }>;
  }>;
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/geopolitics/timeline`);
}
