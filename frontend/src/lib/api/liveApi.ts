import type {
  GraphData,
  GraphTaskStatus,
  LiveAction,
  LiveConfig,
  LiveProfiles,
  LiveStats,
} from "@/types/simulation";
import { fetchJSON } from "./fetchUtils";

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
