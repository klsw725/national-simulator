"""
시뮬레이션 설정 지능형 생성기
LLM을 사용하여 시뮬레이션 요구사항, 문서 내용, 그래프 정보를 바탕으로 세부 시뮬레이션 파라미터를 자동 생성합니다.
전 과정 자동화를 구현하여 수동 파라미터 설정이 필요 없습니다.

단계별 생성 전략을 채택하여 한 번에 너무 긴 내용이 생성되어 실패하는 것을 방지합니다:
1. 시간 설정 생성
2. 이벤트 설정 생성
3. 에이전트 설정 일괄 생성
4. 플랫폼 설정 생성
"""

import json
import math
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.simulation_config')

# 생활 패턴 설정 (베이징 시간 기준)
CHINA_TIMEZONE_CONFIG = {
    # 심야 시간대 (활동 거의 없음)
    "dead_hours": [0, 1, 2, 3, 4, 5],
    # 오전 시간대 (점진적으로 깨어남)
    "morning_hours": [6, 7, 8],
    # 업무 시간대
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    # 저녁 피크 (가장 활발)
    "peak_hours": [19, 20, 21, 22],
    # 야간 시간대 (활동 감소)
    "night_hours": [23],
    # 활동 계수
    "activity_multipliers": {
        "dead": 0.05,      # 새벽 활동 거의 없음
        "morning": 0.4,    # 오전 점진적 활성화
        "work": 0.7,       # 업무 시간대 중간 수준
        "peak": 1.5,       # 저녁 피크
        "night": 0.5       # 심야 감소
    }
}


@dataclass
class AgentActivityConfig:
    """개별 에이전트의 활동 설정"""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str
    
    # 활동성 설정 (0.0-1.0)
    activity_level: float = 0.5  # 전체 활동성
    
    # 발언 빈도 (시간당 예상 발언 횟수)
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    
    # 활동 시간대 (24시간제, 0-23)
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    
    # 응답 속도 (이슈 발생 시 반응 지연 시간, 단위: 시뮬레이션 분)
    response_delay_min: int = 5
    response_delay_max: int = 60
    
    # 감정 성향 (-1.0에서 1.0, 부정에서 긍정)
    sentiment_bias: float = 0.0
    
    # 입장 (특정 화제에 대한 태도)
    stance: str = "neutral"  # supportive, opposing, neutral, observer
    
    # 영향력 가중치 (해당 발언이 다른 에이전트에게 노출될 확률 결정)
    influence_weight: float = 1.0


