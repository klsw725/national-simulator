"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import * as api from "@/lib/gatewayApi";
import type { Scenario } from "@/types/simulation";

const STATUS_OPTIONS = [
  { value: "", label: "전체 상태" },
  { value: "created", label: "대기" },
  { value: "completed", label: "완료" },
  { value: "failed", label: "실패" },
];

const SORT_OPTIONS = [
  { value: "created_at", label: "생성일" },
  { value: "updated_at", label: "수정일" },
  { value: "name", label: "이름" },
];

interface ScenarioSearchProps {
  onResults: (scenarios: Scenario[], total: number) => void;
}

export default function ScenarioSearch({ onResults }: ScenarioSearchProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState("desc");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const doSearch = useCallback(
    async (q: string, s: string, sortBy: string, orderBy: string) => {
      try {
        const result = await api.searchScenarios({
          q: q || undefined,
          status: s || undefined,
          sort: sortBy,
          order: orderBy,
          limit: 50,
        });
        onResults(result.scenarios, result.total);
      } catch {}
    },
    [onResults]
  );

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      doSearch(query, status, sort, order);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, status, sort, order, doSearch]);

  const selectStyle: React.CSSProperties = {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 4,
    padding: "4px 6px",
    fontSize: 11,
    color: "#d1d5db",
    outline: "none",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 10 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 6,
          padding: "6px 10px",
        }}
      >
        <Search size={14} color="rgb(107, 114, 128)" aria-hidden="true" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="시나리오 검색..."
          aria-label="시나리오 검색"
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "#f3f4f6",
            fontSize: 12,
          }}
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            style={{
              background: "none",
              border: "none",
              color: "rgb(107, 114, 128)",
              cursor: "pointer",
              fontSize: 14,
              padding: 0,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        )}
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="상태 필터" style={selectStyle}>
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="정렬 기준" style={selectStyle}>
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <button
          onClick={() => setOrder(order === "desc" ? "asc" : "desc")}
          aria-label={order === "desc" ? "오름차순 정렬" : "내림차순 정렬"}
          style={{
            ...selectStyle,
            cursor: "pointer",
            minWidth: 28,
            textAlign: "center",
          }}
        >
          {order === "desc" ? "↓" : "↑"}
        </button>
      </div>
    </div>
  );
}
