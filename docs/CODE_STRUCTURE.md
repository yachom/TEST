# 코드 구조 명세

## 1. 전체 디렉토리 구조

```
fnpricing-real/
│
├── core/                              # 자산 무관 공통 도구
│   ├── shared/                        # 도메인 / 저장소 / 인프라 추상
│   │   ├── domain/
│   │   │   ├── asset.py               # AssetFamily, AssetClass
│   │   │   ├── address.py             # AddressIdentifier (PNU, 법정동 등)
│   │   │   ├── evaluation.py          # EvaluationDimension, EvaluationTarget, EvaluationClaim
│   │   │   ├── ontology_schema.py     # SignalType, Applicability 등
│   │   │   └── states.py              # 6종 처리 상태 Enum
│   │   ├── stores/
│   │   │   ├── raw_store.py           # ABC
│   │   │   ├── ontology_store.py      # ABC
│   │   │   ├── signal_store.py        # ABC (배치 ↔ On-demand 연결 지점)
│   │   │   ├── graph_store.py         # ABC + InMemoryGraphStore (scope_id 격리)
│   │   │   ├── document_store.py      # ABC (On-demand용)
│   │   │   └── report_store.py        # ABC (On-demand용)
│   │   └── infra/
│   │       ├── llm_client.py          # ABC + StubLLMClient (StubLLMClient만 정의)
│   │       ├── langchain_llm_client.py # LangChainLLMClient (OpenAI / Anthropic)
│   │       ├── tracing_llm_client.py  # TracingLLMClient (LLMClient 데코레이터)
│   │       ├── observability/         # [신규] LLM/Flow trace 백엔드
│   │       │   ├── base.py            # TraceBackend ABC + trace_scope() + contextvars
│   │       │   ├── noop_backend.py
│   │       │   ├── stdout_backend.py
│   │       │   └── langfuse_backend.py
│   │       ├── api_key_rotator.py
│   │       ├── embedding_adapter.py   # ABC + StubEmbeddingAdapter
│   │       ├── db_schema.py
│   │       └── graph_writer.py        # ABC + NoOpGraphWriter (배치용)
│   │
│   ├── llm/                           # [신규] LLM 자산 분리
│   │   ├── catalog.py                 # PromptCatalog ($var 치환, version_hash)
│   │   ├── pricing.py + pricing.yaml  # 모델 단가 (USD/1M tokens)
│   │   └── prompts/                   # 8 개 prompt YAML
│   │       ├── exploration/{planner,critic}.yaml
│   │       ├── qa/{analyzer,synthesizer,verifier}.yaml
│   │       ├── tagging/sentiment.yaml
│   │       ├── mapping/llm_fallback.yaml
│   │       └── reporting/report.yaml
│   │
│   ├── collectors/                    # 외부 데이터 수집 (소스별, 자산 무관)
│   │   ├── base.py                    # Collector ABC, RawRecord, CollectionPlan
│   │   ├── news/
│   │   │   ├── base.py                # NewsCollector ABC
│   │   │   ├── naver.py               # NaverNewsCollector
│   │   │   ├── mock.py                # MockNewsCollector
│   │   │   └── normalizer.py          # NewsNormalizer
│   │   ├── transaction/               # 부동산 실거래가 [추후]
│   │   ├── building/                  # 건축물대장 [추후]
│   │   ├── streaming/                 # 음원 스트리밍 [추후]
│   │   └── chart/                     # 음원 차트 [추후]
│   │
│   ├── processors/                    # 데이터 처리 도구 (재사용)
│   │   ├── filters/
│   │   │   └── rule_filter.py         # RuleFilterService
│   │   ├── embedders/
│   │   │   └── text_embedder.py       # TextEmbedderService
│   │   ├── deduplicators/
│   │   │   └── semantic_dedup.py      # SemanticDeduplicationService
│   │   ├── taggers/
│   │   │   ├── base.py                # OntologyTagger ABC (스키마 주입식)
│   │   │   ├── models.py              # OntologyTag (extra: dict 포함)
│   │   │   └── sentiment_tagger.py    # SentimentOntologyTagger
│   │   ├── ontology_mapper/           # [신규] 어댑터 + LLM fallback
│   │   │   ├── base.py                # OntologyMapper, BaseAdapter
│   │   │   ├── adapters/              # 도구별 어댑터 (구조화 입력 → 그래프)
│   │   │   └── llm_fallback.py        # 비정형 입력 → LLM → 그래프
│   │   └── graph_writers/
│   │       ├── signal_writer.py       # SignalWriterService (배치)
│   │       ├── pattern_builder.py     # [신규] OntologyTag → 노드/엣지 패턴
│   │       └── signal_joiner.py       # [신규 placeholder, POC 보류]
│   │
│   ├── agents/                        # [신규] 자율 에이전트 Flow
│   │   ├── base.py                    # Agent ABC, AgentContext, EvidenceTrace
│   │   ├── policy.py                  # AgentPolicy, PolicyGate
│   │   ├── orchestrator.py            # 결정적 흐름 제어 (예정)
│   │   ├── exploration/               # ExplorationFlow + 서브 에이전트
│   │   │   ├── flow.py                # LangGraph StateGraph
│   │   │   ├── planner.py             # 추가 수집 계획
│   │   │   ├── retriever.py           # 도구 호출
│   │   │   └── critic.py              # 충분성 판정
│   │   └── qa/                        # QAFlow + 서브 에이전트
│   │       ├── flow.py
│   │       ├── analyzer.py            # 질문 분류
│   │       ├── retriever.py           # 그래프/보고서/신호 검색
│   │       ├── synthesizer.py         # 답변 합성
│   │       └── verifier.py            # 근거 검증
│   │
│   ├── reporting/                     # [신규] 보고서 + QA 서비스
│   │   ├── report_builder.py          # Subgraph → 보고서 (단발 LLM)
│   │   ├── qa_service.py              # QAFlow 감싸는 서비스
│   │   └── graph_query_policy.py      # traversal 정책 모듈
│   │
│   ├── evaluation/                    # 평가축 추상 + 공통 부분
│   │   ├── base.py                    # EvaluationStrategy ABC
│   │   ├── quantitative/
│   │   │   └── stub.py                # 목업 (자산 무관 인터페이스만)
│   │   ├── structural/
│   │   │   └── stub.py                # 목업
│   │   └── sentiment/
│   │       ├── strategy.py            # SentimentEvaluationStrategy
│   │       ├── target_base.py         # SentimentTarget ABC
│   │       ├── claim_builder.py
│   │       └── score_builder.py       # placeholder (보고서 미정)
│   │
│   ├── pipelines/                     # DAG에서 재사용할 Task 함수
│   │   └── tasks.py                   # collect_task, filter_task, embed_task ...
│   │
│   ├── tools/                         # LLM Agent Tool 베이스
│   │   └── base.py
│   │
│   └── application/                   # 자산 무관 유스케이스 서비스
│       ├── search_plan_service.py
│       ├── api_quota_service.py
│       ├── collection_service.py      # 구 NewsSearchApplicationService
│       └── run_summary_service.py
│
├── projects/                          # 자산별 평가 프로젝트
│   ├── commercial_real_estate/        # 상가형 부동산 (MVP)
│   │   ├── profile.py                 # AssetProfile 정의
│   │   ├── config/
│   │   │   ├── search_groups.yaml     # 검색어 그룹
│   │   │   └── ontology_schema.py     # 부동산 평가 요인 사전
│   │   ├── targets/                   # 평가 대상
│   │   │   ├── building.py            # 건물 (PNU)
│   │   │   └── tenant.py              # 입점업체 (사업자번호)
│   │   ├── collectors/                # 자산 특화 collector (필요 시)
│   │   ├── evaluators/                # 자산 특화 evaluator (필요 시)
│   │   ├── tools/                     # 자산 특화 Tool (필요 시)
│   │   └── dags/                      # Airflow DAG (소스별)
│   │       ├── news_collection.py     # 뉴스 수집 DAG
│   │       ├── transaction_collection.py  # 실거래가 [추후]
│   │       └── building_register.py   # 건축물대장 [추후]
│   │
│   └── music_copyright/               # 음악 저작권 (POC 2번째)
│       ├── profile.py
│       ├── config/
│       │   ├── search_groups.yaml
│       │   └── ontology_schema.py
│       ├── targets/
│       │   ├── artist.py              # 아티스트
│       │   └── song.py                # 음원 (ISRC)
│       └── dags/
│           ├── news_collection.py
│           └── streaming_collection.py
│
├── interfaces/
│   ├── composition.py                 # AssetProfile 받아 의존성 조립
│   └── cli.py                         # python -m interfaces.cli run-once <asset>
│
├── config/
│   └── policy.yaml                    # 자산 무관 정책 (임계치, API 한도)
│
├── tests/
│   ├── core/
│   │   ├── agents/                    # orchestrator e2e + flow smoke
│   │   ├── collectors/
│   │   ├── evaluation/
│   │   ├── llm/                       # PromptCatalog + pricing + enum drift
│   │   ├── processors/
│   │   ├── reporting/
│   │   └── shared/
│   │       ├── infra/                 # TracingLLMClient + observability backends
│   │       └── test_api_key_rotator.py
│   └── projects/
│       └── commercial_real_estate/
│
├── docs/                              # 본 문서들
└── pyproject.toml
```

