"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Send, User, Users, Power, Loader2 } from "lucide-react";
import type { EnvStatus } from "@/types/simulation";
import * as api from "@/lib/gatewayApi";

type Mode = "copilot" | "agent-all" | "agent-single";

interface Message {
  role: "user" | "copilot" | "agent";
  content: string;
  agentId?: number;
  agentName?: string;
  platform?: string;
  platforms?: Record<string, { agent_id: number; response: string; platform: string }>;
  toolsUsed?: string[];
  suggestions?: string[];
}

interface Props {
  scenarioId: string | undefined;
}

export default function ConversationPanel({ scenarioId }: Props) {
  const [mode, setMode] = useState<Mode>("copilot");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [agentId, setAgentId] = useState<number>(0);
  const [envStatus, setEnvStatus] = useState<EnvStatus | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const pollEnvStatus = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const status = await api.getEnvStatus(scenarioId);
      setEnvStatus(status);
    } catch (e) {
      setEnvStatus({
        simulation_id: scenarioId,
        env_alive: false,
        reddit_available: false,
        twitter_available: false,
        message: e instanceof Error ? e.message : "에이전트 대화 상태를 확인할 수 없습니다.",
      });
    }
  }, [scenarioId]);

  useEffect(() => {
    pollEnvStatus();
    const interval = setInterval(pollEnvStatus, 10_000);
    return () => clearInterval(interval);
  }, [pollEnvStatus]);

  const envAlive = envStatus?.env_alive ?? false;
  const envMessage = envStatus?.message ?? "에이전트 대화 상태를 확인하는 중입니다.";
  const isInterview = mode !== "copilot";

  const handleSend = useCallback(
    async (text: string) => {
      if (!scenarioId || !text.trim() || loading) return;
      setError(null);

      const userMsg: Message = { role: "user", content: text.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      try {
        if (mode === "copilot") {
          const res = await api.copilotChat(scenarioId, text.trim(), conversationId);
          setConversationId(res.conversation_id);
          setMessages((prev) => [
            ...prev,
            {
              role: "copilot",
              content: res.response,
              toolsUsed: res.tools_used,
              suggestions: res.suggestions,
            },
          ]);
        } else if (mode === "agent-all") {
          const data = await api.interviewAllAgents(scenarioId, text.trim());
          const agentMsgs: Message[] = data.results.map((r) => ({
            role: "agent" as const,
            content: r.response ?? "",
            agentId: r.agent_id,
            agentName: r.agent_name,
            platform: r.platform,
            platforms: r.platforms,
          }));
          setMessages((prev) => [...prev, ...agentMsgs]);
        } else {
          const r = await api.interviewAgent(scenarioId, agentId, text.trim());
          setMessages((prev) => [
            ...prev,
            {
              role: "agent",
              content: r.response ?? "",
              agentId: r.agent_id,
              agentName: r.agent_name,
              platform: r.platform,
              platforms: r.platforms,
            },
          ]);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "요청 실패");
      } finally {
        setLoading(false);
        setTimeout(
          () => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }),
          50,
        );
      }
    },
    [scenarioId, mode, conversationId, agentId, loading],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  const handleCloseEnv = async () => {
    if (!scenarioId || !confirm("시뮬레이션 환경을 종료하시겠습니까?")) return;
    try {
      await api.closeSimulationEnv(scenarioId);
      await pollEnvStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "환경 종료 실패");
    }
  };

  if (!scenarioId) {
    return (
      <div style={{ padding: 24, color: "rgb(107, 114, 128)", fontSize: 13, textAlign: "center" }}>
        시나리오를 선택해주세요
      </div>
    );
  }

  const sendDisabled = loading || !input.trim() || (isInterview && !envAlive);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      <div
        style={{
          padding: "10px 12px",
          borderBottom: "1px solid var(--border-secondary)",
          display: "flex",
          flexDirection: "column",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 0,
            borderRadius: 6,
            overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          {(
            [
              { key: "copilot", label: "코파일럿", icon: <Bot size={12} /> },
              { key: "agent-all", label: "전체 에이전트", icon: <Users size={12} /> },
              { key: "agent-single", label: "개별 에이전트", icon: <User size={12} /> },
            ] as const
          ).map((m, i, arr) => (
            <button
              key={m.key}
              onClick={() => setMode(m.key)}
              style={{
                flex: 1,
                padding: "7px 10px",
                background: mode === m.key ? "rgba(34, 211, 238, 0.1)" : "transparent",
                border: "none",
                borderRight: i < arr.length - 1 ? "1px solid rgba(255,255,255,0.08)" : "none",
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

        {mode === "agent-single" && (
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

        {isInterview && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
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
              }}
            >
              {envAlive && (
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "rgb(74, 222, 128)",
                    animation: "convPulse 1.5s ease-in-out infinite",
                  }}
                />
              )}
              {envAlive ? "ENV 활성" : "ENV 비활성"}
            </span>
            {envAlive && (
              <button
                onClick={handleCloseEnv}
                style={{
                  padding: "3px 8px",
                  background: "rgba(239, 68, 68, 0.08)",
                  border: "1px solid rgba(239, 68, 68, 0.2)",
                  borderRadius: 4,
                  color: "rgb(239, 68, 68)",
                  fontSize: 10,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <Power size={10} />
                종료
              </button>
            )}
          </div>
        )}

        {isInterview && (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: 6,
              background: envAlive ? "rgba(74, 222, 128, 0.08)" : "rgba(245, 158, 11, 0.08)",
              border: envAlive ? "1px solid rgba(74, 222, 128, 0.18)" : "1px solid rgba(245, 158, 11, 0.18)",
              color: envAlive ? "rgb(187, 247, 208)" : "rgb(252, 211, 77)",
              fontSize: 11,
              lineHeight: 1.5,
            }}
          >
            {envMessage}
          </div>
        )}
      </div>


      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.length === 0 && (
          <div style={{ textAlign: "center", padding: "32px 16px", color: "rgb(75, 85, 99)" }}>
            <div style={{ fontSize: 20, marginBottom: 8 }}>{mode === "copilot" ? "🤖" : "💬"}</div>
            <div style={{ fontSize: 12, lineHeight: 1.6 }}>
              {mode === "copilot" ? (
                <>
                  시나리오에 대해 질문하세요.
                  <br />
                  데이터를 검색하고 분석하여 답변합니다.
                </>
              ) : (
                <>
                  {envAlive ? "에이전트에게 질문하여" : "현재 에이전트 대화 ENV가 비활성 상태입니다."}
                  <br />
                  {envAlive ? "인터뷰 결과를 확인하세요" : "코파일럿 모드를 사용하거나 ENV 연결 후 다시 시도하세요"}
                </>
              )}
            </div>
            {mode === "copilot" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 16 }}>
                {["이 시나리오를 요약해줘", "가장 공격적인 행위자는?", "지정학 이벤트 분포를 분석해줘"].map(
                  (s) => (
                    <button
                      key={s}
                      onClick={() => handleSend(s)}
                      style={{
                        padding: "8px 12px",
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 6,
                        color: "#9ca3af",
                        fontSize: 11,
                        cursor: "pointer",
                        textAlign: "left",
                      }}
                    >
                      {s}
                    </button>
                  ),
                )}
              </div>
            )}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role !== "user" && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  marginBottom: 4,
                  paddingLeft: 2,
                }}
              >
                {msg.role === "copilot" ? (
                  <>
                    <Bot size={11} style={{ color: "var(--accent-cyan)" }} />
                    <span style={{ fontSize: 10, fontWeight: 600, color: "var(--accent-cyan)" }}>
                      코파일럿
                    </span>
                  </>
                ) : (
                  <>
                    <User size={11} style={{ color: "rgb(34, 211, 238)" }} />
                    <span style={{ fontSize: 10, fontWeight: 600, color: "rgb(34, 211, 238)" }}>
                      {msg.agentName ?? `에이전트 #${msg.agentId}`}
                    </span>
                    {msg.platform && (
                      <span
                        style={{
                          fontSize: 9,
                          padding: "1px 5px",
                          borderRadius: 3,
                          background: "rgba(168, 85, 247, 0.1)",
                          color: "#a855f7",
                        }}
                      >
                        {msg.platform}
                      </span>
                    )}
                  </>
                )}
              </div>
            )}

            <div
              style={{
                padding: "10px 12px",
                borderRadius: 8,
                fontSize: 12,
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                ...(msg.role === "user"
                  ? {
                      background: "rgba(34, 211, 238, 0.08)",
                      border: "1px solid rgba(34, 211, 238, 0.15)",
                      color: "#d1d5db",
                      marginLeft: 40,
                    }
                  : {
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.05)",
                      color: "#d1d5db",
                      marginRight: 20,
                    }),
              }}
            >
              {msg.content}
            </div>

            {msg.platforms &&
              Object.entries(msg.platforms).map(([platform, data]) => (
                <div
                  key={platform}
                  style={{
                    marginTop: 6,
                    fontSize: 12,
                    color: "rgb(209, 213, 219)",
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    padding: "6px 8px",
                    background: "rgba(255,255,255,0.02)",
                    borderRadius: 4,
                    borderLeft: "2px solid rgba(168, 85, 247, 0.3)",
                    marginRight: 20,
                  }}
                >
                  <span style={{ fontSize: 9, color: "#a855f7", fontWeight: 600 }}>[{platform}]</span>
                  <br />
                  {data.response}
                </div>
              ))}

            {msg.toolsUsed && msg.toolsUsed.length > 0 && (
              <div
                style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4, paddingLeft: 4 }}
              >
                {msg.toolsUsed.map((tool) => (
                  <span
                    key={tool}
                    style={{
                      fontSize: 9,
                      padding: "2px 6px",
                      borderRadius: 3,
                      background: "rgba(168, 85, 247, 0.1)",
                      color: "#a855f7",
                    }}
                  >
                    🔧 {tool}
                  </span>
                ))}
              </div>
            )}

            {msg.suggestions && msg.suggestions.length > 0 && i === messages.length - 1 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                {msg.suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSend(s)}
                    disabled={loading}
                    style={{
                      padding: "6px 10px",
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: 4,
                      color: "#9ca3af",
                      fontSize: 11,
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    → {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div
            style={{
              padding: "10px 12px",
              fontSize: 12,
              color: "rgb(107, 114, 128)",
              marginRight: 20,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Loader2 size={12} style={{ animation: "convSpin 1s linear infinite" }} />
            {mode === "copilot" ? "분석 중..." : "응답 대기 중..."}
          </div>
        )}
      </div>


      {error && (
        <div
          style={{
            margin: "0 12px 8px",
            padding: "8px 10px",
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.2)",
            borderRadius: 4,
            fontSize: 11,
            color: "rgb(239, 68, 68)",
            flexShrink: 0,
          }}
        >
          {error}
        </div>
      )}


      <div
        style={{
          borderTop: "1px solid var(--border-secondary)",
          padding: "10px 12px",
          display: "flex",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isInterview ? (envAlive ? "에이전트에게 질문하세요..." : "에이전트 대화 ENV가 비활성입니다") : "질문을 입력하세요..."}
          disabled={loading || (isInterview && !envAlive)}
          style={{
            flex: 1,
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 6,
            padding: "8px 12px",
            color: "#f3f4f6",
            fontSize: 12,
            outline: "none",
            opacity: isInterview && !envAlive ? 0.5 : 1,
          }}
        />
        <button
          onClick={() => handleSend(input)}
          disabled={sendDisabled}
          style={{
            background: !sendDisabled ? "var(--accent-cyan)" : "rgba(255,255,255,0.05)",
            border: "none",
            borderRadius: 6,
            padding: "8px 12px",
            cursor: !sendDisabled ? "pointer" : "default",
            display: "flex",
            alignItems: "center",
          }}
        >
          <Send size={14} color={!sendDisabled ? "var(--bg-primary)" : "rgb(75, 85, 99)"} />
        </button>
      </div>

      <style>{`
        @keyframes convPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes convSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
