"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { BackendStatus, Ship } from "@/types/dashboard";

const FAST_INTERVAL = 15_000;
const SLOW_INTERVAL = 120_000;

interface PollingResult {
  ships: Ship[];
  gdelt: unknown[];
  backendStatus: BackendStatus;
}

export function useDataPolling(): PollingResult {
  const [ships, setShips] = useState<Ship[]>([]);
  const [gdelt, setGdelt] = useState<unknown[]>([]);
  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("connecting");

  const fastEtag = useRef<string | null>(null);
  const slowEtag = useRef<string | null>(null);

  const pollFast = useCallback(async () => {
    try {
      const headers: HeadersInit = {};
      if (fastEtag.current) {
        headers["If-None-Match"] = fastEtag.current;
      }
      const res = await fetch("/api/osint/live_data/fast", { headers });
      if (res.status === 304) {
        setBackendStatus("connected");
        return;
      }
      if (!res.ok) {
        setBackendStatus("disconnected");
        return;
      }
      const etag = res.headers.get("etag");
      if (etag) fastEtag.current = etag;

      const data = await res.json();
      const shipList: Ship[] = data.ships ?? data.data?.ships ?? [];
      setShips(shipList);
      setBackendStatus("connected");
    } catch {
      setBackendStatus("disconnected");
    }
  }, []);

  const pollSlow = useCallback(async () => {
    try {
      const headers: HeadersInit = {};
      if (slowEtag.current) {
        headers["If-None-Match"] = slowEtag.current;
      }
      const res = await fetch("/api/osint/live_data/slow", { headers });
      if (res.status === 304) return;
      if (!res.ok) return;
      const etag = res.headers.get("etag");
      if (etag) slowEtag.current = etag;

      const data = await res.json();
      setGdelt(data.gdelt ?? data.data?.gdelt ?? []);
    } catch {
      // slow poll failure is non-critical
    }
  }, []);

  useEffect(() => {
    pollFast();
    pollSlow();

    const fastTimer = setInterval(pollFast, FAST_INTERVAL);
    const slowTimer = setInterval(pollSlow, SLOW_INTERVAL);

    return () => {
      clearInterval(fastTimer);
      clearInterval(slowTimer);
    };
  }, [pollFast, pollSlow]);

  return { ships, gdelt, backendStatus };
}