---

## 2. core vs projects 분리 원칙

판단이 헷갈릴 때 적용할 단순 규칙.

| 위치 | 기준 | 예시 |
|---|---|---|
| `core/` | 다른 자산에서도 재사용 가능 | `RuleFilterService`, `Collector` ABC, `SemanticDedup` |
| `projects/<자산>/` | 자산명·자산 식별자·자산 평가 요인이 코드에 등장 | `BuildingTarget(pnu)`, 상가 검색어 사전, 부동산 온톨로지 사전 |

**자산 디렉토리는 비어있어도 OK.** 상가형 부동산이 자산 특화 collector를 필요로 하지 않으면 `projects/commercial_real_estate/collectors/` 는 빈 채로 둔다.

### 회색 지대 처리

- **온톨로지 스키마 (평가 요인 사전)**: 자산별로 달라지므로 `projects/<자산>/config/ontology_schema.py` 에 둔다. 공통 enum(SignalType, Applicability)만 `core/shared/domain/ontology_schema.py`에 둔다.
- **검색어 그룹**: 완전히 자산 특화. `projects/<자산>/config/search_groups.yaml`.
- **API Key, 임계치, 안전 비율**: 자산 무관. `config/policy.yaml`.

---

## 3. 의존 방향 규칙

```
interfaces / projects
        │
        ▼
   core/application      ← 비즈니스 흐름
        │
   ┌────┴────────┐
   ▼             ▼
core/shared   core/collectors
              core/processors
              core/evaluation
```

