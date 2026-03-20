"use client";

import { useMemo } from "react";

interface Props {
  markdown: string;
}

function renderMarkdown(md: string): string {
  const lines = md.split("\n");
  const html: string[] = [];
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Heading ##
    if (/^##\s+(.+)/.test(line)) {
      if (inList) { html.push("</ul>"); inList = false; }
      const text = line.replace(/^##\s+/, "");
      html.push(
        `<h2 style="font-size:15px;font-weight:700;color:var(--accent-cyan);margin:16px 0 8px;border-bottom:1px solid var(--border-secondary);padding-bottom:6px">${esc(text)}</h2>`
      );
      continue;
    }

    // Heading ###
    if (/^###\s+(.+)/.test(line)) {
      if (inList) { html.push("</ul>"); inList = false; }
      const text = line.replace(/^###\s+/, "");
      html.push(
        `<h3 style="font-size:13px;font-weight:600;color:var(--text-primary);margin:12px 0 6px">${esc(text)}</h3>`
      );
      continue;
    }

    // Heading #
    if (/^#\s+(.+)/.test(line)) {
      if (inList) { html.push("</ul>"); inList = false; }
      const text = line.replace(/^#\s+/, "");
      html.push(
        `<h1 style="font-size:17px;font-weight:700;color:var(--text-primary);margin:16px 0 8px">${esc(text)}</h1>`
      );
      continue;
    }

    // List item
    if (/^[-*]\s+(.+)/.test(line)) {
      if (!inList) { html.push('<ul style="margin:4px 0;padding-left:16px">'); inList = true; }
      const text = line.replace(/^[-*]\s+/, "");
      html.push(`<li style="font-size:12px;color:var(--text-primary);line-height:1.5;margin-bottom:2px">${inline(text)}</li>`);
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      if (inList) { html.push("</ul>"); inList = false; }
      continue;
    }

    // Paragraph
    if (inList) { html.push("</ul>"); inList = false; }
    html.push(`<p style="font-size:12px;color:var(--text-primary);line-height:1.6;margin:6px 0">${inline(line)}</p>`);
  }

  if (inList) html.push("</ul>");
  return html.join("\n");
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function inline(s: string): string {
  let out = esc(s);
  // bold
  out = out.replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--text-primary);font-weight:600">$1</strong>');
  // italic
  out = out.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // inline code
  out = out.replace(/`(.+?)`/g, '<code style="background:var(--bg-tertiary);padding:1px 4px;border-radius:3px;font-size:11px">$1</code>');
  return out;
}

export default function ReportViewer({ markdown }: Props) {
  const html = useMemo(() => renderMarkdown(markdown), [markdown]);

  if (!markdown) {
    return (
      <div
        style={{
          padding: 24,
          textAlign: "center",
          color: "var(--text-muted)",
          fontSize: 13,
        }}
      >
        리포트가 없습니다
      </div>
    );
  }

  return (
    <div
      style={{
        maxHeight: 400,
        overflow: "auto",
        padding: "4px 0",
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
