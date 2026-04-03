from __future__ import annotations

from typing import Any

import networkx as nx
from openai import AsyncOpenAI

from app.config import settings

NARRATIVE_PROMPT = """\
당신은 지정학 분석관입니다. 아래의 인과 분석 결과를 전문적인 브리핑 형식으로 설명하세요.

인과 경로:
{causal_paths}

각 경로의 인과 강도:
{attributions}

규칙:
- 인과 경로를 따라 "A → B → C" 형식으로 메커니즘을 설명
- 각 단계의 기여도(%)를 포함
- "시뮬레이션 데이터 기반 추정치"임을 명시
- 추측이 아닌 데이터 기반 결과만 서술
- 한국어로 작성
"""


class CausalNarrator:
    def __init__(self):
        self._llm = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    async def generate_narrative(
        self,
        dag: nx.DiGraph,
        target_variable: str,
        attributions: dict[str, float] | None = None,
        context: str = "",
    ) -> str:
        attributions = attributions or {}
        if target_variable not in dag.nodes:
            return "인과 내러티브를 생성할 수 없습니다. 대상 변수가 DAG에 없습니다."

        path_entries: list[dict[str, Any]] = []
        ancestors = sorted(nx.ancestors(dag, target_variable))

        for source in ancestors:
            if len(path_entries) >= 5:
                break
            try:
                for path in nx.all_simple_paths(dag, source=source, target=target_variable):
                    path_score = self._score_path(path, attributions)
                    path_entries.append(
                        {
                            "path": path,
                            "path_text": " → ".join(path),
                            "contribution_pct": round(path_score * 100, 1),
                        },
                    )
                    if len(path_entries) >= 5:
                        break
            except nx.NetworkXNoPath:
                continue

        if not path_entries:
            path_entries = [{"path": [target_variable], "path_text": target_variable, "contribution_pct": 0.0}]

        causal_paths = "\n".join(
            [f"- {entry['path_text']}" for entry in path_entries],
        )
        attribution_lines = "\n".join(
            [f"- {entry['path_text']}: {entry['contribution_pct']}%" for entry in path_entries],
        )
        if context.strip():
            attribution_lines = f"{attribution_lines}\n\n추가 컨텍스트:\n{context.strip()}"

        response = await self._llm.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {
                    "role": "user",
                    "content": NARRATIVE_PROMPT.format(
                        causal_paths=causal_paths,
                        attributions=attribution_lines,
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=2048,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        from app.utils.llm_compat import extract_content

        return extract_content(response.choices[0].message)

    async def enrich_briefing(
        self,
        briefing_text: str,
        dag: nx.DiGraph,
        attributions: dict[str, float] | None = None,
    ) -> str:
        if not attributions:
            return briefing_text

        target_variable = self._infer_target_variable(dag, attributions)
        if not target_variable:
            return briefing_text

        narrative = await self.generate_narrative(
            dag=dag,
            target_variable=target_variable,
            attributions=attributions,
        )
        if not narrative.strip():
            return briefing_text

        section = f"## 인과 분석\n{narrative.strip()}\n\n"
        appendix_marker = "## 부록"
        idx = briefing_text.find(appendix_marker)
        if idx == -1:
            if briefing_text.endswith("\n"):
                return f"{briefing_text}\n{section}"
            return f"{briefing_text}\n\n{section}"
        return f"{briefing_text[:idx]}{section}{briefing_text[idx:]}"

    @staticmethod
    def _score_path(path: list[str], attributions: dict[str, float]) -> float:
        if not attributions:
            return 0.0
        weights = [float(attributions.get(node, 0.0)) for node in path]
        if not weights:
            return 0.0
        return max(0.0, min(1.0, sum(weights) / len(weights)))

    @staticmethod
    def _infer_target_variable(dag: nx.DiGraph, attributions: dict[str, float]) -> str | None:
        attr_keys = set(attributions.keys())
        candidate_scores: list[tuple[int, int, str]] = []
        for node in dag.nodes:
            preds = list(dag.predecessors(node))
            overlap = sum(1 for pred in preds if pred in attr_keys)
            if overlap > 0:
                candidate_scores.append((overlap, len(preds), str(node)))
        if candidate_scores:
            candidate_scores.sort(reverse=True)
            return candidate_scores[0][2]

        sinks = sorted([str(node) for node in dag.nodes if dag.out_degree(node) == 0])
        if sinks:
            return sinks[0]
        nodes = sorted([str(node) for node in dag.nodes])
        return nodes[0] if nodes else None
