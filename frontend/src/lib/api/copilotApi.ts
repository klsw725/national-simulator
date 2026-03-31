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
