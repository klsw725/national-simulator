import { fetchJSON } from "./fetchUtils";

export function getHealthDetailed(): Promise<{
  status: string;
  services: Record<string, { status: string; latency_ms?: number; circuit_breaker?: string; failure_count?: number }>;
}> {
  return fetchJSON("/api/health/detailed");
}

export function getDashboard(): Promise<{
  total_scenarios: number;
  by_status: Record<string, number>;
  by_region: Record<string, number>;
  recent_activity: Array<{ scenario_id: string; action: string; actor: string; timestamp: string }>;
  running_simulations: Array<{ id: string; name: string; status: string }>;
}> {
  return fetchJSON("/api/dashboard");
}

export function getAnalyticsTrend(params: {
  source_type: string;
  hours?: number;
  interval?: string;
  region?: string;
}): Promise<{
  source_type: string;
  interval: string;
  data_points: Array<{ time: string; count: number; countries: Record<string, number> }>;
  summary: { min: number; max: number; avg: number; trend: string };
}> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null) qs.set(k, String(v));
  }
  return fetchJSON(`/api/analytics/trend?${qs.toString()}`);
}

export function getAnalyticsAnomalies(params?: {
  hours?: number;
  region?: string;
}): Promise<{
  anomalies: Array<{
    type: string;
    source_type: string;
    detected_at: string;
    severity: string;
    detail: string;
    current: number;
    baseline: number;
    sigma: number;
  }>;
}> {
  const qs = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null) qs.set(k, String(v));
    }
  }
  return fetchJSON(`/api/analytics/anomalies?${qs.toString()}`);
}

export function getAnalyticsCompare(params: {
  source_type: string;
  period_a: string;
  period_b: string;
  hours?: number;
}): Promise<{
  source_type: string;
  period_a: { avg: number; max: number; min: number; trend: string };
  period_b: { avg: number; max: number; min: number; trend: string };
  delta: { avg: number; max: number; pct_change: string };
}> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null) qs.set(k, String(v));
  }
  return fetchJSON(`/api/analytics/compare?${qs.toString()}`);
}

export function getAnalyticsSnapshots(hours?: number): Promise<{
  snapshots: Array<{
    time: string;
    assets: Record<string, number>;
    tension: Record<string, number>;
  }>;
}> {
  const qs = hours ? `?hours=${hours}` : "";
  return fetchJSON(`/api/analytics/snapshots${qs}`);
}
