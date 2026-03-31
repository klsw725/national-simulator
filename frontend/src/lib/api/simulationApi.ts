import type { CheckpointResponse, ContinueRequest, PipelineMode, SimulateRequest } from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

export function retrySimulation(
  scenarioId: string,
): Promise<{ scenario_id: string; result_id: string; recovery_point: string; message: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/retry`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}

export function startSimulation(
  scenarioId: string,
  mode: PipelineMode = "auto"
): Promise<{ status: string; pipeline_mode: string }> {
  const body: SimulateRequest = { mode };
  return fetchJSON(`/api/scenario/${scenarioId}/simulate`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

export function getCheckpoint(
  scenarioId: string
): Promise<CheckpointResponse> {
  return fetchJSON(`/api/scenario/${scenarioId}/checkpoint`);
}

export function continueSimulation(
  scenarioId: string,
  edits?: Record<string, unknown>
): Promise<{ status: string }> {
  const body: ContinueRequest = { edits: edits || null };
  return fetchJSON(`/api/scenario/${scenarioId}/continue`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

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
