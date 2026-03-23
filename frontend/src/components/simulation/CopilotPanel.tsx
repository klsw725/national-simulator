"use client";

import { useCallback, useRef, useState } from "react";
import { Send } from "lucide-react";
import * as api from "@/lib/gatewayApi";

interface CopilotPanelProps {
  scenarioId: string | undefined;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  toolsUsed?: string[];
  sources?: string[];
  suggestions?: string[];
}

export default function CopilotPanel({ scenarioId }: CopilotPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const scrollRef = useRef<HTMLDivElement>(null);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!scenarioId || !text.trim()) return;
      const userMsg: ChatMessage = { role: "user", content: text.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      try {
        const result = await api.copilotChat(scenarioId, text.trim(), conversationId);
        setConversationId(result.conversation_id);
        const assistantMsg: ChatMessage = {
          role: "assistant",
          content: result.response,
          toolsUsed: result.tools_used,
          sources: result.sources,
          suggestions: result.suggestions,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (e) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `오류: ${e instanceof Error ? e.message : "요청 실패"}` },
        ]);
      } finally {
        setLoading(false);
        setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }), 50);
      }
    },
    [scenarioId, conversationId]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  if (!scenarioId) {
    return (
      <div style={{ padding: 24, color: "rgb(107, 114, 128)", fontSize: 13, textAlign: "center" }}>
        시나리오를 선택해주세요
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        ref={scrollRef}
        style={{ flex: 1, overflowY: "auto", padding: "12px 16px", display: "flex", flexDirection: "column", gap: 12 }}
      >
        {messages.length === 0 && (
          <div style={{ textAlign: "center", padding: "32px 16px", color: "rgb(75, 85, 99)" }}>
            <div style={{ fontSize: 20, marginBottom: 8 }}>🤖</div>
            <div style={{ fontSize: 12, lineHeight: 1.6 }}>
              시나리오에 대해 질문하세요.
              <br />
              데이터를 검색하고 분석하여 답변합니다.
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 16 }}>
              {[
                "이 시나리오를 요약해줘",
                "가장 공격적인 행위자는?",
                "지정학 이벤트 분포를 분석해줘",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => sendMessage(suggestion)}
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
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
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

            {msg.toolsUsed && msg.toolsUsed.length > 0 && (
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4, paddingLeft: 4 }}>
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
                    onClick={() => sendMessage(s)}
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
          <div style={{ padding: "10px 12px", fontSize: 12, color: "rgb(107, 114, 128)", marginRight: 20 }}>
            분석 중...
          </div>
        )}
      </div>

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
          placeholder="질문을 입력하세요..."
          disabled={loading}
          style={{
            flex: 1,
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 6,
            padding: "8px 12px",
            color: "#f3f4f6",
            fontSize: 12,
            outline: "none",
          }}
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
          style={{
            background: input.trim() ? "var(--accent-cyan)" : "rgba(255,255,255,0.05)",
            border: "none",
            borderRadius: 6,
            padding: "8px 12px",
            cursor: input.trim() ? "pointer" : "default",
            display: "flex",
            alignItems: "center",
          }}
        >
          <Send size={14} color={input.trim() ? "var(--bg-primary)" : "rgb(75, 85, 99)"} />
        </button>
      </div>
    </div>
  );
}
