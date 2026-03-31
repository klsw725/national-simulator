import type { Scenario, ScenarioFormData } from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

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
