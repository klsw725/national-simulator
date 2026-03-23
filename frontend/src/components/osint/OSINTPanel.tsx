"use client";

import { useState } from "react";
import type { PollingResult } from "@/hooks/useDataPolling";
import type { OSINTSummary } from "@/hooks/useOSINTSummary";
import OverviewTab from "./OverviewTab";
import AssetsTab from "./AssetsTab";
import FeedTab from "./FeedTab";
import FreshnessTab from "./FreshnessTab";
import TrendTab from "./TrendTab";

type TabId = "overview" | "assets" | "feed" | "freshness" | "trend";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "요약" },
  { id: "assets", label: "자산" },
  { id: "feed", label: "피드" },
  { id: "freshness", label: "선도" },
  { id: "trend", label: "트렌드" },
];

interface OSINTPanelProps {
  open: boolean;
  onClose: () => void;
  polling: PollingResult;
  summary: OSINTSummary;
  onFlyTo?: (lng: number, lat: number) => void;
}

export default function OSINTPanel({
  open,
  onClose,
  polling,
  summary,
  onFlyTo,
}: OSINTPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: 400,
        height: "100vh",
        zIndex: 20,
        background: "rgb(12, 14, 18)",
        borderRight: "1px solid var(--border-secondary)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderBottom: "1px solid var(--border-secondary)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: "#f3f4f6",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          OSINT Situation
        </span>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            color: "rgb(107, 114, 128)",
            cursor: "pointer",
            fontSize: 18,
            lineHeight: 1,
            padding: "2px 6px",
          }}
        >
          ×
        </button>
      </div>

      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-secondary)",
          flexShrink: 0,
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              padding: "8px 4px",
              background: "none",
              border: "none",
              borderBottom:
                activeTab === tab.id
                  ? "2px solid var(--accent-cyan)"
                  : "2px solid transparent",
              color:
                activeTab === tab.id ? "#f3f4f6" : "rgb(107, 114, 128)",
              fontSize: 12,
              fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: "pointer",
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
        {activeTab === "overview" && (
          <OverviewTab summary={summary} polling={polling} />
        )}
        {activeTab === "assets" && (
          <AssetsTab summary={summary} polling={polling} onFlyTo={onFlyTo} />
        )}
        {activeTab === "feed" && <FeedTab summary={summary} polling={polling} onFlyTo={onFlyTo} />}
        {activeTab === "freshness" && (
          <FreshnessTab polling={polling} />
        )}
        {activeTab === "trend" && <TrendTab />}
      </div>
    </div>
  );
}