엄격히 지켜야 할 규칙:

- `core/shared/` 는 외부 라이브러리 import 금지 (순수 Python)
- `core/` 의 어느 모듈도 `projects/` 를 import 하지 않는다
- `projects/<A>/` 는 `projects/<B>/` 를 import 하지 않는다 (자산 간 격리)
- `interfaces/composition.py` 만 모든 모듈을 알고 있다 (Composition Root)

---

## 4. 핵심 추상화 명세

### 4.1 Collector

외부 데이터를 수집하는 모든 컴포넌트의 공통 인터페이스.

```python
# core/collectors/base.py

@dataclass
class CollectionPlan:
    queries: list[CollectionQuery]
    estimated_calls: int
    provider_breakdown: dict[str, int]

@dataclass
class CollectionQuery:
    text: str
    source_type: str         # "news", "transaction", "streaming", ...
    asset_class: AssetClass | None
    max_results: int = 10
    extra: dict = field(default_factory=dict)  # source별 파라미터

@dataclass
class RawRecord:
    """얇은 공통 모델. 세부는 source_type별 typed accessor가 처리."""
    source_type: str
    source_id: str           # provider 내 고유 ID
    content: dict            # 정규화된 원본
    collected_at: datetime
    metadata: dict = field(default_factory=dict)

class Collector(ABC):
    @property
    @abstractmethod
    def source_type(self) -> str: ...

    @abstractmethod
    def collect(self, query: CollectionQuery) -> list[RawRecord]: ...

    @abstractmethod
    def quota_estimate(self, query: CollectionQuery) -> int: ...
```

`NaverNewsCollector` 가 `Collector` 를 구현. 향후 `TransactionCollector`, `StreamingStatCollector` 등이 추가된다.

### 4.2 EvaluationStrategy

평가 3축의 추상 인터페이스.

```python
# core/evaluation/base.py

class EvaluationDimension(Enum):
    QUANTITATIVE = "quantitative"
    STRUCTURAL = "structural"
    SENTIMENT = "sentiment"

class EvaluationStrategy(ABC):
    @property
    @abstractmethod
    def dimension(self) -> EvaluationDimension: ...

    @abstractmethod
    def evaluate(
        self,
        asset_id: str,
        profile: "AssetProfile",
    ) -> list[EvaluationClaim]: ...
```

