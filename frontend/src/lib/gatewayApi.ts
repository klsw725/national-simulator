import type { Scenario, ScenarioFormData, PipelineMode, CheckpointData } from "@/types/simulation";

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
): Promise<{ status: string; seed_status: string; simulation_status: string }> {
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
