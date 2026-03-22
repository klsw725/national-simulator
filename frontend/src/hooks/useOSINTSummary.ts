"use client";

import { useMemo } from "react";
import type { PollingResult } from "@/hooks/useDataPolling";

export interface AssetCountByCountry {
  country: string;
  ships: number;
  flights: number;
  uavs: number;
  satellites: number;
  bases: number;
}

export interface OSINTSummary {
  tensionScore: number;
  totalShips: number;
  totalFlights: number;
  totalUavs: number;
  totalSatellites: number;
  totalBases: number;
  totalGpsJamming: number;
  assetsByCountry: AssetCountByCountry[];
  recentEvents: RecentEvent[];
}

export interface RecentEvent {
  time: string;
  source: string;
  category: "military" | "info" | "infra" | "environment";
  title: string;
  detail?: string;
  lat?: number;
  lng?: number;
}

export function useOSINTSummary(polling: PollingResult): OSINTSummary {
  return useMemo(() => {
    const countryMap = new Map<string, AssetCountByCountry>();

    const getOrCreate = (country: string): AssetCountByCountry => {
      if (!countryMap.has(country)) {
        countryMap.set(country, {
          country,
          ships: 0,
          flights: 0,
          uavs: 0,
          satellites: 0,
          bases: 0,
        });
      }
      return countryMap.get(country)!;
    };

    for (const s of polling.ships) {
      if (s.country) getOrCreate(s.country).ships++;
    }
    for (const f of polling.militaryFlights) {
      if (f.country) getOrCreate(f.country).flights++;
    }
    for (const u of polling.uavs) {
      if (u.country) getOrCreate(u.country).uavs++;
    }
    for (const s of polling.satellites) {
      if (s.country) getOrCreate(s.country).satellites++;
    }
    for (const b of polling.militaryBases) {
      if (b.country) getOrCreate(b.country).bases++;
    }

    const assetsByCountry = Array.from(countryMap.values())
      .map((c) => ({
        ...c,
        _total: c.ships + c.flights + c.uavs + c.satellites + c.bases,
      }))
      .sort((a, b) => b._total - a._total)
      .map(({ _total: _, ...rest }) => rest);

    let tensionScore = 0;
    const gdeltEvents = polling.gdelt as Array<Record<string, unknown>>;
    if (gdeltEvents.length > 0) {
      const scores = gdeltEvents
        .map((e) => Number(e.tension_score ?? e.goldstein_scale ?? 0))
        .filter((n) => !isNaN(n));
      if (scores.length > 0) {
        const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
        tensionScore = Math.min(10, Math.max(0, Math.abs(avg)));
      }
    }

    const recentEvents: RecentEvent[] = [];
    const now = new Date().toISOString().slice(11, 16);

    for (const g of gdeltEvents.slice(0, 3)) {
      recentEvents.push({
        time: (g.date_added as string)?.slice(11, 16) ?? now,
        source: "GDELT",
        category: "info",
        title: (g.title as string) ?? (g.event_description as string) ?? "분쟁 이벤트",
        detail: `Goldstein: ${g.goldstein_scale ?? "N/A"}`,
      });
    }

    for (const n of (polling.news as Array<Record<string, unknown>>).slice(0, 2)) {
      recentEvents.push({
        time: now,
        source: (n.source as string) ?? "News",
        category: "info",
        title: (n.title as string) ?? "",
      });
    }

    for (const q of polling.earthquakes.slice(0, 2)) {
      recentEvents.push({
        time: now,
        source: "지진",
        category: "environment",
        title: `M${q.mag} ${q.place}`,
        lat: q.lat,
        lng: q.lng,
      });
    }

    for (const o of polling.internetOutages.slice(0, 2)) {
      recentEvents.push({
        time: now,
        source: "인터넷",
        category: "infra",
        title: `${o.country_name} — 심각도 ${o.severity}%`,
        lat: o.lat,
        lng: o.lng,
      });
    }

    for (const j of polling.gpsJamming.slice(0, 2)) {
      recentEvents.push({
        time: now,
        source: "GPS 재밍",
        category: "military",
        title: `심각도 ${j.severity}%, 영향 ${j.affected_count}대`,
        lat: j.lat,
        lng: j.lng,
      });
    }

    recentEvents.sort((a, b) => b.time.localeCompare(a.time));

    return {
      tensionScore,
      totalShips: polling.ships.length,
      totalFlights: polling.militaryFlights.length,
      totalUavs: polling.uavs.length,
      totalSatellites: polling.satellites.length,
      totalBases: polling.militaryBases.length,
      totalGpsJamming: polling.gpsJamming.length,
      assetsByCountry,
      recentEvents: recentEvents.slice(0, 8),
    };
  }, [
    polling.ships,
    polling.militaryFlights,
    polling.uavs,
    polling.satellites,
    polling.militaryBases,
    polling.gdelt,
    polling.news,
    polling.earthquakes,
    polling.internetOutages,
    polling.gpsJamming,
  ]);
}
