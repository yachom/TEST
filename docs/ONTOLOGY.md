# 온톨로지 매핑

본 문서는 본 시스템의 핵심 작업인 **수집된 정보를 온톨로지 어휘로 정형화하여 그래프 DB 에 적재** 하는 정책을 기술한다.

---

## 1. 온톨로지란 무엇인가

비개발자 / 새 합류자를 위한 짧은 설명.

**온톨로지 = 공유 어휘 + 관계 규칙.**

단순히 "그래프에 노드와 엣지로 데이터를 표현한다" 는 말로는 부족하다. 온톨로지의 핵심은 **모든 노드가 미리 합의된 어휘 안에서만 정의된다** 는 점이다.

예시:
- "Land 는 LandUse 를 가진다" 는 관계 규칙
- "LandUse 는 정해진 분류표(예: 제2종근린, 일반상업, 주거 등) 안에서만 선택된다" 는 어휘 규칙

이 규칙이 미리 합의되어 있어야:
- 자산 A 의 데이터와 자산 B 의 데이터가 **같은 LandUse 노드를 공유** 할 수 있고
- "이 LandUse 에 영향 주는 규제는?" 같은 질문이 그래프 traversal 로 풀린다

본 시스템이 그래프 DB 를 쓰는 이유도 이 traversal 때문이다. 관계가 1차 시민이라야 "이 자산에 영향 주는 신호" 같은 질문이 자연스럽게 풀린다.

---

## 2. 어휘 정의의 위치

| 위치 | 내용 | 변경 빈도 |
|---|---|---|
| `core/shared/domain/ontology_schema.py` | 자산 무관 공통 enum (SignalType, InfluenceDirection, Applicability 등) | 낮음 |
| `projects/<자산>/config/ontology_schema.py` | 자산별 평가 요인 사전, 이벤트 유형, 자산 하위 유형 | 자산 추가/수정 시 |

**원칙**: 두 자산 이상에서 같은 어휘가 쓰이면 `core/` 로 승격. 한 자산만 쓰면 `projects/` 에 둔다.

POC 단계에서는 어휘가 작게 시작하고 자산을 분석하면서 점진적으로 확장된다.

---

## 3. 매핑 두 방식 — 핵심 결정

수집물 → 그래프 노드/엣지 매핑은 두 방식이 있다. 입력 형태에 따라 다르게 적용한다.

### 3.1 (가) 방식 — 직접 매핑 (코드)

**적용 입력**: 미리 스키마가 정의된 API 응답 (vworld, 건축허브, 입점 상가 API 등).

**과정**: 어댑터 코드가 응답 dict 를 직접 노드/엣지로 변환. LLM 호출 없음.

**예시 입력**:
```json
{
  "address": "강남구 ○○동 123-45",
  "land_area_m2": 1500.5,
  "land_use": "제2종 근린생활시설",
  "owner_count": 47,
  "official_price_won": 85000000
}
```

**예시 출력**:
```
(:Address {pnu, address})
   ─[:HAS_LAND]→ (:Land {area_m2: 1500.5, official_price: 85000000})
                    ─[:HAS_USE]→ (:LandUse {code: "제2종근린"})
                    ─[:OWNED_BY]→ (:OwnershipFact {count: 47})
```

**장점**:
- 결정적, 빠름, 호출 비용 0
- 숫자/식별자 정밀 보존 (47 이 그대로 47)
- 같은 LandUse 노드를 다른 자산이 공유 가능 → traversal 으로 신호 자동 연결

**제약**:
- 어댑터 작성 비용 발생 (도구마다 1개씩)

### 3.2 (다) 방식 — 텍스트 평탄화 후 LLM

**적용 입력**: 비정형 텍스트 (웹검색 결과, 토지대장 PDF, 뉴스 기사, 사용자 업로드 문서 등).

**과정**:
1. 입력을 자연어 텍스트로 평탄화
2. LLM 이 OntologyTag 생성 (어휘 사전 주입식)
3. OntologyTag → 노드/엣지 매핑

