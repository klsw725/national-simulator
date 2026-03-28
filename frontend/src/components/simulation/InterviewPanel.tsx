"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquare, Send, Users, User, Power, Loader2 } from "lucide-react";
import type { InterviewResult, EnvStatus } from "@/types/simulation";
import * as api from "@/lib/gatewayApi";

interface Props {
  scenarioId: string;
}

type Mode = "all" | "single";

export default function InterviewPanel({ scenarioId }: Props) {
  const [envStatus, setEnvStatus] = useState<EnvStatus | null>(null);
  const [mode, setMode] = useState<Mode>("all");
  const [agentId, setAgentId] = useState<number>(0);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<InterviewResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const pollEnvStatus = useCallback(async () => {
    try {
      const status = await api.getEnvStatus(scenarioId);
      setEnvStatus(status);
    } catch {
      setEnvStatus(null);
    }
  }, [scenarioId]);

  useEffect(() => {
    pollEnvStatus();
    const interval = setInterval(pollEnvStatus, 10_000);
    return () => clearInterval(interval);
  }, [pollEnvStatus]);

  const handleSend = async () => {
    if (!prompt.trim() || loading) return;
    setError(null);
    setLoading(true);

    try {
      if (mode === "all") {
        const data = await api.interviewAllAgents(scenarioId, prompt.trim());
        setResults((prev) => [...data.results.reverse(), ...prev]);
      } else {
        const data = await api.interviewAgent(scenarioId, agentId, prompt.trim());
        setResults((prev) => [data, ...prev]);
      }
      setPrompt("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "인터뷰 요청 실패");
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" }), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCloseEnv = async () => {
    if (!confirm("시뮬레이션 환경을 종료하시겠습니까?")) return;
    try {
      await api.closeSimulationEnv(scenarioId);
      await pollEnvStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "환경 종료 실패");
    }
  };

  const envAlive = envStatus?.env_alive ?? false;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <MessageSquare size={14} style={{ color: "var(--accent-cyan)" }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
          에이전트 인터뷰
        </span>
        <span
          style={{
            fontSize: 10,
            padding: "2px 8px",
            borderRadius: 999,
            background: envAlive ? "rgba(74, 222, 128, 0.12)" : "rgba(239, 68, 68, 0.12)",
            color: envAlive ? "rgb(74, 222, 128)" : "rgb(239, 68, 68)",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 4,
            marginLeft: "auto",
          }}
        >
          {envAlive && (
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "rgb(74, 222, 128)",
                animation: "interviewPulse 1.5s ease-in-out infinite",
              }}
            />
          )}
          {envAlive ? "ENV 활성" : "ENV 비활성"}
        </span>
      </div>

      <div style={{ display: "flex", gap: 0, borderRadius: 6, overflow: "hidden", border: "1px solid rgba(255,255,255,0.08)" }}>
        {([
          { key: "all" as Mode, label: "전체 인터뷰", icon: <Users size={12} /> },
          { key: "single" as Mode, label: "개별 인터뷰", icon: <User size={12} /> },
        ]).map((m) => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            style={{
              flex: 1,
              padding: "7px 10px",
              background: mode === m.key ? "rgba(34, 211, 238, 0.1)" : "transparent",
              border: "none",
              borderRight: m.key === "all" ? "1px solid rgba(255,255,255,0.08)" : "none",
              color: mode === m.key ? "rgb(34, 211, 238)" : "rgb(156, 163, 175)",
              fontSize: 11,
              fontWeight: mode === m.key ? 600 : 400,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 5,
              transition: "all 0.15s ease",
            }}
          >
            {m.icon}
            {m.label}
          </button>
        ))}
      </div>

      {mode === "single" && (
        <select
          value={agentId}
          onChange={(e) => setAgentId(Number(e.target.value))}
          style={{
            width: "100%",
            padding: "7px 10px",
            background: "rgb(12, 14, 18)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 4,
            color: "rgb(243, 244, 246)",
            fontSize: 12,
            outline: "none",
          }}
        >
          {Array.from({ length: 13 }, (_, i) => (
            <option key={i} value={i}>
              에이전트 #{i}
            </option>
          ))}
        </select>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="에이전트에게 질문하세요..."
          rows={3}
          disabled={loading}
          style={{
            width: "100%",
            padding: "8px 10px",
            background: "rgb(12, 14, 18)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 4,
            color: "rgb(243, 244, 246)",
            fontSize: 12,
            lineHeight: 1.5,
            outline: "none",
            resize: "vertical",
            fontFamily: "inherit",
            opacity: loading ? 0.5 : 1,
          }}
        />
        <button
          onClick={handleSend}
          disabled={!prompt.trim() || loading}
          style={{
            width: "100%",
            padding: "8px 12px",
            background: prompt.trim() && !loading ? "var(--accent-cyan)" : "rgba(255,255,255,0.05)",
            border: "none",
            borderRadius: 4,
            color: prompt.trim() && !loading ? "var(--bg-primary)" : "rgb(156, 163, 175)",
            fontSize: 12,
            fontWeight: 700,
            cursor: prompt.trim() && !loading ? "pointer" : "not-allowed",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            transition: "background 0.15s, color 0.15s",
          }}
        >
          {loading ? <Loader2 size={13} style={{ animation: "interviewSpin 1s linear infinite" }} /> : <Send size={12} />}
          {loading ? "요청 중..." : mode === "all" ? "전체 에이전트에게 질문" : `에이전트 #${agentId}에게 질문`}
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: "8px 10px",
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.2)",
            borderRadius: 4,
            fontSize: 11,
            color: "rgb(239, 68, 68)",
          }}
        >
          {error}
        </div>
      )}

      <div
        ref={scrollRef}
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          maxHeight: 360,
          overflowY: "auto",
          scrollbarWidth: "thin",
        }}
      >
        {results.length === 0 && !loading && (
          <div style={{ textAlign: "center", padding: "24px 16px", color: "rgb(107, 114, 128)" }}>
            <MessageSquare size={20} style={{ marginBottom: 8, opacity: 0.5 }} />
            <div style={{ fontSize: 12, lineHeight: 1.5 }}>
              에이전트에게 질문하여
              <br />
              인터뷰 결과를 확인하세요
            </div>
          </div>
        )}

        {results.map((r, i) => (
          <div
            key={`${r.agent_id}-${r.timestamp ?? i}`}
            style={{
              padding: "10px 12px",
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: 6,
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <User size={11} style={{ color: "rgb(34, 211, 238)" }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: "rgb(34, 211, 238)" }}>
                {r.agent_name ?? `에이전트 #${r.agent_id}`}
              </span>
              {r.platform && (
                <span
                  style={{
                    fontSize: 9,
                    padding: "1px 5px",
                    borderRadius: 3,
                    background: "rgba(168, 85, 247, 0.1)",
                    color: "#a855f7",
                    marginLeft: "auto",
                  }}
                >
                  {r.platform}
                </span>
              )}
            </div>

            <div style={{ fontSize: 11, color: "rgb(156, 163, 175)", lineHeight: 1.4 }}>
              <span style={{ fontWeight: 600, color: "rgb(243, 244, 246)" }}>Q: </span>
              {r.prompt}
            </div>

            {r.response && (
              <div
                style={{
                  fontSize: 12,
                  color: "rgb(209, 213, 219)",
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  padding: "6px 8px",
                  background: "rgba(255,255,255,0.02)",
                  borderRadius: 4,
                  borderLeft: "2px solid rgba(34, 211, 238, 0.3)",
                }}
              >
                {r.response}
              </div>
            )}

            {r.platforms && Object.entries(r.platforms).map(([platform, data]) => (
              <div
                key={platform}
                style={{
                  fontSize: 12,
                  color: "rgb(209, 213, 219)",
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  padding: "6px 8px",
                  background: "rgba(255,255,255,0.02)",
                  borderRadius: 4,
                  borderLeft: "2px solid rgba(168, 85, 247, 0.3)",
                }}
              >
                <span style={{ fontSize: 9, color: "#a855f7", fontWeight: 600 }}>[{platform}]</span>
                <br />
                {data.response}
              </div>
            ))}
          </div>
        ))}
      </div>

      {envAlive && (
        <button
          onClick={handleCloseEnv}
          style={{
            width: "100%",
            padding: "8px 12px",
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.2)",
            borderRadius: 4,
            color: "rgb(239, 68, 68)",
            fontSize: 11,
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            marginTop: 4,
          }}
        >
          <Power size={12} />
          시뮬레이션 환경 종료
        </button>
      )}

      <style>{`
        @keyframes interviewPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes interviewSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
