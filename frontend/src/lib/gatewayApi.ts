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

// ── Export ──

export function exportScenarioJSON(scenarioId: string): Promise<unknown> {
  return fetchJSON(`/api/scenario/${scenarioId}/export?format=json`);
}

export async function downloadExport(scenarioId: string, type: "csv" | "observations" | "geopolitics" | "report"): Promise<Blob> {
  const urlMap: Record<string, string> = {
    csv: `/api/scenario/${scenarioId}/export?format=csv`,
    observations: `/api/scenario/${scenarioId}/export/observations`,
    geopolitics: `/api/scenario/${scenarioId}/export/geopolitics`,
    report: `/api/scenario/${scenarioId}/export/report`,
  };
  const res = await fetch(urlMap[type]);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.blob();
}

export function generateBriefing(scenarioId: string): Promise<{
  id: string;
  scenario_id: string;
  content: string;
  version: number;
  created_at: string;
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/briefing/generate`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}

export function getBriefing(scenarioId: string): Promise<{
  id: string;
  scenario_id: string;
  content: string;
  version: number;
  created_at: string;
  updated_at: string;
} | null> {
  return fetchJSON(`/api/scenario/${scenarioId}/briefing`);
}

export function updateBriefing(scenarioId: string, content: string): Promise<{
  id: string;
  content: string;
  version: number;
  updated_at: string;
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/briefing`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify({ content }),
  });
}

// ── Search / Compare / Dashboard ──

export function searchScenarios(params: {
  q?: string;
  status?: string;
  region?: string;
  created_after?: string;
  created_before?: string;
  sort?: string;
  order?: string;
  limit?: number;
  offset?: number;
}): Promise<{ scenarios: Scenario[]; total: number }> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") qs.set(k, String(v));
  }
  return fetchJSON(`/api/scenario?${qs.toString()}`);
}

export function compareScenarios(idA: string, idB: string): Promise<{
  scenario_a: { id: string; name: string; region_name: string; status: string; actors: string[]; action_count: number; geopolitics_events: number };
  scenario_b: { id: string; name: string; region_name: string; status: string; actors: string[]; action_count: number; geopolitics_events: number };
  diff: { actors_only_a: string[]; actors_only_b: string[]; actors_common: string[]; action_count_delta: number; geopolitics_events_delta: number };
}> {
  return fetchJSON(`/api/scenario/${idA}/compare/${idB}`);
}

export function getDashboard(): Promise<{
  total_scenarios: number;
  by_status: Record<string, number>;
  by_region: Record<string, number>;
  recent_activity: Array<{ scenario_id: string; action: string; actor: string; timestamp: string }>;
  running_simulations: Array<{ id: string; name: string; status: string }>;
}> {
  return fetchJSON("/api/dashboard");
}

// ── Analytics ──

export function getAnalyticsTrend(params: {
  source_type: string;
  hours?: number;
  interval?: string;
  region?: string;
}): Promise<{
  source_type: string;
  interval: string;
  data_points: Array<{ time: string; count: number; countries: Record<string, number> }>;
  summary: { min: number; max: number; avg: number; trend: string };
}> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null) qs.set(k, String(v));
  }
  return fetchJSON(`/api/analytics/trend?${qs.toString()}`);
}

export function getAnalyticsAnomalies(params?: {
  hours?: number;
  region?: string;
}): Promise<{
  anomalies: Array<{
    type: string;
    source_type: string;
    detected_at: string;
    severity: string;
    detail: string;
    current: number;
    baseline: number;
    sigma: number;
  }>;
}> {
  const qs = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null) qs.set(k, String(v));
    }
  }
  return fetchJSON(`/api/analytics/anomalies?${qs.toString()}`);
}

export function getAnalyticsCompare(params: {
  source_type: string;
  period_a: string;
  period_b: string;
  hours?: number;
}): Promise<{
  source_type: string;
  period_a: { avg: number; max: number; min: number; trend: string };
  period_b: { avg: number; max: number; min: number; trend: string };
  delta: { avg: number; max: number; pct_change: string };
}> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null) qs.set(k, String(v));
  }
  return fetchJSON(`/api/analytics/compare?${qs.toString()}`);
}

export function getAnalyticsSnapshots(hours?: number): Promise<{
  snapshots: Array<{
    time: string;
    assets: Record<string, number>;
    tension: Record<string, number>;
  }>;
}> {
  const qs = hours ? `?hours=${hours}` : "";
  return fetchJSON(`/api/analytics/snapshots${qs}`);
}

// ── Interactive Simulation ──

export function getInteractiveStatus(scenarioId: string): Promise<{
  scenario_id: string;
  simulation_status: string;
  current_round: number;
  max_rounds: number;
  is_paused: boolean;
  pause_reason: string | null;
  injected_events_count: number;
  tension_alerts: number;
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/interactive_status`);
}

export function pauseSimulation(scenarioId: string): Promise<{ status: string; round: number }> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulation/pause`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}

export function resumeSimulation(scenarioId: string): Promise<{ status: string; from_round: number; remaining_rounds: number }> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulation/resume`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}

export function injectEvent(scenarioId: string, data: { event_type: string; content: string; target_agents: string[] }): Promise<{ event_id: string; status: string; injected_at_round: number }> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulation/inject_event`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(data),
  });
}

// ── Copilot ──

export function copilotChat(
  scenarioId: string,
  message: string,
  conversationId?: string,
): Promise<{
  response: string;
  conversation_id: string;
  sources: string[];
  tools_used: string[];
  suggestions: string[];
}> {
  return fetchJSON("/api/copilot/chat", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      scenario_id: scenarioId,
      message,
      conversation_id: conversationId,
    }),
  });
}

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
