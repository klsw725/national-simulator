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
      <div className="p-6 text-[rgb(107,114,128)] text-[13px] text-center">
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
    <div className="p-4 flex flex-col gap-4">
      <Section title="데이터 내보내기">
        <div className="flex flex-col gap-1.5">
          {EXPORT_ITEMS.map(({ type, label, ext }) => (
            <button
              key={type}
              onClick={() => handleDownload(type, ext)}
              disabled={downloading !== null}
              className="flex items-center justify-between px-3 py-2 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.08)] rounded-md text-[#d1d5db] text-xs"
              style={{
                cursor: downloading ? "wait" : "pointer",
                opacity: downloading && downloading !== type ? 0.5 : 1,
              }}
            >
              <span>{label}</span>
              <span className="text-[11px] text-[rgb(107,114,128)]">
                {downloading === type ? "다운로드 중..." : "↓"}
              </span>
            </button>
          ))}
        </div>
      </Section>

      <Section title="AI 브리핑">
        <div className="flex flex-col gap-2">
          <p className="text-[11px] text-[rgb(107,114,128)] m-0 leading-normal">
            시뮬레이션 결과를 LLM이 분석하여 전문적인 브리핑 문서를 자동 생성합니다.
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleGenerateBriefing}
              disabled={generatingBriefing}
              className="flex-1 px-3 py-2 bg-[var(--accent-cyan)] border-none rounded-md text-[var(--bg-primary)] text-xs font-semibold"
              style={{
                cursor: generatingBriefing ? "wait" : "pointer",
                opacity: generatingBriefing ? 0.7 : 1,
              }}
            >
              {generatingBriefing ? "생성 중..." : "브리핑 생성"}
            </button>
            <button
              onClick={handleLoadBriefing}
              className="px-3 py-2 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-md text-[#d1d5db] text-xs cursor-pointer"
            >
              불러오기
            </button>
          </div>
          {briefingError && (
            <div className="text-[11px] text-[#ef4444]">{briefingError}</div>
          )}
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] font-semibold text-[rgb(107,114,128)] uppercase tracking-wider mb-2">
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
