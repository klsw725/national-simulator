"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

export function useDataPolling(): PollingResult {
  const [ships, setShips] = useState<Ship[]>([]);
  const [militaryFlights, setMilitaryFlights] = useState<Flight[]>([]);
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [militaryBases, setMilitaryBases] = useState<MilitaryBase[]>([]);
  const [uavs, setUavs] = useState<UAV[]>([]);
  const [trackedFlights, setTrackedFlights] = useState<Flight[]>([]);
  const [cctv, setCctv] = useState<CCTV[]>([]);
  const [gpsJamming, setGpsJamming] = useState<GPSJamming[]>([]);
  const [liveuamap, setLiveuamap] = useState<unknown[]>([]);
  const [gdelt, setGdelt] = useState<unknown[]>([]);
  const [news, setNews] = useState<unknown[]>([]);
  const [stocks, setStocks] = useState<unknown[]>([]);
  const [earthquakes, setEarthquakes] = useState<Earthquake[]>([]);
  const [kiwisdr, setKiwisdr] = useState<KiwiSDR[]>([]);
  const [internetOutages, setInternetOutages] = useState<InternetOutage[]>([]);
  const [firmsFires, setFirmsFires] = useState<FIRMSFire[]>([]);
  const [datacenters, setDatacenters] = useState<Datacenter[]>([]);
  const [powerPlants, setPowerPlants] = useState<PowerPlant[]>([]);
  const [spaceWeather, setSpaceWeather] = useState<SpaceWeather | null>(null);
  const [frontlines, setFrontlines] = useState<unknown>(null);
  const [freshness, setFreshness] = useState<Record<string, string>>({});
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
      setShips(data.ships ?? data.data?.ships ?? []);
      setMilitaryFlights(data.military_flights ?? []);
      setSatellites(data.satellites ?? []);
      setUavs(data.uavs ?? []);
      setTrackedFlights(data.tracked_flights ?? []);
      setCctv(data.cctv ?? []);
      setGpsJamming(data.gps_jamming ?? []);
      setLiveuamap(data.liveuamap ?? []);
      if (data.freshness) {
        setFreshness((prev) => ({ ...prev, ...data.freshness }));
      }
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
      setMilitaryBases(data.military_bases ?? []);
      setNews(data.news ?? []);
      setStocks(data.stocks ?? []);
      setEarthquakes(data.earthquakes ?? []);
      setKiwisdr(data.kiwisdr ?? []);
      setInternetOutages(data.internet_outages ?? []);
      setFirmsFires(data.firms_fires ?? []);
      setDatacenters(data.datacenters ?? []);
      setPowerPlants(data.power_plants ?? []);
      setSpaceWeather(data.space_weather ?? null);
      setFrontlines(data.frontlines ?? null);
      if (data.freshness) {
        setFreshness((prev) => ({ ...prev, ...data.freshness }));
      }
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

  return {
    ships,
    militaryFlights,
    satellites,
    militaryBases,
    uavs,
    trackedFlights,
    cctv,
    gpsJamming,
    liveuamap,
    gdelt,
    news,
    stocks,
    earthquakes,
    kiwisdr,
    internetOutages,
    firmsFires,
    datacenters,
    powerPlants,
    spaceWeather,
    frontlines,
    freshness,
    backendStatus,
  };
}