@dataclass  
class TimeSimulationConfig:
    """시간 시뮬레이션 설정 (생활 패턴 기반)"""
    # 총 시뮬레이션 시간 (시뮬레이션 시간 단위)
    total_simulation_hours: int = 72  # 기본 72시간 (3일)
    
    # 라운드당 대표 시간 (시뮬레이션 분) - 기본 60분 (1시간), 시간 흐름 가속
    minutes_per_round: int = 60
    
    # 시간당 활성화되는 에이전트 수 범위
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20
    
    # 피크 시간대 (저녁 19-22시, 가장 활발한 시간)
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5
    
    # 비활성 시간대 (새벽 0-5시, 활동 거의 없음)
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # 새벽 활동성 매우 낮음
    
    # 오전 시간대
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4
    
    # 업무 시간대
    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """이벤트 설정"""
    # 초기 이벤트 (시뮬레이션 시작 시 트리거되는 게시물)
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    
    # 예약 이벤트 (특정 시간에 트리거되는 이벤트)
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # 핫 토픽 키워드
    hot_topics: List[str] = field(default_factory=list)
    
    # 여론 유도 방향
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """플랫폼별 설정"""
    platform: str  # twitter or reddit
    
    # 추천 알고리즘 가중치
    recency_weight: float = 0.4  # 최신성
    popularity_weight: float = 0.3  # 인기도
    relevance_weight: float = 0.3  # 관련성
    
    # 바이럴 임계값 (확산이 트리거되는 상호작용 수)
    viral_threshold: int = 10
    
    # 에코 체임버 강도 (유사 관점 집결 정도)
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """전체 시뮬레이션 파라미터 설정"""
    # 기본 정보
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str
    
    # 시간 설정
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    
    # 에이전트 설정 목록
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    
    # 이벤트 설정
    event_config: EventConfig = field(default_factory=EventConfig)
    
    # 플랫폼 설정
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None
    
    # LLM 설정
    llm_model: str = ""
    llm_base_url: str = ""
    
    # 생성 메타데이터
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # LLM의 추론 설명
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    시뮬레이션 설정 지능형 생성기
    
    LLM을 사용하여 시뮬레이션 요구사항, 문서 내용, 그래프 엔티티 정보를 분석하고,
    최적의 시뮬레이션 파라미터 설정을 자동으로 생성합니다.
    
    단계별 생성 전략 채택:
    1. 시간 설정 및 이벤트 설정 생성 (경량)
    2. 에이전트 설정 일괄 생성 (배치당 10-20개)
    3. 플랫폼 설정 생성
    """
    
    # 컨텍스트 최대 문자 수
    MAX_CONTEXT_LENGTH = 50000
    # 배치당 생성할 에이전트 수
    AGENTS_PER_BATCH = 15
    
    # 각 단계별 컨텍스트 절삭 길이 (문자 수)
    TIME_CONFIG_CONTEXT_LENGTH = 10000   # 시간 설정
    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # 이벤트 설정
    ENTITY_SUMMARY_LENGTH = 300          # 엔티티 요약
    AGENT_SUMMARY_LENGTH = 300           # 에이전트 설정 내 엔티티 요약
    ENTITIES_PER_TYPE_DISPLAY = 20       # 유형별 표시 엔티티 수
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY가 설정되지 않았습니다.")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        전체 시뮬레이션 설정을 지능적으로 생성 (단계별 생성)
        
        Args:
            simulation_id: 시뮬레이션 ID
            project_id: 프로젝트 ID
            graph_id: 그래프 ID
            simulation_requirement: 시뮬레이션 요구사항 설명
            document_text: 원본 문서 내용
            entities: 필터링된 엔티티 목록
            enable_twitter: 트위터 활성화 여부
            enable_reddit: 레딧 활성화 여부
            progress_callback: 진행률 콜백 함수(current_step, total_steps, message)
            
        Returns:
            SimulationParameters: 전체 시뮬레이션 파라미터
        """
        logger.info(f"시뮬레이션 설정 지능형 생성 시작: simulation_id={simulation_id}, 엔티티 수={len(entities)}")
        
        # 총 단계 수 계산
        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # 시간 설정 + 이벤트 설정 + N개 배치 에이전트 + 플랫폼 설정
        current_step = 0
        
        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")
        
        # 1. 기본 컨텍스트 정보 구축
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )
        
        reasoning_parts = []
        
        # ========== 단계 1: 시간 설정 생성 ==========
        report_progress(1, "시간 설정 생성 중...")
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"시간 설정: {time_config_result.get('reasoning', '성공')}")
        
        # ========== 단계 2: 이벤트 설정 생성 ==========
        report_progress(2, "이벤트 설정 및 핫 토픽 생성 중...")
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"이벤트 설정: {event_config_result.get('reasoning', '성공')}")
        
        # ========== 단계 3-N: 에이전트 설정 일괄 생성 ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]
            
            report_progress(
                3 + batch_idx,
                f"에이전트 설정 생성 중 ({start_idx + 1}-{end_idx}/{len(entities)})..."
            )
            
            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)
        
        reasoning_parts.append(f"에이전트 설정: {len(all_agent_configs)}개 성공적으로 생성됨")
        
        # ========== 초기 게시물에 게시자 에이전트 할당 ==========
        logger.info("초기 게시물에 적절한 게시자 에이전트 할당 중...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(f"초기 게시물 할당: {assigned_count}개 게시물에 게시자 할당됨")
        
        # ========== 마지막 단계: 플랫폼 설정 생성 ==========
        report_progress(total_steps, "플랫폼 설정 생성 중...")
        twitter_config = None
        reddit_config = None
        
        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )
        
        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )
        
        # 최종 파라미터 구축
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts)
        )
        
        logger.info(f"시뮬레이션 설정 생성 완료: {len(params.agent_configs)}개의 에이전트 설정")
        
        return params
    
    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """LLM 컨텍스트 구축, 최대 길이로 절삭"""
        
        # 엔티티 요약
        entity_summary = self._summarize_entities(entities)
        
        # 컨텍스트 구축
        context_parts = [
            f"## 시뮬레이션 요구사항\n{simulation_requirement}",
            f"\n## 엔티티 정보 ({len(entities)}개)\n{entity_summary}",
        ]
        
        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # 500자 여유분 확보
        
        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(문서가 절삭되었습니다)"
            context_parts.append(f"\n## 원본 문서 내용\n{doc_text}")
        
        return "\n".join(context_parts)
    
    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """엔티티 요약 생성"""
        lines = []
        
        # 유형별 그룹화
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)
        
        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)}개)")
            # 설정된 표시 수 및 요약 길이 사용
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... 외 {len(type_entities) - display_count}개")
        
        return "\n".join(lines)
    
    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """재시도 로직이 포함된 LLM 호출, JSON 복구 로직 포함"""
        import re
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # 재시도할 때마다 온도 낮춤
                    # max_tokens를 설정하지 않아 LLM이 자유롭게 출력하도록 함
                )
                
                content = response.choices[0].message.content
                if content is None:
                    raise Exception("LLM이 빈 응답을 반환했습니다.")
                
                finish_reason = response.choices[0].finish_reason
                
                # 절삭 여부 확인
                if finish_reason == 'length':
                    logger.warning(f"LLM 출력이 절삭되었습니다 (시도 {attempt+1})")
                    content = self._fix_truncated_json(content)
                
                # JSON 파싱 시도
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 파싱 실패 (시도 {attempt+1}): {str(e)[:80]}")
                    
                    # JSON 복구 시도
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed
                    
                    last_error = e
                    
            except Exception as e:
                logger.warning(f"LLM 호출 실패 (시도 {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))
        
        raise last_error or Exception("LLM 호출 실패")
    
    def _fix_truncated_json(self, content: str) -> str:
        """절삭된 JSON 복구"""
        content = content.strip()
        
        # 닫히지 않은 괄호 계산
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # 닫히지 않은 문자열 확인
        if content and content[-1] not in '",}]':
            content += '"'
        
        # 괄호 닫기
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """설정 JSON 복구 시도"""
        import re
        
        # 절삭된 경우 복구
        content = self._fix_truncated_json(content)
        
        # JSON 부분 추출
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 문자열 내의 줄바꿈 제거
            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s
            
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)
            
            try:
                return json.loads(json_str)
            except:
                # 모든 제어 문자 제거 시도
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass
        
        return None
    
    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """시간 설정 생성"""
        # 설정된 컨텍스트 절삭 길이 사용
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]
        
        # 최대 허용 값 계산 (에이전트 수의 90%)
        max_agents_allowed = max(1, int(num_entities * 0.9))
        
        prompt = f"""다음 시뮬레이션 요구사항을 바탕으로 시간 시뮬레이션 설정을 생성해 주세요.

{context_truncated}

## 작업
시간 설정 JSON을 생성해 주세요.

### 기본 원칙 (참고용이며, 구체적인 사건과 참여 집단에 따라 유연하게 조정해야 함):
- 사용자 집단은 중국인이며, 베이징 시간 생활 패턴을 따라야 합니다.
- 새벽 0-5시는 활동이 거의 없습니다 (활동 계수 0.05).
- 오전 6-8시는 점진적으로 활성화됩니다 (활동 계수 0.4).
- 업무 시간 9-18시는 중간 수준으로 활성화됩니다 (활동 계수 0.7).
- 저녁 19-22시는 피크 시간대입니다 (활동 계수 1.5).
- 23시 이후에는 활동성이 감소합니다 (활동 계수 0.5).
- 일반적인 규칙: 새벽 저활동, 오전 점증, 업무 시간 중간, 저녁 피크.
- **중요**: 아래 예시 값은 참고용일 뿐이며, 사건의 성격과 참여 집단의 특징에 따라 구체적인 시간대를 조정해야 합니다.
  - 예: 학생 집단의 피크는 21-23시일 수 있음, 미디어는 하루 종일 활발함, 공식 기관은 업무 시간에만 활동함.
  - 예: 돌발 이슈의 경우 심야에도 토론이 이어질 수 있으므로 off_peak_hours를 적절히 단축할 수 있음.

### JSON 형식으로 반환 (마크다운 제외)

예시:
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "해당 사건에 대한 시간 설정 설명"
}}

필드 설명:
- total_simulation_hours (int): 총 시뮬레이션 시간, 24-168시간. 돌발 사건은 짧게, 지속적인 화제는 길게 설정.
- minutes_per_round (int): 라운드당 시간, 30-120분, 60분 권장.
- agents_per_hour_min (int): 시간당 최소 활성화 에이전트 수 (범위: 1-{max_agents_allowed})
- agents_per_hour_max (int): 시간당 최대 활성화 에이전트 수 (범위: 1-{max_agents_allowed})
- peak_hours (int 배열): 피크 시간대, 사건 참여 집단에 따라 조정.
- off_peak_hours (int 배열): 비활성 시간대, 보통 심야 및 새벽.
- morning_hours (int 배열): 오전 시간대.
- work_hours (int 배열): 업무 시간대.
- reasoning (string): 왜 이렇게 설정했는지에 대한 간략한 설명."""

        system_prompt = "당신은 소셜 미디어 시뮬레이션 전문가입니다. 순수 JSON 형식으로 반환하며, 시간 설정은 중국인 생활 패턴에 부합해야 합니다."
        
        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"시간 설정 LLM 생성 실패: {e}, 기본 설정 사용")
            return self._get_default_time_config(num_entities)
    
    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """기본 시간 설정 가져오기 (생활 패턴 기반)"""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # 라운드당 1시간, 시간 흐름 가속
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "기본 생활 패턴 설정 사용 (라운드당 1시간)"
        }
    
    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """시간 설정 결과 파싱 및 agents_per_hour 값이 총 에이전트 수를 초과하지 않는지 검증"""
        # 원본 값 가져오기
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))
        
        # 검증 및 수정: 총 에이전트 수를 초과하지 않도록 보장
        if agents_per_hour_min > num_entities:
            logger.warning(f"agents_per_hour_min ({agents_per_hour_min})이 총 에이전트 수 ({num_entities})를 초과하여 수정되었습니다.")
            agents_per_hour_min = max(1, num_entities // 10)
        
        if agents_per_hour_max > num_entities:
            logger.warning(f"agents_per_hour_max ({agents_per_hour_max})이 총 에이전트 수 ({num_entities})를 초과하여 수정되었습니다.")
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)
        
        # min < max 보장
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= max이므로 {agents_per_hour_min}으로 수정되었습니다.")
        
        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # 기본 라운드당 1시간
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # 새벽 활동 거의 없음
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )
    
    def _generate_event_config(
        self, 
        context: str, 
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """이벤트 설정 생성"""
        
        # LLM 참고용 사용 가능한 엔티티 유형 목록 가져오기
        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))
        
        # 유형별 대표 엔티티 이름 나열
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)
        
        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}" 
            for t, examples in type_examples.items()
        ])
        
        # 설정된 컨텍스트 절삭 길이 사용
        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]
        
        prompt = f"""다음 시뮬레이션 요구사항을 바탕으로 이벤트 설정을 생성해 주세요.

시뮬레이션 요구사항: {simulation_requirement}

{context_truncated}

## 사용 가능한 엔티티 유형 및 예시
{type_info}

## 작업
이벤트 설정 JSON을 생성해 주세요:
- 핫 토픽 키워드 추출
- 여론 발전 방향 묘사
- 초기 게시물 내용 설계, **각 게시물은 반드시 poster_type(게시자 유형)을 지정해야 함**

**중요**: poster_type은 반드시 위의 "사용 가능한 엔티티 유형" 중에서 선택해야 초기 게시물이 적절한 에이전트에게 할당될 수 있습니다.
예: 공식 성명은 Official/University 유형이, 뉴스는 MediaOutlet이, 학생 관점은 Student가 게시해야 합니다.

JSON 형식으로 반환 (마크다운 제외):
{{
    "hot_topics": ["키워드1", "키워드2", ...],
    "narrative_direction": "<여론 발전 방향 묘사>",
    "initial_posts": [
        {{"content": "게시물 내용", "poster_type": "엔티티 유형 (사용 가능한 유형 중에서 선택)"}},
        ...
    ],
    "reasoning": "<간략한 설명>"
}}"""

        system_prompt = "당신은 여론 분석 전문가입니다. 순수 JSON 형식으로 반환하세요. poster_type은 반드시 사용 가능한 엔티티 유형과 정확히 일치해야 합니다."
        
        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"이벤트 설정 LLM 생성 실패: {e}, 기본 설정 사용")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "기본 설정 사용"
            }
    
    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """이벤트 설정 결과 파싱"""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", "")
        )
    
    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        초기 게시물에 적절한 게시자 에이전트 할당
        
        각 게시물의 poster_type에 따라 가장 적합한 agent_id를 매칭합니다.
        """
        if not event_config.initial_posts:
            return event_config
        
        # 엔티티 유형별 에이전트 인덱스 구축
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)
        
        # 유형 매핑 테이블 (LLM이 출력할 수 있는 다양한 형식 처리)
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }
        
        # 유형별 사용된 에이전트 인덱스 기록 (동일 에이전트 중복 사용 방지)
        used_indices: Dict[str, int] = {}
        
        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")
            
            # 매칭되는 에이전트 찾기 시도
            matched_agent_id = None
            
            # 1. 직접 매칭
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. 별칭 매칭 사용
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break
            
            # 3. 여전히 찾지 못한 경우 영향력이 가장 높은 에이전트 사용
            if matched_agent_id is None:
                logger.warning(f"유형 '{poster_type}'에 매칭되는 에이전트를 찾지 못해 영향력이 가장 높은 에이전트를 사용합니다.")
                if agent_configs:
                    # 영향력 순으로 정렬하여 가장 높은 에이전트 선택
                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0
            
            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id
            })
            
            logger.info(f"초기 게시물 할당: poster_type='{poster_type}' -> agent_id={matched_agent_id}")
        
        event_config.initial_posts = updated_posts
        return event_config
    
    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """에이전트 설정 일괄 생성"""
        
        # 엔티티 정보 구축 (설정된 요약 길이 사용)
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })
        
        prompt = f"""다음 정보를 바탕으로 각 엔티티의 소셜 미디어 활동 설정을 생성해 주세요.

