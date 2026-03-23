"use client";

import { useCallback, useState } from "react";
import * as api from "@/lib/gatewayApi";
import BriefingEditor from "./BriefingEditor";

interface ExportPanelProps {
  scenarioId: string | undefined;
}

interface BriefingData {
  id: string;
  content: string;
  version: number;
}

type ExportType = "json" | "csv" | "observations" | "geopolitics" | "report";

const EXPORT_ITEMS: { type: ExportType; label: string; ext: string }[] = [
  { type: "json", label: "시나리오 전체 (JSON)", ext: "json" },
  { type: "csv", label: "시뮬레이션 액션 (CSV)", ext: "csv" },
  { type: "observations", label: "관측 데이터 (CSV)", ext: "csv" },
  { type: "geopolitics", label: "지정학 이벤트 (CSV)", ext: "csv" },
  { type: "report", label: "MiroFish 보고서 (MD)", ext: "md" },
];

export default function ExportPanel({ scenarioId }: ExportPanelProps) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [generatingBriefing, setGeneratingBriefing] = useState(false);
  const [briefingError, setBriefingError] = useState<string | null>(null);
  const [showEditor, setShowEditor] = useState(false);

  const handleDownload = useCallback(
    async (type: ExportType, ext: string) => {
      if (!scenarioId) return;
      setDownloading(type);
      try {
        if (type === "json") {
          const data = await api.exportScenarioJSON(scenarioId);
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          triggerDownload(blob, `scenario_${scenarioId}.${ext}`);
        } else {
          const blob = await api.downloadExport(scenarioId, type);
          triggerDownload(blob, `scenario_${scenarioId}_${type}.${ext}`);
        }
      } catch (e) {
        console.error("Export failed:", e);
      } finally {
        setDownloading(null);
      }
    },
    [scenarioId]
  );

  const handleGenerateBriefing = useCallback(async () => {
    if (!scenarioId) return;
    setGeneratingBriefing(true);
    setBriefingError(null);
    try {
      const result = await api.generateBriefing(scenarioId);
      setBriefing({ id: result.id, content: result.content, version: result.version });
      setShowEditor(true);
    } catch (e) {
      setBriefingError(e instanceof Error ? e.message : "브리핑 생성 실패");
    } finally {
      setGeneratingBriefing(false);
    }
  }, [scenarioId]);

  const handleLoadBriefing = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const result = await api.getBriefing(scenarioId);
      if (result) {
        setBriefing({ id: result.id, content: result.content, version: result.version });
        setShowEditor(true);
      }
    } catch {}
  }, [scenarioId]);

  const handleSaveBriefing = useCallback(
    async (content: string) => {
      if (!scenarioId) return;
      const result = await api.updateBriefing(scenarioId, content);
      setBriefing((prev) =>
        prev ? { ...prev, content: result.content, version: result.version } : null
      );
    },
    [scenarioId]
  );

  if (!scenarioId) {
    return (
      <div style={{ padding: 24, color: "rgb(107, 114, 128)", fontSize: 13, textAlign: "center" }}>
        시나리오를 선택해주세요
      </div>
    );
  }

  if (showEditor && briefing) {
    return (
      <BriefingEditor
        content={briefing.content}
        version={briefing.version}
        onSave={handleSaveBriefing}
        onBack={() => setShowEditor(false)}
      />
    );
  }

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <Section title="데이터 내보내기">
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {EXPORT_ITEMS.map(({ type, label, ext }) => (
            <button
              key={type}
              onClick={() => handleDownload(type, ext)}
              disabled={downloading !== null}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 12px",
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 6,
                color: "#d1d5db",
                fontSize: 12,
                cursor: downloading ? "wait" : "pointer",
                opacity: downloading && downloading !== type ? 0.5 : 1,
              }}
            >
              <span>{label}</span>
              <span style={{ fontSize: 11, color: "rgb(107, 114, 128)" }}>
                {downloading === type ? "다운로드 중..." : "↓"}
              </span>
            </button>
          ))}
        </div>
      </Section>

      <Section title="AI 브리핑">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <p style={{ fontSize: 11, color: "rgb(107, 114, 128)", margin: 0, lineHeight: 1.5 }}>
            시뮬레이션 결과를 LLM이 분석하여 전문적인 브리핑 문서를 자동 생성합니다.
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleGenerateBriefing}
              disabled={generatingBriefing}
              style={{
                flex: 1,
                padding: "8px 12px",
                background: "var(--accent-cyan)",
                border: "none",
                borderRadius: 6,
                color: "var(--bg-primary)",
                fontSize: 12,
                fontWeight: 600,
                cursor: generatingBriefing ? "wait" : "pointer",
                opacity: generatingBriefing ? 0.7 : 1,
              }}
            >
              {generatingBriefing ? "생성 중..." : "브리핑 생성"}
            </button>
            <button
              onClick={handleLoadBriefing}
              style={{
                padding: "8px 12px",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 6,
                color: "#d1d5db",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              불러오기
            </button>
          </div>
          {briefingError && (
            <div style={{ fontSize: 11, color: "#ef4444" }}>{briefingError}</div>
          )}
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          color: "rgb(107, 114, 128)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 8,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
