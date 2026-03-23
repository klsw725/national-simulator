"use client";

import { useCallback, useState } from "react";

interface BriefingEditorProps {
  content: string;
  version: number;
  onSave: (content: string) => Promise<void>;
  onBack: () => void;
}

export default function BriefingEditor({
  content,
  version,
  onSave,
  onBack,
}: BriefingEditorProps) {
  const [text, setText] = useState(content);
  const [preview, setPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const hasChanges = text !== content;

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaved(false);
    try {
      await onSave(text);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }, [text, onSave]);

  const handleExport = useCallback(() => {
    const blob = new Blob([text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "briefing.md";
    a.click();
    URL.revokeObjectURL(url);
  }, [text]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderBottom: "1px solid var(--border-secondary)",
          flexShrink: 0,
        }}
      >
        <button
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            color: "rgb(107, 114, 128)",
            cursor: "pointer",
            fontSize: 14,
            padding: "2px 6px",
          }}
        >
          ←
        </button>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#f3f4f6", flex: 1 }}>
          브리핑 편집기
        </span>
        <span style={{ fontSize: 10, color: "rgb(75, 85, 99)" }}>v{version}</span>
      </div>

      <div
        style={{
          display: "flex",
          gap: 4,
          padding: "6px 12px",
          borderBottom: "1px solid var(--border-secondary)",
          flexShrink: 0,
        }}
      >
        <button
          onClick={() => setPreview(false)}
          style={{
            padding: "4px 10px",
            borderRadius: 4,
            fontSize: 11,
            border: "none",
            background: !preview ? "rgba(34, 211, 238, 0.1)" : "transparent",
            color: !preview ? "#22d3ee" : "rgb(107, 114, 128)",
            cursor: "pointer",
          }}
        >
          편집
        </button>
        <button
          onClick={() => setPreview(true)}
          style={{
            padding: "4px 10px",
            borderRadius: 4,
            fontSize: 11,
            border: "none",
            background: preview ? "rgba(34, 211, 238, 0.1)" : "transparent",
            color: preview ? "#22d3ee" : "rgb(107, 114, 128)",
            cursor: "pointer",
          }}
        >
          미리보기
        </button>
        <div style={{ flex: 1 }} />
        <button
          onClick={handleExport}
          style={{
            padding: "4px 10px",
            borderRadius: 4,
            fontSize: 11,
            border: "1px solid rgba(255,255,255,0.1)",
            background: "transparent",
            color: "#d1d5db",
            cursor: "pointer",
          }}
        >
          내보내기
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges}
          style={{
            padding: "4px 12px",
            borderRadius: 4,
            fontSize: 11,
            border: "none",
            background: hasChanges ? "var(--accent-cyan)" : "rgba(255,255,255,0.05)",
            color: hasChanges ? "var(--bg-primary)" : "rgb(75, 85, 99)",
            fontWeight: 600,
            cursor: hasChanges ? "pointer" : "default",
            opacity: saving ? 0.7 : 1,
          }}
        >
          {saving ? "저장 중..." : saved ? "저장됨 ✓" : "저장"}
        </button>
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {preview ? (
          <div
            style={{
              padding: 16,
              fontSize: 12,
              lineHeight: 1.7,
              color: "#d1d5db",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {text}
          </div>
        ) : (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{
              width: "100%",
              height: "100%",
              background: "transparent",
              border: "none",
              outline: "none",
              color: "#d1d5db",
              fontSize: 12,
              lineHeight: 1.6,
              padding: 16,
              resize: "none",
              fontFamily: "monospace",
            }}
          />
        )}
      </div>
    </div>
  );
}