`SentimentEvaluationStrategy` 가 본 프로젝트의 메인 구현. `Quantitative`, `Structural` 은 stub.

### 4.3 EvaluationTarget / SentimentTarget

평가 대상의 추상화.

```python
# core/shared/domain/evaluation.py

class EvaluationTarget(ABC):
    target_type: str         # "building", "tenant", "artist", "song", "issuer"

    @abstractmethod
    def unique_key(self) -> str:
        """법적 고유번호 기반 키. PNU, 사업자번호, ISRC, 법인번호 등."""

    @abstractmethod
    def label(self) -> str:
        """사람이 읽을 수 있는 표시명."""

# core/evaluation/sentiment/target_base.py

class SentimentTarget(EvaluationTarget):
    """감정평가 대상의 추상 기반."""
```

자산별 구체 클래스:
- `projects/commercial_real_estate/targets/building.py` → `BuildingTarget(pnu)`
- `projects/commercial_real_estate/targets/tenant.py` → `TenantTarget(business_number)`
- `projects/music_copyright/targets/artist.py` → `ArtistTarget(...)`
- `projects/music_copyright/targets/song.py` → `SongTarget(isrc)`

### 4.4 EvaluationClaim

평가 결과의 통합 모델.

```python
# core/shared/domain/evaluation.py

@dataclass
class Evidence:
    source_type: str         # "news", "review", "transaction"
    source_id: str
    excerpt: str
    score_contribution: float | None = None

@dataclass
class EvaluationClaim:
    asset_id: str
    target: EvaluationTarget
    dimension: EvaluationDimension
    score: float                          # 0.0 ~ 100.0
    evidence: list[Evidence]
    rationale: str
    created_at: datetime
    metadata: dict = field(default_factory=dict)
```

이 하나의 모델로 `정량 × 부동산 건물`, `감정 × 입점업체`, `구조 × 발행사` 같은 모든 조합을 표현한다.

### 4.5 AssetProfile

자산-평가축-수집소스-에이전트 도구의 매핑.

```python
# core/shared/domain/asset.py (혹은 projects/<자산>/profile.py)

@dataclass
class AssetProfile:
    asset_class: AssetClass
    evaluation_dimensions: list[EvaluationDimension]    # 이 자산이 가지는 평가축
    sentiment_target_types: list[type[SentimentTarget]]  # 감정평가 대상 종류
    collector_source_types: list[str]                    # 사용할 collector 소스 ("news" 등)
    config_path: Path                                    # search_groups.yaml 경로
    ontology_schema_module: str                          # 자산 특화 평가 요인 사전 모듈 경로
    allowed_tools: list[str] = field(default_factory=list)  # [확장 예정] 에이전트 노출 도구

    def root_dir(self) -> Path:
        return self.config_path.parent.parent
```

자산 추가 = `projects/<자산>/profile.py` 에 AssetProfile 인스턴스 1개 정의 + 필요한 특화 코드만 추가.

