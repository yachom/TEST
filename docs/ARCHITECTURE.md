# 아키텍처

## 1. 시스템 개요

본 시스템은 두 개의 실행 흐름이 공유 저장소(signal_store + GraphStore) 를 매개로 연결되는 구조다. **두 흐름 모두 본 저장소에서 다룬다** ([D-02](DECISIONS.md#d-02)).

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   배치 파이프라인 (Airflow)              On-demand 주소 분석         │
│   ─────────────────────────              ─────────────────────       │
│                                                                      │
│   외부 데이터 수집                        주소 입력                  │
│        │                                       │                    │
│        ▼                                       ▼                    │
│   raw_store                              [Orchestrator]              │
│        │                                       │                    │
│        ▼                                       ▼                    │
│   LLM 온톨로지 태깅                       ① InitialCollector        │
│        │                                  (vworld, 건축허브, 상가)   │
│        ▼                                       │                    │
│   signal_store ◄─────── 어휘 공유 ──────►      ▼                    │
│   (Market & Policy)                       ② ExplorationFlow         │
│        │                                  (멀티 에이전트, 자율)      │
│        ▼                                       │                    │
│   GraphStore                                   ▼                    │
│   (자산 무관 신호 그래프)                  ③ OntologyMapper          │
│                                          (어댑터 + LLM fallback)     │
│                                                │                    │
│                                                ▼                    │
│                                          GraphStore                 │
│                                          (scope_id 별 격리)          │
│                                                │                    │
│                                                ▼                    │
│                                          ⑤ ReportBuilder            │
│                                                │                    │
│                                                ▼                    │
│                                          ⑥ QAFlow                   │
│                                          (멀티 에이전트, 자율)       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

두 흐름의 연결 지점:
- `signal_store` — 배치 적재, On-demand 가 query_applicable 로 조회
- `GraphStore` — 같은 온톨로지 어휘를 공유하여 traversal 으로 자동 연결 ([ONTOLOGY.md §5.3](ONTOLOGY.md#53-자동-수집-그래프--온디멘드-분석-그래프-연결))

자율 에이전트는 ② ExplorationFlow 와 ⑥ QAFlow 두 곳에만 존재한다 ([AGENT_DESIGN.md](AGENT_DESIGN.md)). 나머지는 결정적 코드 또는 단발 LLM 호출.

---

## 2. 배치 파이프라인 흐름

자산별로 정의된 `AssetProfile`을 기반으로, 등록된 데이터 소스에서 외부 신호를 수집하여 Signal Graph를 구축한다.

```
┌─────────────────┐
│ load_config     │  자산 프로파일 로드 + 활성 그룹 확인
└────────┬────────┘
         ▼
┌─────────────────┐
│ build_plan      │  CollectionPlan 생성 + 호출량 산정
└────────┬────────┘
         ▼
┌─────────────────┐
│ check_quota     │  API 호출 한도 확인
└────────┬────────┘
         ▼
┌─────────────────┐
│ collect_and_save│  Collector → 정규화 → raw_store 저장
└────────┬────────┘
         ▼
┌─────────────────┐
│ rule_filter     │  룰 기반 1차 필터링
└────────┬────────┘
         ▼
┌─────────────────┐
│ embed           │  텍스트 임베딩
└────────┬────────┘
         ▼
┌─────────────────┐
│ semantic_dedup  │  의미 중복 제거 (LLM 비용 절감)
└────────┬────────┘
         ▼
┌─────────────────┐
│ ontology_tag    │  LLM 온톨로지 태깅
└────────┬────────┘
         ▼
┌─────────────────┐
│ build_signals   │  Graph 적재 대상 생성
└────────┬────────┘
         ▼
┌─────────────────┐
│ save_summary    │  실행 요약 기록
└─────────────────┘
```

각 Task는 idempotent하게 설계된다. 재실행해도 중복 처리되지 않는다.

---

## 3. 처리 상태 흐름

각 수집 레코드는 6단계의 상태를 거친다.

```
수집됨 (NEW)
   │
   ├── URL 중복? ──→ url_duplicate    (저장 후 처리 skip)
   ├── 해시 중복? ──→ hash_duplicate
   └── 신규 ──→ new
                 │
                 ▼
            룰 필터링
            ├── 통과 ──→ passed
            └── 제외 ──→ excluded + 제외 이유
                            │
                            ▼ (passed만)
                        임베딩 생성
                        └── done / failed
                                │
                                ▼
                        의미 중복 판단
                        ├── 신규 ──→ novel
                        └── 중복 ──→ duplicate + 기준 레코드 ID
                                        │
                                        ▼ (novel만)
                                LLM 온톨로지 태깅
                                └── done / failed / excluded
                                            │
                                            ▼
                                Graph 적재 대상 판단
                                └── queued / excluded
```

상태 Enum 6종은 `core/shared/domain/states.py`에 정의된다.

---

## 4. On-demand 주소 분석 흐름

본 저장소가 다루는 두 번째 핵심 흐름. 결정적 Orchestrator 가 단계를 관리하며, 자율 판단이 필요한 두 지점은 멀티 에이전트 Flow 로 위임한다.

### 4.1 단계 개요

```
[CLI / API: 주소 입력]
        │
        ▼
[Orchestrator]                   ← scope_id 발급 (analysis_<uuid>)
   ├─ ① InitialCollector         ← 결정적
   │      vworld_tool / building_hub_tool / tenant_tool
   ├─ ② ExplorationFlow          ← 자율 (LLM)
   │      Planner → Retriever → Critic 루프
   ├─ ③ OntologyMapper           ← 어댑터 + LLM fallback
   │      RawRecord → GraphNode/Relation
   ├─ ④ SignalJoiner (placeholder, POC 보류)
   ├─ ⑤ ReportBuilder            ← 단발 LLM
   │      Subgraph → 보고서
   └─ ⑥ QAFlow 인스턴스 반환
          Analyzer → Retriever → Synthesizer → Verifier 루프
```

### 4.2 단계별 책임

| 단계 | 입력 | 출력 | 자율성 |
|---|---|---|---|
| ① InitialCollector | 주소 | RawRecord 목록 | 결정적 |
| ② ExplorationFlow | 1차 결과 | 추가 RawRecord | 자율 (LLM) |
| ③ OntologyMapper | RawRecord 전체 | GraphNode/Relation | 입력별 어댑터 또는 LLM fallback |
| ④ SignalJoiner | (POC 보류) | - | - |
| ⑤ ReportBuilder | Subgraph | 보고서 | 단발 LLM |
| ⑥ QAFlow | 사용자 질문 | 답변 | 자율 (LLM) |

### 4.3 자율 에이전트 두 곳 — Flow 구조

상세는 [AGENT_DESIGN.md](AGENT_DESIGN.md) 참조. 핵심만:

- **ExplorationFlow**: Planner(추가 수집 계획) → Retriever(도구 호출) → Critic(충분성 판정) 루프. 종료: Critic 충분 / 최대 3 회 / PolicyGate 한도 도달.
- **QAFlow**: Analyzer(질문 분류) → Retriever(검색) → Synthesizer(답변 합성) → Verifier(근거 검증) 루프. 종료: Verifier 통과.
- 두 Flow 모두 **Agent ABC** 를 구현 ([D-06](DECISIONS.md#d-06)). 외부에서 보면 `flow.run(ctx)` 한 줄.
- 라우팅은 LangGraph StateGraph ([D-07](DECISIONS.md#d-07)).

### 4.4 PolicyGate (자율성 통제)

자율 에이전트가 무한정 도구를 호출하지 못하도록 PolicyGate 가 게이트. AssetProfile 이 `allowed_tools` 와 한도를 주입한다. 상세 [AGENT_DESIGN.md §5](AGENT_DESIGN.md#5-policygate-하이브리드-자율성-통제).

### 4.5 evidence trace

Flow 가 거친 모든 단계는 EvidenceStep 으로 누적. 보고서의 근거 체인 / QA 답변의 근거 / 디버깅 / 비용 추적에 사용.

---

## 5. 두 흐름의 연결 지점

| 저장소 | 배치 흐름 | On-demand 흐름 |
|---|---|---|
| `raw_store` | 외부 신호 원본 저장 | 1차 / 추가 수집 원본 저장 |
| `ontology_store` | LLM 태깅 결과 저장 | 1차 매핑 결과 저장 |
| `signal_store` | **upsert** (Market & Policy Signal) | **query** (적용 가능 신호 조회) |
| `GraphStore` (신규) | 자산 무관 신호 그래프 (자동 수집 그래프화는 POC 보류) | 분석 단위 그래프 (휘발) |
| `document_store` | 사용 안 함 | 사용자 업로드 PDF 저장 |
| `report_store` | 사용 안 함 | 최종 보고서 저장 |

연결 지점은 두 종류:
1. `signal_store.query_applicable(asset_class, region_code)` — 단순 매칭 기반
2. `GraphStore` 의 **공유 노드를 통한 traversal** — 같은 LandUse / EvaluationFactor 등 어휘를 양 흐름이 공유 ([D-10](DECISIONS.md#d-10), [ONTOLOGY.md](ONTOLOGY.md))

### 5.1 GraphStore scope_id 격리

같은 GraphStore 안에서 분석 단위를 격리하기 위해 모든 read/write 메서드가 `scope_id` 인자를 받는다.

| 모드 | scope_id 의미 | 정리 |
|---|---|---|
| 휘발 (POC) | `analysis_<uuid>` (분석 세션) | 종료 시 `drop_scope` |
| 영구 (향후) | `asset_<id>`, `region_<code>` 등 | drop_scope 호출 안 함 |

POC 는 휘발(InMemoryGraphStore). 영구는 지리/행정동 그룹화 룰 검증 후 검토 ([D-03](DECISIONS.md#d-03)).

---

## 6. LLM Tool 실행 맥락

LLM 이 호출하는 Tool 은 두 종류 사용처가 있다.

```
[배치 / 외부 LLM Agent]            [On-demand ExplorationFlow]
        │                                  │
        ▼                                  ▼
   LLM Tool (얇은 어댑터)             PolicyGate 검사
        │                                  │
        ▼                                  ▼
Application Service                   LLM Tool 실행
(배치와 동일)                              │
        │                                  ▼
        ▼                              결과 + EvidenceStep 기록
Provider / Repository
```

Tool 의 공통 원칙:
- 비즈니스 로직 직접 보유 금지 — Application Service 호출만
- 카테고리별 Tool (`news_search_tool`, `streaming_tool`, `transaction_tool` 등). 자산은 파라미터로 ([D-13](DECISIONS.md#d-13))
- 자산 특화 Tool 은 드물게 `projects/<자산>/tools/`

ExplorationFlow / QAFlow 에서 Tool 을 호출할 때는 PolicyGate 가 호출 전 검사하고 evidence trace 가 기록된다.

---

## 7. 평가 3축의 분리

```
┌───────────────────────────────────────────────────────┐
│              EvaluationStrategy (ABC)                 │
└───────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌──────────────────┐
│Quantitative │  │ Structural  │  │    Sentiment     │
│ (목업)      │  │  (목업)     │  │   (본 구현)      │
│ DCF/NOI/    │  │ 토큰구조/   │  │  온톨로지 기반    │
│ Cap Rate    │  │ 신탁구조    │  │  신호→점수+claim │
└─────────────┘  └─────────────┘  └──────────────────┘
                                          │
                                  ┌───────┴────────┐
                                  ▼                ▼
                          SentimentTarget    SentimentTarget
                          (Building, Tenant, Artist, Song, ...)
```

각 자산은 자신에게 적용할 평가축과 평가 대상을 `AssetProfile`에 명시한다.

---

## 8. Observability

LLM 호출 / 에이전트 흐름은 `TraceBackend` 추상화 뒤에서 외부 백엔드(Langfuse 등) 로 송신된다. 1 차 백엔드는 Langfuse — Cloud free tier 50k events/월 ([D-17](DECISIONS.md#d-17)).

```
[Orchestrator.analyze(address)]
    │
    ├─ scope_id = "analysis_<uuid>"
    │
    ▼  trace_scope(backend, "address_analysis", trace_id=scope_id)
┌──────────────────────────────────────────────────────────┐
│  contextvars: current_trace = TraceContext               │
│                                                          │
│  Planner.run()   →  TracingLLMClient.call(req)           │
│                       │                                  │
│                       ├─ backend.start_generation(...)   │
│                       ├─ inner.call(req)                 │
│                       ├─ backend.end_generation(usage)   │
│                       └─ policy_gate.record(usage,model) │
│                                                          │
│  Critic.run()   → (동일)                                 │
│  ... (모든 sub-agent 의 LLM 호출이 자동으로 같은 trace)  │
└──────────────────────────────────────────────────────────┘
    │
    ▼  block 종료 → backend.end_trace() + flush
```

핵심 원리:
- **호출 지점 코드 변경 0** — Planner, Tagger 등은 `LLMClient` ABC 만 의존. `TracingLLMClient` 는 데코레이터 패턴.
- **contextvars 전파** — Orchestrator 가 한 군데서만 `trace_scope()` 열면 LangGraph StateGraph 내부의 모든 LLM 호출이 동일 thread context 에서 자동 첨부.
- **PolicyGate 자동 record** — TracingLLMClient 가 호출 종료 시 `policy_gate.record(usage=resp.usage, model=resp.model)` 자동 호출. 서브 에이전트들이 명시적으로 안 부름.
- **백엔드 결정 영구 아님** — TraceBackend ABC 뒤에 NoOp / Stdout / Langfuse 구현체. 추후 Phoenix / OTEL 추가 시 ABC 만 구현하면 됨.

evidence trace 와의 차이:
- **EvidenceStep** — 도메인 사용자가 보는 보고서 근거 체인 (사람-읽기용, 보고서/QA 첨부)
- **TraceBackend** — 개발자가 보는 시스템 동작 추적 (Langfuse 대시보드, 토큰/비용/지연시간)

두 추적은 분리되어 있지만 prompt version_hash 같은 공통 메타가 양쪽 모두에 기록되어 cross-reference 가능.

설정: `config/runtime.yaml` 의 `observability.backend` (`noop` / `stdout` / `langfuse`) + env override `FNPRICING_OBSERVABILITY_BACKEND`. Langfuse 키는 `.env`.

## 9. 에러 처리 원칙

- 단일 레코드 처리 실패는 격리한다. 한 뉴스의 실패가 DAG 전체 실패로 이어지지 않는다.
- 시스템 수준 오류(API 인증 실패, 모든 Key 소진, DB 연결 실패)는 DAG 실패로 처리한다.
- 모든 처리 단계는 idempotent하다. 재실행해도 중복 저장이나 중복 처리가 발생하지 않는다.

상세 에러 분류는 `core/shared/domain/errors.py` 참조.
