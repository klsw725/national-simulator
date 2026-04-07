import type { WargameState, DecisionPoint } from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

// ── Wargame status ─────────────────────────────────────────

export interface WargameStatusResponse {
  phase: WargameState["phase"];
  round: number;
  totalRounds: number;
  role: WargameState["role"];
  actorId: string | null;
  tension: number;
  actorStates: WargameState["actorStates"];
  briefing: WargameState["briefing"];
  decisionPoint: WargameState["decisionPoint"];
}

export function getWargameStatus(
  scenarioId: string,
): Promise<WargameStatusResponse> {
  return fetchJSON(`/api/scenario/${scenarioId}/wargame_status`);
}

// ── Decision resolution (delegates to existing endpoint) ───

export function resolveWargameDecision(
  scenarioId: string,
  decisionPointId: string,
  selectedOptionId: string,
): Promise<DecisionPoint> {
  return fetchJSON(
    `/api/scenario/${scenarioId}/decision_points/${decisionPointId}/resolve`,
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ selected_option_id: selectedOptionId }),
    },
  );
}

// ── Resume wargame after decision ──────────────────────────

export function resumeWargame(
  scenarioId: string,
): Promise<{ status: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/continue`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({}),
  });
}

export function submitWargameDecisionV2(
  scenarioId: string,
  chosenAction: Record<string, unknown>,
  selectedOptionId?: string,
): Promise<{ status: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/decide_v2`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      decision_point_id: String(chosenAction.decision_point_id ?? ""),
      selected_option_id: selectedOptionId ?? null,
      chosen_action: chosenAction,
    }),
  });
}