**예시**:
```
"○○ 빌딩 인근 상권에 신규 카페 5개가 개점하며 ..."
       ↓ LLM
OntologyTag(
    signal_type=MARKET,
    affected_evaluation_factors=["상권 활성도"],
    influence_direction=POSITIVE,
    summary="...",
    extra={"local_indicators": ["신규 개점 5건"]}
)
       ↓ pattern_builder
(:MarketSignal) ─[:AFFECTS]→ (:EvaluationFactor {name: "상권 활성도"})
```

**장점**:
- 비정형 입력도 처리 가능
- 새 정보 형태가 등장해도 어댑터 작성 불필요

**제약**:
- 비결정적, 호출 비용 발생
- LLM 해석 단계에서 정밀도 손실 가능 (47 → "약 50명" 등)

### 3.3 결합 정책

```
입력
 │
 ▼
어댑터 레지스트리 조회
 │
 ├── 등록된 어댑터 있음 → (가) 직접 매핑
 └── 어댑터 없음 → (다) 텍스트 평탄화 + LLM
```

신규 도구가 추가될 때, 출력 스키마가 안정적이면 어댑터를 작성하여 (가) 로, 가변적이거나 비정형이면 어댑터 없이 (다) fallback 으로 운영.

---

## 4. 코드 구조

```
core/processors/ontology_mapper/        # [신규]
├── __init__.py
├── base.py                  # OntologyMapper, AdapterRegistry, BaseAdapter
├── adapters/
│   ├── vworld_adapter.py    # (가) — vworld 응답 직접 매핑
│   ├── building_hub_adapter.py
│   ├── tenant_adapter.py
│   └── (확장 자리)
└── llm_fallback.py          # (다) — 어댑터 미등록 입력 처리

core/processors/graph_writers/
├── pattern_builder.py       # OntologyTag → GraphNode/Relation 패턴 매핑 [신규]
├── signal_writer.py         # (기존) — 배치용
└── signal_joiner.py         # placeholder, POC 보류
```

### 4.1 OntologyMapper 인터페이스

```python
# core/processors/ontology_mapper/base.py

class BaseAdapter(ABC):
    @property
    @abstractmethod
    def source_type(self) -> str: ...

    @abstractmethod
    def map(self, raw: RawRecord) -> list[GraphNode | GraphRelation]: ...


class OntologyMapper:
    """어댑터 레지스트리 + LLM fallback 보유."""

    def __init__(self, registry: dict[str, BaseAdapter], llm_fallback: LLMFallbackMapper):
        self._registry = registry
        self._llm_fallback = llm_fallback

    def map(self, raw: RawRecord) -> list[GraphNode | GraphRelation]:
        adapter = self._registry.get(raw.source_type)
        if adapter is not None:
            return adapter.map(raw)
        return self._llm_fallback.map(raw)
```

### 4.2 LLM Fallback

```python
# core/processors/ontology_mapper/llm_fallback.py

class LLMFallbackMapper:
    def __init__(
        self,
        llm_client: LLMClient,
        pattern_builder: GraphPatternBuilder,
        prompt_catalog: PromptCatalog,
    ):
        self._llm = llm_client
        self._builder = pattern_builder
        self._catalog = prompt_catalog

    def map(self, raw: dict) -> list[GraphItem]:
        text = self._flatten_to_text(raw)
        rendered = self._catalog.render("mapping.llm_fallback", flattened_text=text)
        response = self._llm.call(rendered.to_llm_request())
        tag = self._build_tag(raw, response.parsed or {})
        return self._builder.build(tag)
```

