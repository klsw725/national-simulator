import type { EnvStatus, InterviewResult } from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

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

export function getEnvStatus(scenarioId: string): Promise<EnvStatus> {
  return fetchJSON("/api/copilot/env-status", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

export function interviewAgent(
  scenarioId: string,
  agentId: number,
  prompt: string,
): Promise<InterviewResult> {
  return fetchJSON("/api/copilot/interview", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ scenario_id: scenarioId, agent_id: agentId, prompt }),
  });
}

export function interviewAllAgents(
  scenarioId: string,
  prompt: string,
): Promise<{ results: InterviewResult[] }> {
  return fetchJSON("/api/copilot/interview/all", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ scenario_id: scenarioId, prompt }),
  });
}

export function closeSimulationEnv(scenarioId: string): Promise<{ message?: string }> {
  return fetchJSON("/api/copilot/close-env", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}