시뮬레이션 요구사항: {simulation_requirement}

## 엔티티 목록
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## 작업
각 엔티티의 활동 설정을 생성할 때 다음 사항에 주의하세요:
- **시간은 중국인 생활 패턴에 부합해야 함**: 새벽 0-5시는 거의 활동하지 않으며, 저녁 19-22시가 가장 활발함.
- **공식 기관** (University/GovernmentAgency): 활동성 낮음(0.1-0.3), 업무 시간(9-17) 활동, 응답 느림(60-240분), 영향력 높음(2.5-3.0).
- **미디어** (MediaOutlet): 활동성 중간(0.4-0.6), 하루 종일 활동(8-23), 응답 빠름(5-30분), 영향력 높음(2.0-2.5).
- **개인** (Student/Person/Alumni): 활동성 높음(0.6-0.9), 주로 저녁 활동(18-23), 응답 빠름(1-15분), 영향력 낮음(0.8-1.2).
- **공인/전문가**: 활동성 중간(0.4-0.6), 영향력 중상(1.5-2.0).

JSON 형식으로 반환 (마크다운 제외):
{{
    "agent_configs": [
        {{
            "agent_id": <입력과 반드시 일치해야 함>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <게시 빈도>,
            "comments_per_hour": <댓글 빈도>,
            "active_hours": [<활동 시간 목록, 생활 패턴 고려>],
            "response_delay_min": <최소 응답 지연 분>,
            "response_delay_max": <최대 응답 지연 분>,
            "sentiment_bias": <-1.0에서 1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <영향력 가중치>
        }},
        ...
    ]
}}"""

        system_prompt = "당신은 소셜 미디어 행동 분석 전문가입니다. 순수 JSON으로 반환하며, 설정은 중국인 생활 패턴에 부합해야 합니다."
        
        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"에이전트 설정 배치 LLM 생성 실패: {e}, 규칙 기반 생성 사용")
            llm_configs = {}
        
        # AgentActivityConfig 객체 구축
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})
            
            # LLM이 생성하지 않은 경우 규칙 기반 생성 사용
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)
            
            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0)
            )
            configs.append(config)
        
        return configs
    
    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """규칙 기반 개별 에이전트 설정 생성 (생활 패턴 기반)"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()
        
        if entity_type in ["university", "governmentagency", "ngo"]:
            # 공식 기관: 업무 시간 활동, 낮은 빈도, 높은 영향력
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0
            }
        elif entity_type in ["mediaoutlet"]:
            # 미디어: 하루 종일 활동, 중간 빈도, 높은 영향력
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5
            }
        elif entity_type in ["professor", "expert", "official"]:
            # 전문가/교수: 업무 + 저녁 활동, 중간 빈도
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0
            }
        elif entity_type in ["student"]:
            # 학생: 저녁 위주, 높은 빈도
            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # 오전 + 저녁
                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8
            }
        elif entity_type in ["alumni"]:
            # 동문: 저녁 위주
            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23],  # 점심시간 + 저녁
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
        else:
            # 일반인: 저녁 피크
            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # 낮 + 저녁
                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
