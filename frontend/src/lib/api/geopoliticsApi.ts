import type { DecisionPoint, DecisionPointResolveRequest } from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

export function getGeopoliticsSummary(scenarioId: string): Promise<{
  scenario_id: string; total_events: number; total_rounds: number; actors: string[];
}> {
  return fetchJSON(`/api/scenario/${scenarioId}/geopolitics`);
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
  data: DecisionPointResolveRequest,
): Promise<DecisionPoint> {
  return fetchJSON(`/api/scenario/${scenarioId}/decision_points/${dpId}/resolve`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(data),
  });
}
