import type { WhatIfBranch, WhatIfComparison, WhatIfCreateRequest } from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

export type { WhatIfBranch, WhatIfComparison, WhatIfCreateRequest } from "@/types/simulation";

export function createWhatIfBranch(
  scenarioId: string,
  data: WhatIfCreateRequest,
): Promise<{ branch_id: string; status: string; modification: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulation/whatif`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(data),
  });
}

export function getWhatIfBranches(scenarioId: string): Promise<WhatIfBranch[]> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulation/whatif`);
}

export function getWhatIfBranch(scenarioId: string, branchId: string): Promise<WhatIfBranch> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulation/whatif/${branchId}`);
}

export function getWhatIfComparison(scenarioId: string, branchId: string): Promise<WhatIfComparison> {
  return fetchJSON(`/api/scenario/${scenarioId}/simulation/whatif/${branchId}/compare`);
}
