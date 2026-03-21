"""DuckDuckGo 웹 검색 서비스.

시드 문서 보강을 위한 뉴스/웹 검색.
API 키 불필요. 인메모리 캐시 + 레이트 리밋.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

MAX_SEARCHES_PER_SEED = 3
CACHE_TTL = 3600  # 1시간


class WebSearchService:
    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    def _get_cached(self, key: str) -> list[dict] | None:
        entry = self._cache.get(key)
        if entry and (time.time() - entry[0]) < CACHE_TTL:
            return entry[1]
        if entry:
            del self._cache[key]
        return None

    def _set_cache(self, key: str, results: list[dict]) -> None:
        self._cache[key] = (time.time(), results)

    def search_news(self, keywords: list[str]) -> list[dict[str, Any]]:
        """DuckDuckGo 뉴스 검색. 동기 호출.

        Args:
            keywords: 검색 키워드 리스트 (최대 MAX_SEARCHES_PER_SEED개 사용)

        Returns:
            [{title, url, body, source, date}, ...]
        """
        all_results: list[dict[str, Any]] = []

        for keyword in keywords[:MAX_SEARCHES_PER_SEED]:
            cached = self._get_cached(f"news:{keyword}")
            if cached is not None:
                all_results.extend(cached)
                continue

            try:
                with DDGS() as ddgs:
                    results = list(ddgs.news(keyword, max_results=self.max_results))
                self._set_cache(f"news:{keyword}", results)
                all_results.extend(results)
                logger.info("Web search: %d news results for '%s'", len(results), keyword)
            except Exception:
                logger.warning("DuckDuckGo news search failed for '%s'", keyword, exc_info=True)

        return all_results

    def format_for_seed(self, results: list[dict[str, Any]]) -> str:
        """검색 결과를 시드 문서 삽입용 마크다운으로 포맷."""
        if not results:
            return ""

        seen_titles: set[str] = set()
        lines: list[str] = []

        for item in results:
            title = item.get("title", "")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            source = item.get("source", "")
            body = item.get("body", "")
            date = item.get("date", "")

            line = f"- **{title}**"
            if source:
                line += f" ({source})"
            if date:
                line += f" [{date[:10]}]"
            if body:
                line += f"\n  {body[:150]}"
            lines.append(line)

        return "\n".join(lines[:8])  # 최대 8개 기사

    @staticmethod
    def extract_keywords(question: str, region_name: str, actors: list[str] | None = None) -> list[str]:
        """시나리오 정보에서 검색 키워드 추출."""
        keywords: list[str] = []

        if region_name:
            keywords.append(f"{region_name} military tension")

        if question:
            # 질문에서 핵심 단어 추출 (간단한 휴리스틱)
            keywords.append(f"{region_name} {question[:50]}" if region_name else question[:80])

        if actors:
            actor_str = " ".join(actors[:3])
            keywords.append(f"{actor_str} naval conflict")

        return keywords[:MAX_SEARCHES_PER_SEED]
