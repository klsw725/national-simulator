"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type {
  BackendStatus,
  Ship,
  Flight,
  Satellite,
  MilitaryBase,
  UAV,
  CCTV,
  GPSJamming,
  Earthquake,
  KiwiSDR,
  InternetOutage,
  FIRMSFire,
  Datacenter,
  PowerPlant,
  SpaceWeather,
} from "@/types/dashboard";

const FAST_INTERVAL = 15_000;
const SLOW_INTERVAL = 120_000;

export interface PollingResult {
  ships: Ship[];
  militaryFlights: Flight[];
  satellites: Satellite[];
  militaryBases: MilitaryBase[];
  uavs: UAV[];
  trackedFlights: Flight[];
  cctv: CCTV[];
  gpsJamming: GPSJamming[];
  liveuamap: unknown[];
  gdelt: unknown[];
  news: unknown[];
  stocks: unknown[];
  earthquakes: Earthquake[];
  kiwisdr: KiwiSDR[];
  internetOutages: InternetOutage[];
  firmsFires: FIRMSFire[];
  datacenters: Datacenter[];
  powerPlants: PowerPlant[];
  spaceWeather: SpaceWeather | null;
  frontlines: unknown;
  freshness: Record<string, string>;
  backendStatus: BackendStatus;
}

type Action =
  | { type: "POLL_FAST"; payload: Record<string, unknown> }
  | { type: "POLL_SLOW"; payload: Record<string, unknown> }
  | { type: "STATUS"; payload: BackendStatus };

const INITIAL_STATE: PollingResult = {
  ships: [],
  militaryFlights: [],
  satellites: [],
  militaryBases: [],
  uavs: [],
  trackedFlights: [],
  cctv: [],
  gpsJamming: [],
  liveuamap: [],
  gdelt: [],
  news: [],
  stocks: [],
  earthquakes: [],
  kiwisdr: [],
  internetOutages: [],
  firmsFires: [],
  datacenters: [],
  powerPlants: [],
  spaceWeather: null,
  frontlines: null,
  freshness: {},
  backendStatus: "connecting",
};

function pollingReducer(state: PollingResult, action: Action): PollingResult {
  switch (action.type) {
    case "POLL_FAST": {
      const d = action.payload;
      const nested = (d.data ?? {}) as Record<string, unknown>;
      return {
        ...state,
        ships: (d.ships ?? nested.ships ?? state.ships) as Ship[],
        militaryFlights: (d.military_flights ?? state.militaryFlights) as Flight[],
        satellites: (d.satellites ?? state.satellites) as Satellite[],
        uavs: (d.uavs ?? state.uavs) as UAV[],
        trackedFlights: (d.tracked_flights ?? state.trackedFlights) as Flight[],
        cctv: (d.cctv ?? state.cctv) as CCTV[],
        gpsJamming: (d.gps_jamming ?? state.gpsJamming) as GPSJamming[],
        liveuamap: (d.liveuamap ?? state.liveuamap) as unknown[],
        freshness: d.freshness
          ? { ...state.freshness, ...(d.freshness as Record<string, string>) }
          : state.freshness,
        backendStatus: "connected",
      };
    }
    case "POLL_SLOW": {
      const d = action.payload;
      const nested = (d.data ?? {}) as Record<string, unknown>;
      return {
        ...state,
        gdelt: (d.gdelt ?? nested.gdelt ?? state.gdelt) as unknown[],
        militaryBases: (d.military_bases ?? state.militaryBases) as MilitaryBase[],
        news: (d.news ?? state.news) as unknown[],
        stocks: (d.stocks ?? state.stocks) as unknown[],
        earthquakes: (d.earthquakes ?? state.earthquakes) as Earthquake[],
        kiwisdr: (d.kiwisdr ?? state.kiwisdr) as KiwiSDR[],
        internetOutages: (d.internet_outages ?? state.internetOutages) as InternetOutage[],
        firmsFires: (d.firms_fires ?? state.firmsFires) as FIRMSFire[],
        datacenters: (d.datacenters ?? state.datacenters) as Datacenter[],
        powerPlants: (d.power_plants ?? state.powerPlants) as PowerPlant[],
        spaceWeather: (d.space_weather ?? state.spaceWeather) as SpaceWeather | null,
        frontlines: d.frontlines ?? state.frontlines,
        freshness: d.freshness
          ? { ...state.freshness, ...(d.freshness as Record<string, string>) }
          : state.freshness,
      };
    }
    case "STATUS":
      return { ...state, backendStatus: action.payload };
    default:
      return state;
  }
}

export function useDataPolling(): PollingResult {
  const [state, dispatch] = useReducer(pollingReducer, INITIAL_STATE);

  const fastEtag = useRef<string | null>(null);
  const slowEtag = useRef<string | null>(null);
  const fastInFlight = useRef(false);
  const slowInFlight = useRef(false);
  const fastFailCount = useRef(0);
  const slowFailCount = useRef(0);

  const pollFast = useCallback(async () => {
    if (fastInFlight.current) return;
    fastInFlight.current = true;
    try {
      const headers: HeadersInit = {};
      if (fastEtag.current) {
        headers["If-None-Match"] = fastEtag.current;
      }
      const res = await fetch("/api/osint/live_data/fast", { headers });
      if (res.status === 304) {
        dispatch({ type: "STATUS", payload: "connected" });
        fastFailCount.current = 0;
        return;
      }
      if (!res.ok) {
        fastFailCount.current++;
        dispatch({ type: "STATUS", payload: "disconnected" });
        return;
      }
      const etag = res.headers.get("etag");
      if (etag) fastEtag.current = etag;

      const data = await res.json();
      dispatch({ type: "POLL_FAST", payload: data });
      fastFailCount.current = 0;
    } catch {
      fastFailCount.current++;
      dispatch({ type: "STATUS", payload: "disconnected" });
    } finally {
      fastInFlight.current = false;
    }
  }, []);

  const pollSlow = useCallback(async () => {
    if (slowInFlight.current) return;
    slowInFlight.current = true;
    try {
      const headers: HeadersInit = {};
      if (slowEtag.current) {
        headers["If-None-Match"] = slowEtag.current;
      }
      const res = await fetch("/api/osint/live_data/slow", { headers });
      if (res.status === 304) {
        slowFailCount.current = 0;
        return;
      }
      if (!res.ok) {
        slowFailCount.current++;
        return;
      }
      const etag = res.headers.get("etag");
      if (etag) slowEtag.current = etag;

      const data = await res.json();
      dispatch({ type: "POLL_SLOW", payload: data });
      slowFailCount.current = 0;
    } catch {
      slowFailCount.current++;
    } finally {
      slowInFlight.current = false;
    }
  }, []);

  useEffect(() => {
    pollFast();
    pollSlow();

    const fastTimer = setInterval(() => {
      const backoff = Math.min(fastFailCount.current, 3);
      if (backoff === 0 || Math.random() < 1 / (1 << backoff)) {
        pollFast();
      }
    }, FAST_INTERVAL);

    const slowTimer = setInterval(() => {
      const backoff = Math.min(slowFailCount.current, 3);
      if (backoff === 0 || Math.random() < 1 / (1 << backoff)) {
        pollSlow();
      }
    }, SLOW_INTERVAL);

    return () => {
      clearInterval(fastTimer);
      clearInterval(slowTimer);
    };
  }, [pollFast, pollSlow]);

  return state;
}
