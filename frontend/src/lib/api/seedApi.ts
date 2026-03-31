import type { DecisionPoint, SeedResponse } from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

export function generateSeed(
  scenarioId: string
): Promise<{ status: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/seed`, {
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
): Promise<SeedResponse> {
  return fetchJSON(`/api/scenario/${scenarioId}/seed`);
}