`allowed_tools` 는 ExplorationFlow / QAFlow 의 PolicyGate 에 주입되어 자산별 도구 노출을 결정한다 ([AGENT_DESIGN.md §5.3](AGENT_DESIGN.md#53-자산별-다른-정책)).

### 4.6 OntologyTagger (스키마 주입식)

자산별 평가 요인 사전을 주입받아 동작하는 태거.

```python
# core/processors/taggers/base.py

class OntologyTagger(ABC):
    def __init__(self, llm_client: LLMClient, schema: OntologySchema):
        ...

    @abstractmethod
    def tag(self, raw_record: RawRecord, profile: AssetProfile) -> OntologyTag: ...
```

`OntologySchema` 는 자산별로 다르다. 부동산은 `["임대수익률", "공실위험", "거래량"]`, 음악은 `["스트리밍 추세", "저작권 분쟁"]` 등. 자산 모듈에서 정의되어 주입된다.

### 4.7 GraphStore (scope_id 격리)

분석 단위로 격리된 그래프 read/write. POC 는 InMemory, 영구는 추후 ([D-03](DECISIONS.md#d-03)).

```python
# core/shared/stores/graph_store.py

class GraphStore(ABC):
    @abstractmethod
    def upsert_node(self, scope_id: str, node: GraphNode) -> str: ...

    @abstractmethod
    def upsert_relation(self, scope_id: str, relation: GraphRelation) -> None: ...

    @abstractmethod
    def query_subgraph(self, scope_id: str) -> Subgraph: ...

    @abstractmethod
    def find_nodes(self, scope_id: str, label: str) -> list[GraphNode]: ...

    @abstractmethod
    def drop_scope(self, scope_id: str) -> None: ...
```

scope_id 의미: 휘발 모드 = `analysis_<uuid>`, 영구 모드 = `asset_<id>` 또는 `region_<code>`.

기존 `core/shared/infra/graph_writer.py` 의 `GraphWriter` 는 배치 적재용으로 유지. 신규 코드(에이전트, 보고서)는 `GraphStore` 사용.

### 4.8 Agent / AgentContext / EvidenceTrace

모든 (서브)에이전트 및 Flow 의 공통 인터페이스.

```python
# core/agents/base.py

class Agent(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, context: AgentContext) -> AgentContext: ...

@dataclass
class AgentContext:
    scope_id: str
    inputs: dict
    artifacts: dict                    # 단계 간 공유 산출물 (POC: dict, 추후 typed)
    evidence: EvidenceTrace

@dataclass
class EvidenceStep:
    step_id: int
    actor: str
    tool_name: str
    rationale: str
    input_summary: dict
    result_summary: dict
    occurred_at: datetime

@dataclass
class EvidenceTrace:
    scope_id: str
    steps: list[EvidenceStep]
```

Flow 자체도 Agent ABC 를 구현 ([D-06](DECISIONS.md#d-06)) — 외부에서 통일된 진입점.

### 4.9 AgentPolicy / PolicyGate

자율 에이전트의 도구 호출 / 비용 / 루프 통제.

```python
# core/agents/policy.py

@dataclass
class AgentPolicy:
    max_tool_calls: int = 10
    max_cost_usd: float = 1.0
    allowed_tools: list[str]            # AssetProfile 에서 주입
    require_rationale: bool = True

class PolicyGate:
    def check(self, tool_name, rationale, estimated_cost) -> PolicyDecision: ...
    def record(self, cost: float = 0.0) -> None: ...
```

상세 흐름: [AGENT_DESIGN.md §5](AGENT_DESIGN.md#5-policygate-하이브리드-자율성-통제).

### 4.10 PromptCatalog (LLM 자산 분리)

LLM prompt 와 응답 스키마를 YAML 파일로 외부화. 각 에이전트/서비스는 인라인 prompt 문자열을 들지 않고 `PromptCatalog.render(key, **vars)` 로 받는다.

```python
# core/llm/catalog.py

@dataclass(frozen=True)
class RenderedPrompt:
    key: str
    version: int
    version_hash: str          # sha256(system+user+schema) — Langfuse 메타로 송신
    system: str
    user: str
    response_schema: dict | None

    def to_llm_request(self, *, temperature=0.0, max_tokens=2048) -> LLMRequest: ...

class PromptCatalog:
    def __init__(self, root: Path | None = None): ...
    def get(self, key: str) -> PromptTemplate: ...     # raw 템플릿
    def render(self, key: str, **variables) -> RenderedPrompt: ...
    def list_keys(self) -> list[str]: ...
```

**키 규칙**: 디렉토리 경로의 도트 표기. `"exploration.planner"` → `core/llm/prompts/exploration/planner.yaml`.

**치환 문법**: `string.Template` 의 `$var` / `${var}`. prompt 안의 JSON 예시 `{"key": ...}` 와 충돌 없음.

**YAML 형식**:
```yaml
version: 1
description: 한 줄 설명
system: |
  Allowed tools: $tools.
  Respond as JSON: {"calls": [{"tool": str}]}.
user: |
  Address: $address
schema: { ... JSON schema ... }
```

**evidence 통합**: 각 서브 에이전트는 `EvidenceStep.input_summary["prompt_version"] = rendered.version_hash` 로 기록. 보고서/디버그 시 어떤 prompt 버전이 쓰였는지 추적 가능.

**enum drift 보호**: `tagging.sentiment` / `mapping.llm_fallback` 의 enum 값은 코드 enum(`AssetClass`, `SignalType` 등)과 일치해야 함. `tests/core/llm/test_prompt_catalog.py` 가 일치 검증.

### 4.11 TraceBackend / TracingLLMClient (observability)

LLM 호출 / 에이전트 흐름을 외부 백엔드(Langfuse 등)로 추적.

```python
# core/shared/infra/observability/base.py

class TraceBackend(ABC):
    def start_trace(name, trace_id, metadata=None) -> TraceContext: ...
    def end_trace(ctx, output=None, error=None) -> None: ...
    def start_generation(trace, name, role, model, input, metadata=None) -> GenerationContext: ...
    def end_generation(gen, output=None, usage=None, error=None) -> None: ...
    def flush() -> None: ...

@contextmanager
def trace_scope(backend, name, trace_id, metadata=None) -> TraceContext:
    """contextvars 기반 trace 라이프사이클. 내부 LLM 호출이 자동으로 같은 trace에 속함."""

def current_trace() -> TraceContext | None:
    """현재 contextvar 의 trace 반환."""
```

구현체:
- `NoOpBackend` — 기본값, 외부 호출 0
- `StdoutBackend` — JSON line 로깅
- `LangfuseBackend` — Langfuse Cloud / Self-hosted (lazy import, 키 부재 시 disabled)

```python
# core/shared/infra/tracing_llm_client.py

class TracingLLMClient(LLMClient):
    """LLMClient 데코레이터. 모든 call() 을 TraceBackend 로 전송 + 옵션으로 PolicyGate 자동 record."""
    def __init__(self, inner, backend, role, *, policy_gate=None, generation_name=None): ...
```

**호출 지점은 LLMClient ABC 만 의존** — 데코레이터 적용 여부와 무관하게 코드 변경 0. Orchestrator 가 `trace_scope()` 한 번만 열면 내부 모든 LLM 호출이 자동으로 같은 trace에 첨부 (contextvars).

**PolicyGate 자동 record**: `policy_gate` 주입 시 `usage`/`model` 자동 누적. 서브 에이전트들이 명시적으로 `gate.record()` 호출 안 해도 됨.

### 4.12 OntologyMapper (어댑터 + LLM fallback)

수집물을 그래프 노드/엣지로 매핑. 어댑터 등록된 입력은 (가) 직접, 미등록은 (다) LLM ([D-09](DECISIONS.md#d-09)).

```python
# core/processors/ontology_mapper/base.py

class BaseAdapter(ABC):
    @property
    @abstractmethod
    def source_type(self) -> str: ...

    @abstractmethod
    def map(self, raw: RawRecord) -> list[GraphNode | GraphRelation]: ...

class OntologyMapper:
    def __init__(self, registry: dict[str, BaseAdapter], llm_fallback: LLMFallbackMapper):
        ...

    def map(self, raw: RawRecord) -> list[GraphNode | GraphRelation]:
        adapter = self._registry.get(raw.source_type)
        if adapter is not None:
            return adapter.map(raw)
        return self._llm_fallback.map(raw)
```

어댑터 추가 절차는 [EXTENSION_GUIDE.md](EXTENSION_GUIDE.md), 매핑 정책은 [ONTOLOGY.md](ONTOLOGY.md).

---

## 5. 처리 상태 Enum

`core/shared/domain/states.py` 에 6종이 정의된다.

| Enum | 값 | 용도 |
|---|---|---|
| `IngestionStatus` | new, url_duplicate, hash_duplicate, save_failed | 수집 단계 |
| `FilterStatus` | pending, passed, excluded, failed | 룰 필터링 |
| `EmbeddingStatus` | pending, done, failed, excluded | 임베딩 |
| `DedupStatus` | pending, novel, duplicate, failed | 의미 중복 제거 |
| `TagStatus` | pending, done, failed, excluded | LLM 온톨로지 태깅 |
| `GraphStatus` | pending, queued, done, failed, excluded | Signal 적재 |

각 excluded 상태는 사유 Enum과 함께 기록된다.

---

## 6. 객체지향 설계 원칙 요약

| 원칙 | 적용 방식 |
|---|---|
| DAG는 로직을 가지지 않는다 | DAG는 `core/pipelines/tasks.py` 의 함수만 호출 |
| Tool은 로직을 가지지 않는다 | Tool은 Application Service만 호출 |
| Provider는 외부 API 호출만 담당 | `Collector` ABC 뒤에 캡슐화 |
| Repository는 저장소 접근만 담당 | 비즈니스 판단 로직 금지 |
| Service는 흐름을 담당 | 여러 Repository / Collector / Adapter 조합 |
| Domain Model은 개념을 표현 | 외부 의존 0, 순수 dataclass |
| 구현체는 인터페이스 뒤에 숨김 | ABC + 구체 구현 분리 |
