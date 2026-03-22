"use client";

import { useEffect, useState, useCallback } from "react";
import { Activity, Wifi, WifiOff, Database, RefreshCw, Shield } from "lucide-react";
import { getHealthDetailed } from "@/lib/gatewayApi";

interface ServiceHealth {
  status: string;
  latency_ms?: number;
  circuit_breaker?: string;
  failure_count?: number;
}

interface HealthData {
  status: string;
  services: Record<string, ServiceHealth>;
}

const SERVICE_META: Record<string, { label: string; icon: typeof Activity }> = {
  gateway: { label: "Gateway", icon: Shield },
  mirofish: { label: "MiroFish", icon: Activity },
  shadowbroker: { label: "ShadowBroker", icon: Wifi },
  database: { label: "Database", icon: Database },
};

const CB_COLORS: Record<string, string> = {
  closed: "var(--status-connected)",
  open: "var(--accent-red)",
  "half-open": "var(--accent-amber)",
};

function StatusDot({ healthy }: { healthy: boolean }) {
  return (
    <span
      style={{
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: healthy ? "var(--status-connected)" : "var(--accent-red)",
        display: "inline-block",
        flexShrink: 0,
      }}
    />
  );
}

function CircuitBadge({ state }: { state: string }) {
  const color = CB_COLORS[state] ?? "var(--text-muted)";
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: "1px 7px",
        borderRadius: 999,
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
        color,
        textTransform: "capitalize",
      }}
    >
      {state}
    </span>
  );
}

function ServiceCard({ name, service }: { name: string; service: ServiceHealth }) {
  const meta = SERVICE_META[name] ?? { label: name, icon: Activity };
  const Icon = meta.icon;
  const healthy = service.status === "healthy";

  return (
    <div
      style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border-secondary)",
        borderRadius: 6,
        padding: 10,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Icon size={12} color={healthy ? "var(--accent-cyan)" : "var(--accent-red)"} />
          <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
            {meta.label}
          </span>
        </div>
        <StatusDot healthy={healthy} />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        {service.latency_ms != null && (
          <span style={{ fontSize: 12, fontFamily: "monospace", color: "var(--text-muted)" }}>
            {service.latency_ms}ms
          </span>
        )}
        {service.circuit_breaker && <CircuitBadge state={service.circuit_breaker} />}
        {(service.failure_count ?? 0) > 0 && (
          <span style={{ fontSize: 11, color: "var(--accent-red)", fontWeight: 600 }}>
            {service.failure_count} failures
          </span>
        )}
      </div>
    </div>
  );
}

export default function HealthDashboard() {
  const [data, setData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getHealthDetailed();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Health check failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, [refresh]);

  const healthy = data?.status === "healthy";

  return (
    <div
      style={{
        border: "1px solid var(--border-secondary)",
        borderRadius: 6,
        background: "var(--bg-secondary)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {data ? (
            healthy ? (
              <Wifi size={13} color="var(--status-connected)" />
            ) : (
              <WifiOff size={13} color="var(--accent-amber)" />
            )
          ) : (
            <Activity size={13} color="var(--text-muted)" />
          )}
          <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
            Service Health
          </span>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          style={{
            background: "transparent",
            border: "1px solid var(--border-secondary)",
            borderRadius: 4,
            padding: "3px 6px",
            cursor: loading ? "default" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: loading ? 0.5 : 1,
          }}
        >
          <RefreshCw
            size={12}
            color="var(--text-muted)"
            style={{
              animation: loading ? "health-spin 1s linear infinite" : "none",
            }}
          />
          <style>{`@keyframes health-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
        </button>
      </div>

      {data && (
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            padding: "4px 8px",
            borderRadius: 4,
            textAlign: "center",
            background: healthy
              ? "rgba(34, 197, 94, 0.1)"
              : "rgba(245, 158, 11, 0.12)",
            color: healthy
              ? "var(--status-connected)"
              : "var(--accent-amber)",
            border: healthy
              ? "1px solid rgba(34, 197, 94, 0.2)"
              : "1px solid rgba(245, 158, 11, 0.25)",
          }}
        >
          {healthy ? "All systems operational" : "Degraded performance"}
        </div>
      )}

      {error && (
        <div
          style={{
            fontSize: 11,
            padding: "4px 8px",
            borderRadius: 4,
            background: "rgba(239, 68, 68, 0.1)",
            color: "var(--accent-red)",
            border: "1px solid rgba(239, 68, 68, 0.2)",
          }}
        >
          {error}
        </div>
      )}

      {data && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {Object.entries(data.services).map(([name, service]) => (
            <ServiceCard key={name} name={name} service={service} />
          ))}
        </div>
      )}

      {!data && !error && (
        <div style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: 8 }}>
          Loading...
        </div>
      )}
    </div>
  );
}
