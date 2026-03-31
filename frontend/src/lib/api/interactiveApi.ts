import type {
  EnvStatus,
  InjectEventRequest,
  InterviewHistoryItem,
  InterviewResult,
  InteractiveStatus,
} from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

export function getEnvStatus(scenarioId: string): Promise<EnvStatus> {
  return fetchJSON(`/api/scenario/${scenarioId}/env_status`);
}

export function interviewAgent(
  scenarioId: string,
  agentId: number,
  prompt: string,
  platform?: string,
): Promise<InterviewResult> {
  return fetchJSON(`/api/scenario/${scenarioId}/interview`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ agent_id: agentId, prompt, platform }),
  });
}

export function interviewAllAgents(
  scenarioId: string,
  prompt: string,
  platform?: string,
): Promise<{ success: boolean; total_agents: number; results: InterviewResult[] }> {
  return fetchJSON(`/api/scenario/${scenarioId}/interview/all`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ prompt, platform }),
  });
}

export function getInterviewHistory(
  scenarioId: string,
  agentId?: number,
  limit?: number,
): Promise<{ interviews: InterviewHistoryItem[]; total: number }> {
  const params = new URLSearchParams();
  if (agentId != null) params.set("agent_id", String(agentId));
  if (limit != null) params.set("limit", String(limit));
  const qs = params.toString();
  return fetchJSON(`/api/scenario/${scenarioId}/interview/history${qs ? `?${qs}` : ""}`);
}

export function closeSimulationEnv(
  scenarioId: string,
): Promise<{ success: boolean; message: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/close_env`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({}),
  });
}

export function getInteractiveStatus(scenarioId: string): Promise<InteractiveStatus> {
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

export function injectEvent(scenarioId: string, data: InjectEventRequest): Promise<{ event_id: string; status: string; injected_at_round: number }> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulation/inject_event`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(data),
  });
}
