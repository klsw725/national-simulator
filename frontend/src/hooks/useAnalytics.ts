"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/gatewayApi";

type TrendData = Awaited<ReturnType<typeof api.getAnalyticsTrend>>;
type AnomalyData = Awaited<ReturnType<typeof api.getAnalyticsAnomalies>>;

interface UseAnalyticsParams {
  sourceType: string;
  hours: number;
}

export function useAnalytics({ sourceType, hours }: UseAnalyticsParams) {
  const [trend, setTrend] = useState<TrendData | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [trendResult, anomalyResult] = await Promise.all([
        api.getAnalyticsTrend({ source_type: sourceType, hours }),
        api.getAnalyticsAnomalies({ hours }),
      ]);
      setTrend(trendResult);
      setAnomalies(anomalyResult);
    } catch {
      /* noop */
    }
    setLoading(false);
  }, [sourceType, hours]);

  useEffect(() => {
    load();
  }, [load]);

  return { trend, anomalies, loading, reload: load };
}