prompt 와 응답 JSON Schema 는 `core/llm/prompts/mapping/llm_fallback.yaml` 에 정의된다 ([D-16](DECISIONS.md#d-16)). 코드 수정 없이 LLM 매핑 동작을 조정하려면 YAML 만 변경.

배치 흐름의 `sentiment_tagger` 와 매우 유사한 구조 — 둘 다 PromptCatalog 의 다른 키 (`tagging.sentiment` vs `mapping.llm_fallback`) 를 사용. 차이는 입력 형태 (NewsArticle vs 평탄화된 dict) 와 schema 의 변형.

---

## 5. 그래프 DB 정책

### 5.1 휘발 vs 영구

POC 는 **휘발(InMemoryGraphStore)**, 영구는 추후.

영구가 진짜 의미를 가지려면 다음이 선행되어야 한다:
- 지리/행정동 기반 인접 자산 그룹화 룰
- 같은 주소 재분석 시 차이 비교 룰
- scope 관리 정책 (언제 누적, 언제 분리)

이 검증 부담이 POC 범위 밖이라 휘발로 시작.

### 5.2 scope_id 격리

같은 GraphStore 안에서 분석 단위를 격리하기 위해 모든 read/write 메서드가 `scope_id` 를 받는다.

| 모드 | scope_id 의미 | 예시 |
|---|---|---|
| 휘발 (POC) | 분석 세션 단위 | `analysis_<uuid>` |
| 영구 (향후) | 자산 또는 지역 단위 | `asset_<id>`, `region_<code>` |

```python
class GraphStore(ABC):
    @abstractmethod
    def upsert_node(self, scope_id: str, node: GraphNode) -> str: ...

    @abstractmethod
    def query_subgraph(self, scope_id: str) -> Subgraph: ...

    @abstractmethod
    def drop_scope(self, scope_id: str) -> None: ...
```

휘발 모드에서는 분석 종료 시 `drop_scope(scope_id)` 호출. 영구 모드에서는 호출 안 함.

### 5.3 자동 수집 그래프 ↔ 온디멘드 분석 그래프 연결

**채택 방향(옵션 A)**: 자동 수집 신호도 같은 온톨로지 어휘로 그래프화. 같은 LandUse / EvaluationFactor 노드를 공유하므로 traversal 으로 자동 연결.

**POC 에서의 구체화**: 보류. 자동 수집 그래프화는 검색어 설정·어휘 합의 등 사전 작업이 필요. 자리만 만들어둠 (`signal_joiner.py` placeholder).

---

## 6. POC 단계 단순화

| 영역 | POC | 추후 |
|---|---|---|
| 어댑터 수 | 1~2 개 (Mock 도구 + Naver 뉴스) | 도구 추가에 따라 |
| 어휘 사전 | 평가 요인 리스트만 | 노드 라벨 / 엣지 타입 사전 |
| LLM 응답 스키마 | placeholder JSON | 운영 스키마 |
| 그래프 DB | InMemory | Neo4j 검토 |
| signal_joiner | placeholder | 자동 수집 그래프화 후 구현 |

---

## 7. 새 도구 / 새 입력 형태 추가 절차

### 7.1 구조화된 응답을 가진 새 도구

1. 도구 자체를 `core/tools/` 에 추가 (BaseTool 구현)
2. 어댑터 작성 — `core/processors/ontology_mapper/adapters/<name>_adapter.py`
3. composition.py 에서 OntologyMapper 의 registry 에 등록
4. 어휘 추가가 필요하면 `core/shared/domain/ontology_schema.py` 또는 `projects/<자산>/config/ontology_schema.py` 갱신

### 7.2 비정형 입력만 있는 도구 (웹검색 등)

1. 도구 추가
2. 어댑터 작성 불필요 — LLM fallback 으로 자동 처리
3. 어휘 사전이 풍부할수록 fallback 결과 품질 향상

---

## 8. 참고 문서

- [ARCHITECTURE.md](ARCHITECTURE.md) — 매핑이 전체 흐름 어디에 위치하는지
- [AGENT_DESIGN.md](AGENT_DESIGN.md) — 어떤 에이전트가 어떤 입력을 매퍼에 던지는지
- [DECISIONS.md](DECISIONS.md) — (가)+(다) 결합, scope_id, 옵션 A 선택의 이유
