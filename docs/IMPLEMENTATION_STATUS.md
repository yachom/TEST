# 구현 현황 및 교체 가이드

본 문서는 다음 두 질문에 답하기 위한 단일 출처다.

1. **현재 무엇이 동작하는가?** — 어떤 입력이 어떤 파일·함수를 거쳐 어떤 출력이 되는지.
2. **어디가 임시이고, 무엇으로 교체해야 하는가?** — Mock / Stub / Placeholder 인벤토리 + 교체 우선순위.

대상 독자: (1) 새 세션에서 구현 진행 상황을 빠르게 파악해야 하는 개발자, (2) Phase 4 (실제 외부 연동) 작업자, (3) 새 도구 / 새 어댑터를 추가할 사람.

---

## 1. 한눈에 보기

| 항목 | 상태 |
|---|---|
| 배치 파이프라인 (Airflow) | **별도 레포 `fnpricing-batch` 운영** ([D-19](DECISIONS.md#d-19)). 본 레포는 라이브러리 + CLI `run-once` 검증용 |
| On-demand 주소 분석 | 뼈대 동작 (Stub LLM + Mock 도구) + `claims: list[EvaluationClaim]` 반환 (현재 stub) |
| 테스트 | **119 개 통과** |
| CLI | `run-once`, `search`, `analyze-address`, `init-db` (`.env` 자동 로드) |
| 그래프 DB | InMemory (휘발) |
| LLM | Stub / LangChain (OpenAI / Anthropic), 모든 호출이 PromptCatalog 경유, TracingLLMClient wrap |
| Observability | TraceBackend ABC + NoOp/Stdout/Langfuse (default: NoOp) |
| **확장 자리 (D-18, 2026-05-12)** | **9 ABC + 4 DB 테이블 — placeholder 구현체로 미리 열림** |
| 도구 | Mock 1 개 + VworldTool/TransactionTool/BuildingRegisterTool (real_tools 모드) |

```
$ python -m interfaces.cli analyze-address "강남구 역삼동 123-45" \
    --show-evidence --question "이 자산의 임대수익률은?"
```

---

## 2. On-demand 주소 분석 — 데이터 흐름 상세

### 2.1 전체 다이어그램

```
사용자 (CLI 또는 API)
       │
       ▼  address: str
[interfaces/cli.py::cmd_analyze_address]
       │
       ▼  AssetClass, address
[interfaces/composition.py::build_address_analysis_orchestrator]
       │
       ▼  Orchestrator 인스턴스
[core/agents/orchestrator.py::Orchestrator.analyze(address)]
       │
       ├─ scope_id = "analysis_<uuid>" 발급
       ├─ AgentContext 생성 (scope_id, inputs={"address": address})
       │
       ▼
   ① InitialCollector.collect(address)
       │     [core/agents/initial_collector.py]
       │     입력: address
       │     출력: list[dict]  (도구별 응답)
       │
       ▼  ctx.artifacts["initial_collection"] = list[dict]
   ② ExplorationFlow.run(ctx)
       │     [core/agents/exploration/flow.py]  ← LangGraph
       │     서브 에이전트 루프 (최대 3회)
       │
       │  Planner → Retriever → Critic → [replan or done]
       │
       ▼  ctx.artifacts["retrieved"] = list[{"tool", "result"}]
   ③ all_raw = initial_collection + [r["result"] for r in retrieved]
   ④ OntologyMapper.map_all(all_raw)
       │     [core/processors/ontology_mapper/base.py]
       │     출력: list[GraphNode | GraphRelation]
       │
       ▼
   ⑤ for item in graph_items:
   ⑥     graph_store.upsert_node/relation(scope_id, item)
       │     [core/shared/stores/graph_store.py::InMemoryGraphStore]
       │
       ▼
   ⑦ ReportBuilder.build(scope_id)
       │     [core/reporting/report_builder.py]
       │     출력: dict (scope_id, node_count, summary 등)
       │
       ▼
   ⑧ AnalysisResult(scope_id, report, qa_flow, evidence) 반환
       │
       ▼
사용자가 추가 질문 시 →
   ⑨ QAService.ask(scope_id, question)
         [core/reporting/qa_service.py]
         → QAFlow.run(ctx)
         → 답변 dict
```

### 2.2 단계별 상세

#### ① InitialCollector — 결정적 1차 수집

| 항목 | 내용 |
|---|---|
| 파일 | [core/agents/initial_collector.py](../core/agents/initial_collector.py) |
| 입력 | `address: str` |
| 출력 | `list[dict]` — 도구별 응답 |
| 호출 도구 | composition 에서 주입된 `BaseTool` 목록 (POC: `MockAddressInfoTool` 1 개) |
| 자율성 | 없음 (등록된 도구를 순서대로 호출) |
| 다음 단계 | ctx.artifacts["initial_collection"] 에 저장 → ExplorationFlow |

각 도구 응답 dict 형태:
```python
{
    "source_type": "mock_address",      # OntologyMapper 라우팅 키
    "source_id": address,
    "content": {
        "address": "...",
        "land_use": "제2종근린",
        "land_area_m2": 1500.0,
        "owner_count": 47,
    },
}
```

#### ② ExplorationFlow — 자율 추가 수집 루프

| 항목 | 내용 |
|---|---|
| 파일 | [core/agents/exploration/flow.py](../core/agents/exploration/flow.py) |
| 라우팅 | LangGraph StateGraph |
| 종료 조건 | Critic 충분 / iteration ≥ 3 / PolicyGate 한도 도달 |

**Planner** ([planner.py](../core/agents/exploration/planner.py))
- 입력: `ctx.artifacts["initial_collection"]` + `ctx.artifacts["retrieved"]` (재계획 시) + `ctx.artifacts["critic_feedback"]`
- LLM 호출: 추가 도구 호출 계획 생성
- 출력: `ctx.artifacts["plan"] = [{"tool", "input", "rationale"}, ...]`
- Evidence: 1 step (`exploration.planner` / `llm`)

**Retriever** ([retriever.py](../core/agents/exploration/retriever.py))
- 입력: `ctx.artifacts["plan"]`
- 각 호출마다 PolicyGate.check → 통과 시 도구 실행 → PolicyGate.record
- 차단된 호출 / 미등록 도구 / 정상 호출 모두 EvidenceStep 기록
- 출력: `ctx.artifacts["retrieved"]` 에 `{"tool", "result"}` 추가
- Evidence: plan 항목 수만큼 (또는 차단/미등록 시에도)

**Critic** ([critic.py](../core/agents/exploration/critic.py))
- 입력: 누적 `initial` + `retrieved` 카운트
- LLM 호출: 충분성 판정
- 출력: `ctx.artifacts["critic_decision"] = "sufficient" | "needs_more"` + `ctx.artifacts["critic_feedback"]`
- Evidence: 1 step

#### ③+④ OntologyMapper — 수집물 → 그래프 아이템

| 항목 | 내용 |
|---|---|
| 파일 | [core/processors/ontology_mapper/base.py](../core/processors/ontology_mapper/base.py) |
| 입력 | `list[dict]` — InitialCollector 응답 + Retriever 응답 합본 |
| 출력 | `list[GraphNode | GraphRelation]` |
| 라우팅 | `raw["source_type"]` 으로 어댑터 검색 → 등록된 어댑터 있으면 (가), 없으면 (다) |

(가) **MockAddressAdapter** ([adapters/mock_adapter.py](../core/processors/ontology_mapper/adapters/mock_adapter.py))
- `source_type == "mock_address"` 응답을 직접 매핑
- 출력 패턴: Address 노드 + LandUse 노드 + HAS_USE 엣지

(다) **LLMFallbackMapper** ([llm_fallback.py](../core/processors/ontology_mapper/llm_fallback.py))
- 어댑터 없는 입력을 텍스트 평탄화 → LLM 호출 → OntologyTag 생성
- OntologyTag → GraphPatternBuilder → 그래프 아이템

#### ⑤ GraphPatternBuilder — OntologyTag → 그래프

| 항목 | 내용 |
|---|---|
| 파일 | [core/processors/graph_writers/pattern_builder.py](../core/processors/graph_writers/pattern_builder.py) |
| 입력 | `OntologyTag` |
| 출력 | `[MarketSignal 노드] + [EvaluationFactor 노드 + AFFECTS 엣지] * N` |

POC 매핑은 단순. 추후 신호 → 평가요인 / 지역 / 기간 / 자산 하위유형 등 다중 엣지로 정교화.

#### ⑥ GraphStore — 분석 그래프 적재

| 항목 | 내용 |
|---|---|
| 파일 | [core/shared/stores/graph_store.py](../core/shared/stores/graph_store.py) |
| 구현체 | `InMemoryGraphStore` (POC) |
| scope_id | `analysis_<uuid12>` |
| 주요 메서드 | `upsert_node`, `upsert_relation`, `query_subgraph`, `find_nodes`, `drop_scope` |

#### ⑦ ReportBuilder — 그래프 → 보고서

| 항목 | 내용 |
|---|---|
| 파일 | [core/reporting/report_builder.py](../core/reporting/report_builder.py) |
| 입력 | `scope_id` |
| 가공 | `graph_store.query_subgraph(scope_id)` → `GraphQueryPolicy.filter` → 통계 집계 + LLM 요약 |
| 출력 | dict (`scope_id`, `node_count`, `relation_count`, `nodes_by_label`, `relations_by_type`, `summary`) |

#### ⑧ AnalysisResult — Orchestrator 반환

| 항목 | 내용 |
|---|---|
| 파일 | [core/agents/orchestrator.py](../core/agents/orchestrator.py) |
| 필드 | `scope_id: str`, `report: dict`, `qa_flow: QAFlow`, `evidence: EvidenceTrace` |

#### ⑨ QAService / QAFlow — 사용자 질문 응답

| 항목 | 내용 |
|---|---|
| 파일 | [core/reporting/qa_service.py](../core/reporting/qa_service.py), [core/agents/qa/flow.py](../core/agents/qa/flow.py) |
| 입력 | `scope_id`, `question` |
| 종료 조건 | Verifier pass / synth_attempt ≥ 2 |
| 출력 | dict (`answer`, `citations`, `verifier_decision`, `evidence_steps`) |

**Analyzer** → 질문 분류 (`factual` / `reasoning` / `comparison` / `temporal`)
**QARetriever** → graph_store.query_subgraph + (kind 별) report_store / signal_store 검색
**Synthesizer** → 답변 초안 + citations
**Verifier** → 근거 정합성 판정 (실패 시 Synthesizer 재시도)

### 2.3 AgentContext.artifacts 키 사전

Flow 내부에서 서브 에이전트들이 주고받는 키 일람.

| 키 | 생산자 | 소비자 | 형태 |
|---|---|---|---|
| `initial_collection` | Orchestrator | Planner | list[dict] |
| `plan` | Planner | Retriever | list[{"tool", "input", "rationale"}] |
| `retrieved` | Retriever | Planner (재계획), OntologyMapper | list[{"tool", "result"}] |
| `iteration` | ExplorationFlow | 라우팅 | int |
| `critic_decision` | Critic | 라우팅 | "sufficient" \| "needs_more" |
| `critic_feedback` | Critic | Planner (재계획) | str |
| `question_kind` | Analyzer | QARetriever | "factual" \| ... |
| `required_info` | Analyzer | (참고) | list[str] |
| `qa_evidence` | QARetriever | Synthesizer, Verifier | list[dict] |
| `answer_draft` | Synthesizer | Verifier | str |
| `citations` | Synthesizer | Verifier | list[str] |
| `verifier_decision` | Verifier | 라우팅 | "pass" \| "fail" |
| `verifier_feedback` | Verifier | Synthesizer (재시도) | str |
| `synth_attempt` | QAFlow | 라우팅 | int |

키는 `dict` 자유 형식으로 시작 — 안정화 후 typed 모델로 승격 ([D-14](DECISIONS.md#d-14)).

---

## 3. Mock / Stub / Placeholder 인벤토리

POC 에서 임시로 둔 부분과, Phase 4 에서 어떻게 교체할지를 한 표에 모음.

### 3.1 LLM

| 항목 | 현재 | 위치 | Phase 4 교체 |
|---|---|---|---|
| LLMClient | Stub / LangChain(OpenAI · Anthropic) — TracingLLMClient 데코레이터로 wrap | [core/shared/infra/llm_client.py](../core/shared/infra/llm_client.py), [langchain_llm_client.py](../core/shared/infra/langchain_llm_client.py), [tracing_llm_client.py](../core/shared/infra/tracing_llm_client.py) | runtime.yaml provider/model 변경. provider 추가 시 `_get_chat_model` 분기 |
| Prompt 관리 | **PromptCatalog (8 개 YAML)** ✅ | [core/llm/catalog.py](../core/llm/catalog.py), [core/llm/prompts/](../core/llm/prompts/) | (확장) Langfuse Prompt Management 동기화 또는 Anthropic caching 지원 |
| 응답 스키마 | YAML schema 필드에 정의 ✅ | [core/llm/prompts/*/*.yaml](../core/llm/prompts/) | structured output API (Anthropic tool_use 등) 활용 |
| Prompt 버전 추적 | sha256 version_hash 가 EvidenceStep 및 Langfuse 메타에 자동 기록 ✅ | [catalog.py](../core/llm/catalog.py) | — |
| 모델 단가 | yaml 외부화 ✅ | [core/llm/pricing.yaml](../core/llm/pricing.yaml), [pricing.py](../core/llm/pricing.py) | Anthropic prompt caching 단가 / batch 50% 할인 필드 추가 |
| 비용 추적 | PolicyGate 가 토큰 → USD 환산 누적 (TracingLLMClient 자동 호출) ✅ | [core/agents/policy.py](../core/agents/policy.py) | scope_id 별 영구 저장 + 일간/월간 집계 |

### 3.2 도구 (Tool)

**현재 도구 인벤토리**:

| 도구 | 종류 | 위치 | 상태 |
|---|---|---|---|
| `news_search_tool` | 배치용 | (배치 파이프라인 내부) | 동작 중 (Mock Provider) |
| `MockAddressInfoTool` | On-demand | [core/tools/mock_address_info_tool.py](../core/tools/mock_address_info_tool.py) | **목업** |

**도구 추가 위치 규칙** ([D-13](DECISIONS.md#d-13)):

| 도구 종류 | 위치 |
|---|---|
| 두 자산 이상에서 사용 가능 | `core/tools/` |
| 한 자산만 사용 | `projects/<자산>/tools/` |

**Phase 4 에 추가될 부동산 도구 (예정)**:

| 신규 도구 | 역할 | OntologyMapper 어댑터 작성 권장? |
|---|---|---|
| `vworld_tool` | 토지/건물 공적 정보 | (가) 권장 — 응답 스키마 안정 |
| `building_hub_tool` | 건축물대장 | (가) 권장 |
| `tenant_lookup_tool` | 입점 상가 정보 | (가) 권장 |
| `transaction_tool` | 실거래가 | (가) 권장 |
| `pdf_upload_tool` | 토지대장 PDF 등 | (다) — 비정형, LLM fallback |
| `web_search_tool` | 자율 추가 검색 | (다) — 비정형, LLM fallback |

도구 추가 절차는 [EXTENSION_GUIDE.md §4](EXTENSION_GUIDE.md#4-llm-tool-추가).

### 3.3 OntologyMapper 어댑터

| 어댑터 | 위치 | 상태 |
|---|---|---|
| `MockAddressAdapter` | [core/processors/ontology_mapper/adapters/mock_adapter.py](../core/processors/ontology_mapper/adapters/mock_adapter.py) | **목업** — vworld 어댑터로 교체 예정 |

**Phase 4 추가 어댑터 (예정)**:

| 어댑터 | 입력 source_type | 출력 노드/엣지 |
|---|---|---|
| `VworldAdapter` | `vworld` | Address, Land, LandUse, HAS_USE |
| `BuildingHubAdapter` | `building_register` | Building, Address, BUILT_ON |
| `TenantAdapter` | `tenant` | Address, Tenant, OPERATES_AT |
| `TransactionAdapter` | `transaction` | Address, Transaction, AT_PRICE |

어댑터 추가 절차는 [EXTENSION_GUIDE.md §5](EXTENSION_GUIDE.md#5-새-ontologymapper-어댑터-추가).

### 3.4 저장소 (Stores)

| 저장소 | 현재 구현 | 위치 | Phase 4 교체 |
|---|---|---|---|
| `RawStore` | InMemory | [core/collectors/news/repositories/in_memory/](../core/collectors/news/repositories/in_memory/) | PostgreSQL |
| `OntologyStore` | InMemory | 위와 동일 | PostgreSQL |
| `SignalStore` | InMemory | 위와 동일 | PostgreSQL + pgvector |
| `EmbeddingStore` | InMemory | 위와 동일 | PostgreSQL + pgvector |
| `GraphStore` | **InMemoryGraphStore** | [core/shared/stores/graph_store.py](../core/shared/stores/graph_store.py) | Neo4j |
| `ReportStore` | (사용 시 stub) | [core/shared/stores/report_store.py](../core/shared/stores/report_store.py) | 파일 시스템 또는 PostgreSQL |
| `DocumentStore` | (미사용) | [core/shared/stores/document_store.py](../core/shared/stores/document_store.py) | S3 또는 파일 시스템 (PDF 업로드) |

`composition.py` 의 `_NullReportStore`, `_NullSignalStore` 는 QARetriever 호출을 만족시키기 위한 임시 — 실제 ReportStore / SignalStore 구현체로 교체.

### 3.5 그래프 작성기

| 항목 | 현재 | 위치 | Phase 4 |
|---|---|---|---|
| `GraphWriter` (배치용) | `NoOpGraphWriter` | [core/shared/infra/graph_writer.py](../core/shared/infra/graph_writer.py) | Neo4jGraphWriter |
| `SignalJoiner` | **placeholder** (NotImplementedError) | [core/processors/graph_writers/signal_joiner.py](../core/processors/graph_writers/signal_joiner.py) | 자동 수집 그래프화 정책 구체화 후 ([D-15](DECISIONS.md#d-15)) |

### 3.6 외부 API Provider

| Provider | 현재 | 위치 | Phase 4 |
|---|---|---|---|
| Naver News | `MockNewsSearchProvider` (default) | [core/collectors/news/](../core/collectors/news/) | NaverNewsSearchProvider 실제 호출 (이미 구현됨, env var 만 필요) |
| vworld | (없음) | — | `core/collectors/transaction/` 또는 `core/tools/` 에 추가 |
| 건축허브 | (없음) | — | 위와 동일 |

### 3.7 Observability

LLM 호출 / 에이전트 흐름을 외부 백엔드에 송신하여 토큰·비용·라이프사이클을 추적한다.

| 항목 | 현재 | 위치 | 비고 |
|---|---|---|---|
| TraceBackend ABC | 구현 완료 ✅ | [core/shared/infra/observability/base.py](../core/shared/infra/observability/base.py) | trace_scope() contextmanager, contextvars 기반 |
| NoOpBackend | 구현 완료 ✅ — 기본값 | [noop_backend.py](../core/shared/infra/observability/noop_backend.py) | 외부 호출 0 (CI/테스트/추적 불필요) |
| StdoutBackend | 구현 완료 ✅ | [stdout_backend.py](../core/shared/infra/observability/stdout_backend.py) | JSON line 로깅 (로컬 디버깅) |
| LangfuseBackend | 구현 완료 ✅ | [langfuse_backend.py](../core/shared/infra/observability/langfuse_backend.py) | Langfuse Cloud free 50k events/월. 키 부재 시 자동 disabled |
| TracingLLMClient | 구현 완료 ✅ | [tracing_llm_client.py](../core/shared/infra/tracing_llm_client.py) | LLMClient 데코레이터. PolicyGate auto-record 지원 |
| 배치 파이프라인 trace | **미구현** | — | Airflow DAG task 가 trace_scope 열어야 함. on-demand 만 wrap 됨 |
| LLM cache | **미구현** | — | 결정적 호출 (ontology tagging 등) 같은 입력 → 캐시 hit |
| Prompt caching (Anthropic) | **미구현** | — | system prompt 가 길어서 효과 큼. `cache_control` 마킹 추가 시 90% 입력 토큰 비용 절감 가능 |

**설정 (config/runtime.yaml + .env)**:
```yaml
observability:
  backend: noop          # noop | stdout | langfuse
```
또는 env override: `FNPRICING_OBSERVABILITY_BACKEND=langfuse` + `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`.

**Why Langfuse**: Cloud free tier 50k events/월 (Phoenix 는 셀프호스팅 강제), LangChain/LangGraph callback 통합 매끄러움, PromptCatalog 와 시너지 (prompt management first-class), OTEL export 호환 — 미래 Phoenix 전환 시 데이터 손실 없음. 결정 자체는 TraceBackend ABC 뒤에 숨겨 영구 아님 ([D-17](DECISIONS.md#d-17)).

### 3.8 자동 수집 그래프화

| 항목 | 현재 | Phase 4 |
|---|---|---|
| 자동 수집 신호 → 그래프 적재 | 미구현 (배치는 signal_store 까지만) | 옵션 A 의 어휘 합의 후 GraphPatternBuilder 로 자동 수집 신호도 그래프화 ([D-10](DECISIONS.md#d-10)) |
| 자동 수집 ↔ 온디멘드 그래프 연결 | 어휘 공유로 자동 (구현 시) | 동일 — 추가 컴포넌트 불필요 |

---

## 4. 도구 호출 흐름 (배치 vs 에이전트)

같은 도구가 두 경로로 호출될 수 있다. 실패 격리·비용 통제·evidence 기록은 경로별로 다르다.

### 4.1 배치 흐름

```
Airflow DAG → Application Service (예: NewsSearchApplicationService)
            → Provider/Repository (실제 외부 API)
            → 저장소 적재
```

- 도구 자체가 호출되지는 않음 — Application Service 가 직접 Provider 호출
- 실패 격리: 단일 레코드 실패는 DAG 전체 실패로 이어지지 않음 ([ARCHITECTURE.md §8](ARCHITECTURE.md#8-에러-처리-원칙))

### 4.2 에이전트 흐름 (On-demand)

```
ExplorationFlow.Retriever → BaseTool.run(**input) → Application Service → Provider
                          ↑
                   PolicyGate.check 통과 시
                   ↓
                   PolicyGate.record + EvidenceStep 누적
```

- 각 호출 전 PolicyGate (max_tool_calls, max_cost_usd, allowed_tools)
- 차단된 호출도 EvidenceStep 으로 남음

**같은 도구가 양쪽에서 동작하도록** — 도구는 비즈니스 로직 직접 보유 금지, Application Service 호출만 ([ARCHITECTURE.md §6](ARCHITECTURE.md#6-llm-tool-실행-맥락)).

---

## 5. 교체 우선순위 (Phase 4 작업 순서 제안)

### 5.1 1차 — 실제 LLM 연동 (대부분 완료, 잔여만)

기본 LLM/스키마/비용추적/observability 는 완료. 잔여:

- [x] runtime.yaml provider/model 설정 (현재 anthropic / claude-haiku-4-5-20251001)
- [x] 각 서브 에이전트의 응답 JSON Schema 정의 (PromptCatalog YAML 의 `schema` 필드)
- [x] PolicyGate 의 비용 추적을 토큰 기반으로 (TracingLLMClient auto-record)
- [x] Anthropic 지원 (langchain-anthropic, `[anthropic]` extras)
- [ ] Langfuse 키 발급 + 운영 환경에서 실제 trace 확인
- [ ] golden eval — 알려진 주소/뉴스로 prompt 변경 시 회귀 추적

### 5.2 2차 — 첫 번째 실제 도구 (vworld)

이유: end-to-end 흐름의 모든 단계가 실제 데이터로 검증됨. 어댑터 패턴 첫 적용.

작업:
1. `core/tools/vworld_tool.py` (BaseTool 구현, 실제 API 호출)
2. `core/processors/ontology_mapper/adapters/vworld_adapter.py`
3. `composition.py` 의 도구 레지스트리 + OntologyMapper registry 등록
4. `MockAddressInfoTool` 와 병행 운영 (env var 로 선택)
5. 어휘 사전 (`core/shared/domain/ontology_schema.py`) 에 LandUse 표준 코드 추가

### 5.3 3차 — 추가 도구 + 어댑터

`building_hub_tool`, `tenant_lookup_tool`, `transaction_tool` 차례로 추가. 패턴은 vworld 와 동일.

### 5.4 4차 — 비정형 입력 도구 (LLM fallback 검증)

`pdf_upload_tool`, `web_search_tool` 추가. 어댑터 작성하지 않고 LLMFallbackMapper 만으로 동작 확인. 어휘 사전이 충분히 채워져 있어야 매핑 품질 확보.

### 5.5 5차 — 영구 그래프 + Real Stores

작업:
1. `Neo4jGraphStore` 구현 (GraphStore ABC)
2. PostgreSQL 기반 SignalStore / RawStore / OntologyStore 구현
3. scope_id 정책 결정 — `asset_<id>` / `region_<code>` 중 어느 단위
4. 지리/행정동 인접 자산 그룹화 룰 ([D-03](DECISIONS.md#d-03))

### 5.6 6차 — 자동 수집 그래프화 (옵션 A)

작업:
1. 어휘 합의 — LandUse / EvaluationFactor / Region 표준 코드
2. 배치의 GraphSignalService 가 GraphPatternBuilder 호출하도록 변경
3. 자동 수집 그래프와 온디멘드 그래프의 scope 분리 정책 (`scope_id="global"` 등)
4. SignalJoiner 의 필요성 재평가 — 대부분 어휘 공유로 해결되면 폐기

---

## 6. 빠른 참조

### 6.1 새 세션 시작 시 확인할 곳

1. [README.md](../README.md) — 전체 안내
2. [ARCHITECTURE.md](ARCHITECTURE.md) — 시스템 구조
3. **본 문서** — 현재 무엇이 동작하고 무엇이 임시인지
4. [DECISIONS.md](DECISIONS.md) — 왜 그렇게 결정됐는지

### 6.2 자주 묻는 질문

**Q. CLI 동작 여부 확인은?**
```
python -m pytest tests/                                          # 93 tests
python -m interfaces.cli analyze-address "강남구 역삼동 123-45"
```

**Q. Stub LLM 이 빈 응답을 주는데 어떻게 흐름이 끝까지 가는가?**
각 서브 에이전트 (`Planner`, `Critic`, `Verifier` 등) 가 빈 응답에 대해 안전 기본값을 갖는다. 예: Critic 의 default 는 `"sufficient"`, Verifier 의 default 는 `"pass"`. 따라서 1 회 반복 후 종료.

**Q. 새 도구를 추가하면 무엇을 변경해야 하는가?**
1. `core/tools/<name>.py` (BaseTool)
2. (선택) `core/processors/ontology_mapper/adapters/<name>_adapter.py`
3. `interfaces/composition.py` 의 도구 / 어댑터 레지스트리
4. `AssetProfile.allowed_tools` (현재는 미사용 — Phase 4에 활성화)

상세 절차: [EXTENSION_GUIDE.md](EXTENSION_GUIDE.md).

**Q. composition.py 의 `_NullReportStore` / `_NullSignalStore` 는 왜?**
QARetriever 가 ReportStore / SignalStore 를 인자로 받지만 POC 에서는 그래프만 검색해도 충분. 임시로 빈 stub 을 주입. Phase 4 에서 실제 구현체로 교체.

**Q. 자동 수집 데이터를 어떻게 온디멘드 분석에 반영하는가?**
현재 미연동. Phase 4 의 6차 작업에서 옵션 A 로 구현 — 같은 어휘를 쓰면 그래프 traversal 으로 자동 연결. SignalJoiner 같은 별도 컴포넌트는 불필요할 가능성 큼 ([D-15](DECISIONS.md#d-15)).

---

## 6.5 확장 자리 — 의도적으로 비어있는 인터페이스 ([D-18](DECISIONS.md#d-18))

"실제 구현은 추후, 인터페이스만 미리" 원칙으로 열어둔 자리들. 추후 구현체 추가 시 호출 측 변경 0.

### 6.5.1 평가 축 (STO 자산 평가)

| ABC | 위치 | 현재 placeholder | 활성화 시점 |
|---|---|---|---|
| `EvaluationOrchestrator` | [core/agents/evaluation_orchestrator.py](../core/agents/evaluation_orchestrator.py) | `DefaultEvaluationOrchestrator` (3 strategy 호출 + stub score 반환), `NoOp` | ScoreBuilder 실제 구현 시 자동 활성화 |
| `ScoreBuilder` | [core/evaluation/scoring/base.py](../core/evaluation/scoring/base.py) | `StubScoreBuilder` (score=0.0) | 점수 산출 룰 (가중치) 도메인 의사결정 후 |
| `IdentifierExtractor` | [core/agents/identifier_extractor.py](../core/agents/identifier_extractor.py) | `NoOpIdentifierExtractor`, `RegistryBased` (빈 registry) | 도구 확장 (주소 외 입력) 단계 |

### 6.5.2 영구 저장 (대시보드 raw 자료)

| ABC | 위치 | 현재 placeholder | 활성화 시점 |
|---|---|---|---|
| `AnalysisRunStore` | [core/shared/stores/analysis_run_store.py](../core/shared/stores/analysis_run_store.py) | `InMemoryAnalysisRunStore` | `SqliteAnalysisRunStore` 추가 시 |
| `EvaluationClaimStore` | [core/shared/stores/evaluation_claim_store.py](../core/shared/stores/evaluation_claim_store.py) | `InMemoryEvaluationClaimStore` | 동일 |
| `LLMCallRecorder` | [core/shared/infra/observability/recorders.py](../core/shared/infra/observability/recorders.py) | `NoOpLLMCallRecorder`, `InMemoryLLMCallRecorder` | `SqliteLLMCallRecorder` 추가 + `TracingLLMClient` wire-up |
| `UsageMetricsCollector` | (위 동일) | `NoOpUsageMetricsCollector`, `InMemoryUsageMetricsCollector` | `Orchestrator.analyze()` 종료 시 PolicyGate snapshot 적재 |
| `DashboardExporter` | [core/shared/infra/dashboard_exporter.py](../core/shared/infra/dashboard_exporter.py) | `NoOpDashboardExporter` | 영구 저장소가 채워진 후 |

### 6.5.3 환경/시크릿

| ABC | 위치 | 현재 placeholder | 활성화 시점 |
|---|---|---|---|
| `SecretProvider` | [core/shared/config/secrets.py](../core/shared/config/secrets.py) | `EnvSecretProvider`, `ChainSecretProvider`, `StaticSecretProvider` | Airflow / Vault / AWS 추가 시 새 provider 한 클래스 |

### 6.5.4 DB 스키마 (CREATE TABLE 만, write 미연결)

`python -m interfaces.cli init-db` 가 다음 테이블도 생성:
- `analysis_runs` — on-demand 분석 1회 메타 + 누적 metric
- `evaluation_claims` — 3축 평가 결과
- `llm_calls` — LLM 호출 단위 metric (토큰/비용/지연/prompt 버전)
- `agent_evidence_steps` — evidence trace 영구화

`db_schema.py` 의 SQL 은 인덱스까지 정의되어 있어, Sqlite*Store 추가 시 INSERT/SELECT 만 작성하면 즉시 사용 가능.

---

## 7. 관련 문서

- [ARCHITECTURE.md](ARCHITECTURE.md) — 전체 시스템 구조
- [RUNTIME_BEHAVIOR.md](RUNTIME_BEHAVIOR.md) — CLI 입출력 실측치 + 모드 매트릭스
- [AGENT_DESIGN.md](AGENT_DESIGN.md) — 에이전트 / Flow 상세
- [ONTOLOGY.md](ONTOLOGY.md) — 매핑 정책
- [CODE_STRUCTURE.md](CODE_STRUCTURE.md) — 디렉토리 + 추상화
- [DECISIONS.md](DECISIONS.md) — 결정 이력 + 트레이드오프
- [EXTENSION_GUIDE.md](EXTENSION_GUIDE.md) — 확장 절차
- [POC_PLAN.md](POC_PLAN.md) — 단계별 목표
