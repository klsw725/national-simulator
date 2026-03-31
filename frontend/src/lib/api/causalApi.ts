import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

export interface CausalDAGResponse {
  model_type: string;
  dag: {
    directed: boolean;
    multigraph: boolean;
    nodes: Array<{ id: string; node_type?: string }>;
    links: Array<{ source: string; target: string; edge_type?: string; strength?: number }>;
  };
}

export interface CausalInterventionResult {
  interventions: Record<string, number>;
  targets: Record<string, { mean: number; std: number; ci_lower: number; ci_upper: number }>;
  num_samples: number;
}

export interface CausalCounterfactualResult {
  observed: Record<string, number>;
  counterfactual: Record<string, number>;
  differences: Record<string, number>;
}

export interface CausalAttributionResult {
  target_variable: string;
  attributions: Record<string, number>;
  total_explained: number;
  method: string;
}

export function getCausalDomainDAG(): Promise<CausalDAGResponse> {
  return fetchJSON("/api/causal/domain_dag");
}

export function fitCausalModel(modelId: string, scenarioId: string): Promise<{
  model_id: string; variables: string[]; observations: number; status: string;
}> {
  return fetchJSON("/api/causal/fit", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ model_id: modelId, scenario_id: scenarioId }),
  });
}

export function causalIntervene(
  modelId: string,
  interventions: Record<string, number>,
  targetVariables?: string[],
): Promise<CausalInterventionResult> {
  return fetchJSON("/api/causal/intervene", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ model_id: modelId, interventions, target_variables: targetVariables }),
  });
}

export function causalCounterfactual(
  modelId: string,
  observed: Record<string, number>,
  interventions: Record<string, number>,
): Promise<CausalCounterfactualResult> {
  return fetchJSON("/api/causal/counterfactual", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ model_id: modelId, observed, interventions }),
  });
}

export function causalAttribute(
  modelId: string,
  targetVariable: string,
): Promise<CausalAttributionResult> {
  return fetchJSON("/api/causal/attribute", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ model_id: modelId, target_variable: targetVariable }),
  });
}
