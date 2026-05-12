# 확장 가이드

본 시스템에는 5가지 확장 축이 있다. 각 축별로 필요한 작업을 설명한다.

1. [새 자산 추가](#1-새-자산-추가)
2. [새 데이터 소스(Collector) 추가](#2-새-데이터-소스collector-추가)
3. [새 평가축 채우기 (정량/구조)](#3-새-평가축-채우기-정량구조)
4. [새 LLM Tool / 에이전트 도구 추가](#4-llm-tool-추가)
5. [새 OntologyMapper 어댑터 추가](#5-새-ontologymapper-어댑터-추가)
6. [새 (서브) 에이전트 추가](#6-새-서브-에이전트-추가)
7. [새 LLM Prompt 추가 / 수정](#7-새-llm-prompt-추가--수정)
8. [새 Observability Backend 추가](#8-새-observability-backend-추가)

---

## 1. 새 자산 추가

신규 STO 기초자산(예: 한우, 미술품)을 추가하는 절차.

### 1단계: 자산 디렉토리 생성

```
projects/livestock/
├── profile.py
├── config/
│   ├── search_groups.yaml
│   └── ontology_schema.py
├── targets/
│   ├── farm.py
│   └── breed.py
├── collectors/        # 자산 특화 collector 필요 시
├── evaluators/        # 자산 특화 evaluator 필요 시
├── tools/             # 자산 특화 Tool 필요 시
└── dags/
    └── news_collection.py
```

### 2단계: AssetClass 등록

`core/shared/domain/asset.py` 에 새 자산 클래스를 추가한다.

```python
class AssetClass(str, Enum):
    # ... 기존 값들 ...
    HANWOO = "hanwoo"   # 한우

ASSET_CLASS_TO_FAMILY[AssetClass.HANWOO] = AssetFamily.LIVESTOCK
```

`AssetFamily` 가 새 카테고리라면 그것도 추가한다.

### 3단계: 평가 대상(SentimentTarget) 정의

```python
# projects/livestock/targets/farm.py

from dataclasses import dataclass
from core.evaluation.sentiment.target_base import SentimentTarget

@dataclass(frozen=True)
class FarmTarget(SentimentTarget):
    target_type: ClassVar[str] = "farm"
    business_number: str   # 사업자등록번호
    farm_name: str

    def unique_key(self) -> str:
        return f"farm:{self.business_number}"

    def label(self) -> str:
        return f"{self.farm_name} ({self.business_number})"
```

### 4단계: 검색어 그룹 작성

```yaml
# projects/livestock/config/search_groups.yaml

active_asset_classes:
  - hanwoo

groups:
  - name: hanwoo_market
    active: true
    priority: 1
    schedule_type: daily
    provider: naver
    asset_class: hanwoo
    queries:
      - 한우 도매가
      - 한우 사육두수
      - 사료비 인상
      - 한우 농가 폐업
```

### 5단계: 자산 특화 온톨로지 스키마

```python
# projects/livestock/config/ontology_schema.py

LIVESTOCK_EVALUATION_FACTORS = [
    "도매가 추이",
    "사육두수",
    "사료비",
    "농가 수익성",
    "수출 환경",
]

LIVESTOCK_EVENT_TYPES = [
    "도매가 변동",
    "정책 발표",
    "전염병 발생",
    "수출 규제",
]
```

### 6단계: AssetProfile 작성

```python
# projects/livestock/profile.py

from pathlib import Path
from core.shared.domain.asset import AssetClass
from core.shared.domain.evaluation import EvaluationDimension
from projects.livestock.targets.farm import FarmTarget
from projects.livestock.targets.breed import BreedTarget

LIVESTOCK_PROFILE = AssetProfile(
    asset_class=AssetClass.HANWOO,
    evaluation_dimensions=[
        EvaluationDimension.QUANTITATIVE,
        EvaluationDimension.STRUCTURAL,
        EvaluationDimension.SENTIMENT,
    ],
    sentiment_target_types=[FarmTarget, BreedTarget],
    collector_source_types=["news"],
    config_path=Path(__file__).parent / "config" / "search_groups.yaml",
    ontology_schema_module="projects.livestock.config.ontology_schema",
    allowed_tools=[              # On-demand 에이전트가 사용할 도구 목록
        "news_search_tool",
        "web_search_tool",
        # "wholesale_price_tool",  # 자산 특화 도구 시 추가
    ],
)
```

`allowed_tools` 는 자산이 On-demand 분석에서 어떤 도구를 사용할지 선언한다. PolicyGate 가 이 목록 외 도구 호출을 차단한다 ([AGENT_DESIGN.md §5](AGENT_DESIGN.md#5-policygate-하이브리드-자율성-통제)).

### 7단계: DAG 작성

```python
# projects/livestock/dags/news_collection.py

from core.pipelines.tasks import build_collection_dag
from projects.livestock.profile import LIVESTOCK_PROFILE

dag = build_collection_dag(
    dag_id="livestock_news_collection",
    profile=LIVESTOCK_PROFILE,
    source_type="news",
    schedule_interval="0 6 * * *",
)
```

### 8단계: 테스트 추가

```
tests/projects/livestock/
├── test_profile.py
└── test_targets.py
```

### 9단계: composition.py 등록

`interfaces/composition.py` 에 새 프로파일을 등록하여 CLI에서 사용 가능하게 한다.

---

## 2. 새 데이터 소스(Collector) 추가

신규 외부 데이터 소스(예: 음원 스트리밍 API, 한우 도매가 API)를 추가하는 절차.

### 1단계: Collector 디렉토리 생성

```
core/collectors/streaming/
├── __init__.py
├── base.py                # StreamingCollector ABC
├── spotify.py             # 구체 구현
├── melon.py
└── normalizer.py
```

### 2단계: Collector 구현

```python
# core/collectors/streaming/spotify.py

from core.collectors.base import Collector, RawRecord, CollectionQuery

class SpotifyStreamingCollector(Collector):
    @property
    def source_type(self) -> str:
        return "streaming"

    def collect(self, query: CollectionQuery) -> list[RawRecord]:
        # 실제 Spotify API 호출 또는 Mock 반환
        ...

    def quota_estimate(self, query: CollectionQuery) -> int:
        return 1
```

### 3단계: composition.py 에 등록

```python
# interfaces/composition.py

from core.collectors.streaming.spotify import SpotifyStreamingCollector

def build_collector_registry():
    return {
        "news": NaverNewsCollector(...),
        "streaming": SpotifyStreamingCollector(...),
    }
```

### 4단계: 자산 프로파일에 추가

```python
# projects/music_copyright/profile.py

MUSIC_COPYRIGHT_PROFILE = AssetProfile(
    ...,
    collector_source_types=["news", "streaming"],   # 추가
)
```

### 5단계: 자산별 DAG 작성

```python
# projects/music_copyright/dags/streaming_collection.py

dag = build_collection_dag(
    dag_id="music_streaming_collection",
    profile=MUSIC_COPYRIGHT_PROFILE,
    source_type="streaming",
    schedule_interval="@hourly",
)
```

뉴스 DAG와 별도 DAG로 분리하여 독립 스케줄·독립 실패 관리.

---

## 3. 새 평가축 채우기 (정량/구조)

본 프로젝트는 감정평가만 본 구현이다. 정량/구조 평가는 stub 상태다. 향후 채울 때:

### 3.1 정량 평가 채우기

```python
# core/evaluation/quantitative/dcf.py

from core.evaluation.base import EvaluationStrategy, EvaluationDimension

class DCFEvaluationStrategy(EvaluationStrategy):
    @property
    def dimension(self) -> EvaluationDimension:
        return EvaluationDimension.QUANTITATIVE

    def evaluate(self, asset_id, profile) -> list[EvaluationClaim]:
        # 결정론적 DCF 계산
        ...
```

자산별로 다른 정량 모델은 `projects/<자산>/evaluators/` 에 둔다.

### 3.2 구조 평가 채우기

토큰·신탁·발행 구조 평가는 결정론적 룰 기반으로 채울 수 있다.

```python
# core/evaluation/structural/issuance_structure.py

class IssuanceStructureEvaluationStrategy(EvaluationStrategy):
    ...
```

### 3.3 평가축을 자산 프로파일에 연결

```python
# projects/commercial_real_estate/profile.py

COMMERCIAL_PROFILE = AssetProfile(
    ...,
    evaluation_dimensions=[
        EvaluationDimension.QUANTITATIVE,
        EvaluationDimension.STRUCTURAL,
        EvaluationDimension.SENTIMENT,
    ],
    # 채워질수록 더 많은 차원이 활성화된다
)
```

---

## 4. LLM Tool 추가

LLM Agent / On-demand ExplorationFlow 가 호출할 수 있는 새 Tool 을 추가하는 절차. 본 프로젝트는 소스 카테고리별 Tool 을 권장한다 ([D-13](DECISIONS.md#d-13)).

### 4.1 공통 Tool 추가 (예: 스트리밍 검색)

```python
# core/tools/streaming_search_tool.py

from core.tools.base import BaseTool

class StreamingSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "streaming_search"

    @property
    def description(self) -> str:
        return "음원 스트리밍 통계를 검색한다. asset_class와 keyword를 받는다."

    def __init__(self, collection_service):
        self._service = collection_service

    def run(self, keyword: str, asset_class: str | None = None, save: bool = True) -> dict:
        ...
```

### 4.2 자산 특화 Tool 추가 (드물게 필요)

자산 특화 분석 로직을 가진 Tool 은 `projects/<자산>/tools/` 에 둔다.

### 4.3 On-demand 에이전트에 노출

추가한 Tool 을 On-demand 분석에서 사용하려면:

1. AssetProfile.allowed_tools 목록에 도구 이름 추가
2. composition.py 에서 ExplorationFlow / QAFlow 의 Tool 레지스트리에 등록

```python
# interfaces/composition.py

def build_tool_registry() -> dict[str, BaseTool]:
    return {
        "news_search_tool": NewsSearchTool(...),
        "streaming_search_tool": StreamingSearchTool(...),
        # 새 도구 추가
    }
```

### 4.4 출력 스키마가 안정적이라면 — OntologyMapper 어댑터도 함께

도구 응답을 그래프로 매핑할 때 (가) 직접 매핑을 쓸 수 있다면, [§5](#5-새-ontologymapper-어댑터-추가) 참조하여 어댑터를 작성한다. 어댑터가 없으면 자동으로 (다) LLM fallback 으로 처리됨.

---

## 5. 새 처리 단계 추가

룰 필터와 LLM 태깅 사이에 새로운 처리 단계(예: 분류기 기반 사전 필터)를 추가하는 절차.

### 1단계: Processor 추가

```
core/processors/classifiers/
├── __init__.py
├── base.py                # Classifier ABC
└── lightweight_bert.py
```

### 2단계: 상태 Enum 확장

`core/shared/domain/states.py` 에 새 단계의 상태를 추가한다.

### 3단계: Repository 확장

`find_pending_<새단계>()`, `update_<새단계>_status()` 메서드를 추가한다.

### 4단계: DAG에 Task 삽입

`core/pipelines/tasks.py` 에 새 Task 함수를 추가하고, DAG에 의존성으로 연결한다.

---

## 5. 새 OntologyMapper 어댑터 추가

도구 응답을 그래프로 직접 매핑하는 어댑터 작성 절차. 응답 스키마가 안정적인 경우 권장 ([D-09](DECISIONS.md#d-09)).

### 5.1 어댑터 작성

```python
# core/processors/ontology_mapper/adapters/wholesale_price_adapter.py

from core.processors.ontology_mapper.base import BaseAdapter
from core.shared.infra.graph_writer import GraphNode, GraphRelation

class WholesalePriceAdapter(BaseAdapter):
    @property
    def source_type(self) -> str:
        return "wholesale_price"

    def map(self, raw) -> list[GraphNode | GraphRelation]:
        content = raw.content
        return [
            GraphNode(
                label="WholesalePrice",
                properties={
                    "price_id": raw.source_id,
                    "value_won": content["price_per_kg"],
                    "date": content["date"],
                },
                unique_key="price_id",
            ),
            # 필요한 엣지도 함께 반환
        ]
```

### 5.2 등록

```python
# interfaces/composition.py

from core.processors.ontology_mapper.base import OntologyMapper
from core.processors.ontology_mapper.adapters.wholesale_price_adapter import WholesalePriceAdapter

def build_ontology_mapper(...) -> OntologyMapper:
    return OntologyMapper(
        registry={
            "vworld": VworldAdapter(),
            "wholesale_price": WholesalePriceAdapter(),  # 추가
            # ...
        },
        llm_fallback=LLMFallbackMapper(...),
    )
```

### 5.3 어휘 사전 갱신

새 노드 라벨 / 엣지 타입이 등장하면 온톨로지 어휘 사전도 갱신:
- 자산 무관 어휘: `core/shared/domain/ontology_schema.py`
- 자산 특화 어휘: `projects/<자산>/config/ontology_schema.py`

다른 자산도 같은 어휘를 쓰면 core/ 로 승격.

### 5.4 어댑터 없이 운영 (LLM fallback)

도구 응답이 비정형이거나 자주 바뀌면 어댑터를 작성하지 않아도 된다. OntologyMapper 가 자동으로 LLMFallbackMapper 로 라우팅한다.

---

## 6. 새 (서브) 에이전트 추가

ExplorationFlow / QAFlow 안에 서브 에이전트를 추가하거나 새 Flow 를 만드는 절차.

### 6.1 ExplorationFlow / QAFlow 안에 서브 에이전트 추가

```python
# core/agents/exploration/hypothesizer.py

from core.agents.base import Agent, AgentContext, EvidenceStep

class Hypothesizer(Agent):
    @property
    def name(self) -> str:
        return "exploration.hypothesizer"

    def __init__(self, llm_client):
        self._llm = llm_client

    def run(self, ctx: AgentContext) -> AgentContext:
        hypotheses = self._call_llm(ctx.artifacts["initial_collection"])
        ctx.artifacts["hypotheses"] = hypotheses
        ctx.evidence.append(EvidenceStep(
            step_id=ctx.evidence.next_step_id(),
            actor=self.name,
            tool_name="llm",
            rationale="generate hypotheses from initial collection",
            input_summary={"initial": "..."},
            result_summary={"count": len(hypotheses)},
        ))
        return ctx
```

그 후 `exploration/flow.py` 의 LangGraph 에 노드 + 엣지 추가:

```python
g.add_node("hypothesize", hypothesizer.run)
g.add_edge(START, "hypothesize")
g.add_edge("hypothesize", "plan")
```

### 6.2 새 Flow 추가

전혀 새로운 자율 흐름이 필요하면 `core/agents/<flow_name>/` 디렉토리 생성:

```
core/agents/comparison/
├── flow.py          # ComparisonFlow (Agent ABC 구현)
├── selector.py      # 비교 대상 선택
├── differ.py        # 차이 분석
└── reporter.py      # 비교 보고서 작성
```

Orchestrator 가 새 Flow 를 호출하도록 등록.

### 6.3 PolicyGate 정책 조정

새 Flow 가 다른 자율성 한도를 필요로 하면 별도 AgentPolicy 인스턴스 생성:

```python
comparison_policy = AgentPolicy(
    max_tool_calls=20,             # 비교는 더 많은 도구 호출 허용
    max_cost_usd=2.0,
    allowed_tools=[...],
)
```

---

## 7. 새 LLM Prompt 추가 / 수정

새 prompt 가 필요한 경우 (예: 새 서브 에이전트, 새 LLM 사용 지점):

### 7.1 YAML 파일 작성

```yaml
# core/llm/prompts/<group>/<name>.yaml

version: 1
description: |
  무엇을 하는 prompt 인지 / 어떤 변수를 받는지 한 단락.
  Variables:
    var1 — 설명
    var2 — 설명

system: |
  $var1 자리에 값이 채워집니다.
  JSON 응답 예시: {"key": "value"}  # 중괄호 그대로 사용 가능 (string.Template)

user: |
  $var2 의 내용

schema:
  type: object
  required: [key]
  properties:
    key: { type: string }
  additionalProperties: false
```

**규칙**:
- key 는 디렉토리 경로의 도트 표기 — `prompts/exploration/planner.yaml` → `"exploration.planner"`
- 변수는 `$var` 또는 `${var}` — JSON 예시의 `{}` 와 충돌 없음 (`string.Template`)
- `schema` 는 응답 JSON Schema — `response_schema` 로 LLMRequest 에 전달됨
- enum 값이 코드 enum 과 일치해야 하면 `tests/core/llm/test_prompt_catalog.py` 에 drift 검증 추가

### 7.2 호출 코드 수정

```python
class MyNewAgent(Agent):
    def __init__(self, llm_client: LLMClient, prompt_catalog: PromptCatalog):
        self._llm = llm_client
        self._catalog = prompt_catalog

    def run(self, ctx: AgentContext) -> AgentContext:
        rendered = self._catalog.render(
            "mygroup.mynew",
            var1=...,
            var2=...,
        )
        response = self._llm.call(rendered.to_llm_request())
        # ...
        ctx.evidence.append(EvidenceStep(
            ...,
            input_summary={..., "prompt_version": rendered.version_hash},
        ))
        return ctx
```

### 7.3 composition 에서 주입

```python
# interfaces/composition.py — build_address_analysis_orchestrator 안

my_agent = MyNewAgent(llm, prompt_catalog=catalog)
```

### 7.4 prompt 수정 시

- `version` 필드 증가 (1 → 2) — 시각적 추적
- 자동 계산되는 `version_hash` 가 변경됨 → EvidenceStep / Langfuse 메타에 자동 반영
- prompt 변경 PR 에 golden eval 결과 첨부 권장 (향후 자동화 예정)

---

## 8. 새 Observability Backend 추가

Langfuse 외 다른 백엔드 (OpenTelemetry, Phoenix(Arize), 자체 PostgreSQL 등) 를 추가하려면 `TraceBackend` ABC 만 구현하면 된다.

### 8.1 ABC 구현

```python
# core/shared/infra/observability/phoenix_backend.py

from core.shared.infra.observability.base import (
    GenerationContext, TraceBackend, TraceContext,
)

class PhoenixBackend(TraceBackend):
    def __init__(self, endpoint: str | None = None):
        # OpenTelemetry SDK 초기화
        ...

    def start_trace(self, name, trace_id, metadata=None) -> TraceContext:
        # OTEL span 시작
        ctx = TraceContext(trace_id=trace_id, name=name, metadata=metadata or {})
        ctx.backend_handle = ...  # 백엔드별 핸들
        return ctx

    def end_trace(self, ctx, output=None, error=None):
        # span 종료
        ...

    def start_generation(self, trace, name, role, model, input, metadata=None):
        # child span 시작
        ...

    def end_generation(self, gen, output=None, usage=None, error=None):
        # child span 종료 + usage 첨부
        ...

    def flush(self):
        ...
```

### 8.2 composition 에 등록

```python
# interfaces/composition.py — _build_trace_backend()

def _build_trace_backend(settings):
    backend = settings.backend.lower()
    if backend == "langfuse":
        ...
    if backend == "phoenix":  # 신규
        from core.shared.infra.observability.phoenix_backend import PhoenixBackend
        return PhoenixBackend(endpoint=settings.phoenix_endpoint)
    if backend == "stdout":
        ...
    return NoOpBackend()
```

### 8.3 설정 추가

```python
# core/shared/config/settings.py — ObservabilitySettings 에 필드 추가
phoenix_endpoint: str = "http://localhost:6006"
```

```yaml
# config/runtime.yaml
observability:
  backend: phoenix
  phoenix:
    endpoint: http://localhost:6006
```

### 8.4 외부 호출 안전성

새 백엔드는 다음을 반드시 지켜야 한다:
- 외부 호출 실패는 try/except 으로 swallow + log warning (`observability 가 본 흐름을 망가뜨리지 않음`)
- 키/엔드포인트 부재 시 `_disabled=True` 로 no-op fallback
- `flush()` 가 비차단 (또는 timeout 짧게)

테스트: `tests/core/shared/infra/test_observability_backends.py` 패턴을 참고 — `RecordingBackend` 로 호출 시퀀스만 검증.

---

## 9. 자주 묻는 질문

### Q. 자산 특화 코드를 core에 두면 안 되는가?

원칙적으로는 안 된다. 다만 **2개 이상의 자산이 동일하게 사용**한다면 core로 승격할 수 있다.
한 자산만 쓰는 코드는 무조건 `projects/<자산>/` 에 둔다.

### Q. 자산 간 코드 공유가 필요한 상황이 발생하면?

자산 간 의존성을 만들지 말고, 공유할 코드를 `core/`로 추출한다.
자산이 다른 자산을 import하는 순간 격리가 깨진다.

### Q. DAG가 자산당 여러 개일 때 검색어 그룹은 어떻게 분리?

`projects/<자산>/config/search_groups.yaml` 안에 그룹별 `schedule_type` 필드를 두고, 각 DAG가 자신에게 해당하는 그룹만 필터링한다. 또는 DAG별로 별도 yaml 파일을 둘 수 있다 (`news_search_groups.yaml`, `transaction_search_groups.yaml` 등).

### Q. 음악 저작권 collector가 부동산과 완전히 달라서 추상화가 어색하다면?

`Collector` ABC는 `collect(query) -> list[RawRecord]` 만 강제한다. `RawRecord.content`는 dict이므로 source별로 자유롭게 채울 수 있다. 이 추상화는 흐름(수집→정규화→저장)만 공유하고, 데이터 형태는 강제하지 않는다.
