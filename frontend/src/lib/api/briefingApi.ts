import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

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
