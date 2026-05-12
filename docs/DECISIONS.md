# 의사결정 기록

본 문서는 본 시스템의 주요 설계 결정과 그 **이유 / 트레이드오프 / 대안** 을 기록한다.
`.md` 다른 문서들은 *현재 상태* 를 기술하지만, 본 문서는 *왜 이 상태인가* 를 기술한다.

새 합류자 / 새 세션은 본 문서를 통해 "이전에 어떤 옵션이 검토되고 왜 기각/채택되었는지" 를 알 수 있다. 같은 논의를 반복하지 않기 위함.

각 결정은 시간순이 아니라 주제별로 묶인다. 결정의 시점은 항목별로 기재한다.

---

## D-01: core/ + projects/<자산>/ 구조

**시점**: 초기 설계
**상태**: 채택

**결정**: 자산 무관 공통 코드는 `core/` 에, 자산 특화 코드는 `projects/<자산>/` 에 둔다.

**이유**:
- 자산이 늘어나도 `core/` 가 그대로 재사용
- 자산 = 한 디렉토리 = 한 곳에서 전체 평가 코드 파악 (비개발자 가독성)

**대안 (기각)**:
- 자산을 코드 전체에 분산 — 자산 추가 시 변경 범위 큼
- 자산을 패키지로 격리하지 않음 — 자산 간 결합이 우연히 생김

**자산 간 의존 금지**: `projects/A/` 가 `projects/B/` 를 import 하면 격리가 깨진다. 공유 필요 시 `core/` 로 승격.

---

## D-02: On-demand 흐름을 본 레포에서 함께 다룸

**시점**: 2026-05-10
**상태**: 채택 (이전 결정 변경)

**결정**: 배치 흐름과 On-demand 주소 분석 흐름을 모두 본 저장소에서 다룬다.

**이전 결정**: On-demand 는 별도 프로젝트로 분리 (배치 저장소는 signal_store 까지만).

**변경 이유**:
- 두 흐름이 **같은 온톨로지 어휘 / 같은 그래프 DB / 같은 LLM 추상화** 를 공유 — 분리 시 중복 발생
- On-demand 의 OntologyMapper 가 배치의 sentiment_tagger 를 그대로 재사용 가능

**트레이드오프**:
- 저장소가 커짐 (배치 + 에이전트 + 보고서 모두 포함)
- 배치 중심 → 양 흐름 균형으로 설계 재정렬 필요

---

## D-03: 그래프 DB 휘발 정책 (POC) + 영구 확장 가능 ABC

**시점**: 2026-05-10
**상태**: 채택

**결정**: POC 는 InMemoryGraphStore 휘발. 인터페이스(GraphStore ABC)는 영구를 가정한 설계 — 모든 메서드가 `scope_id` 를 받는다.

**이유**:
- POC 에서 영구 저장소(Neo4j 등) 운영 부담 회피
- 영구가 진짜 의미를 가지려면 지리/행정동 기반 인접 자산 그룹화 룰이 선행되어야 함 — POC 범위 아님
- 인터페이스를 영구 가정으로 두면 구현체만 교체해서 확장 가능

**scope_id 의미**:
- 휘발: `analysis_<uuid>` (분석 세션, 종료 시 drop_scope)
- 영구: `asset_<id>` 또는 `region_<code>`

**대안 (기각)**:
- 휘발만 가정한 인터페이스 (scope_id 없음) — 영구 전환 시 인터페이스 변경 필요, 다운스트림 영향 큼
- 영구만으로 시작 — 그룹화 룰 검증이 선행돼야 하는데 POC 범위 초과

---

## D-04: 에이전트 자율성 — 옵션 3 하이브리드

**시점**: 2026-05-10
**상태**: 채택

**결정**: LLM 이 도구 + rationale 제안 → PolicyGate 검사 → 통과 시 실행 → evidence trace 기록.

**대안**:
- **옵션 1 (휴리스틱 룰)**: "소유주 N 명 이상 → 토지대장 추가" 같은 룰. 디버깅 쉬움, 유연성 낮음.
- **옵션 2 (LLM 자율)**: LLM 이 도구 목록 보고 자유 판단. 유연하지만 비결정적, 비용/루프 통제 어려움.
- **옵션 3 (하이브리드, 채택)**: LLM 추천 + 정책 게이트. 비결정성을 정책 레이어로 가둠.

**구현**: `core/agents/policy.py` 의 `AgentPolicy` (max_tool_calls, max_cost_usd, allowed_tools, require_rationale) + `PolicyGate.check()`.

**자산별 정책 차별화**: AssetProfile 이 allowed_tools 목록을 들고 PolicyGate 에 주입.

---

## D-05: 멀티 에이전트 Flow 구조

**시점**: 2026-05-10
**상태**: 채택

**결정**: 자율 에이전트는 단일이 아니라 Flow (서브 에이전트 그래프).

- ExplorationFlow = Planner + Retriever + Critic + 확장 자리
- QAFlow = Analyzer + Retriever + Synthesizer + Verifier + 확장 자리

**이유**:
- 단일 에이전트는 확장이 막힘 — Flow 는 서브 에이전트 추가가 한 디렉토리 안에서 끝남
- 사용자가 Plan-Execute-Reflect, 멀티 에이전트 QA 등 복잡한 흐름을 구상 중 — 그 자리 미리 확보

**대안 (기각)**:
- 단일 ExplorerAgent / QAAgent — 확장 시 코드 비대, 혹은 통째 갈아엎기 발생
- 모든 단계를 Flow 로 — Orchestrator 까지 자율화하면 비결정성 통제 어려움. 자율은 두 곳만.

---

## D-06: Flow 도 Agent ABC 를 구현

**시점**: 2026-05-10
**상태**: 채택

**결정**: ExplorationFlow / QAFlow 자체가 `Agent` ABC 를 구현. 외부에서 보면 `flow.run(ctx)` 한 줄.

**이유**:
- 통일된 진입점 — Orchestrator 는 Flow 든 단일 Agent 든 같은 방식으로 호출
- 재귀적 Flow — Flow 안에 Flow 가능 (예: PlannerFlow 안에 hypothesizer + ranker)
- 테스트 용이 — Mock Agent 로 Flow 통째 대체

**대안 (기각)**:
- Flow 와 Agent 별도 추상화 — 인터페이스 두 종류 관리, "Flow 안의 Flow" 어색

---

## D-07: LangGraph 기반 라우팅

**시점**: 2026-05-10
**상태**: 채택

**결정**: Flow 의 분기/루프/조건부 종료를 LangGraph StateGraph 로 표현.

**이유**:
- 기존 `core/shared/infra/langchain_llm_client.py` 가 이미 LangGraph 사용 — 의존성 추가 없음
- Critic 루프 같은 조건부 분기를 `add_conditional_edges` 한 줄로
- 그래프 시각화 가능
- 상태 전달 일관 (StateGraph)

**대안 (기각)**:
- 직접 순차 호출 (while + 분기문) — 단순하지만 분기·루프 표현 비대
- 다른 워크플로 라이브러리 (Prefect, Temporal 등) — 본 시스템 규모에 과도

---

## D-08: 모든 서브 에이전트는 LLM 호출

**시점**: 2026-05-10
**상태**: 채택 (POC 범위)

**결정**: POC 에서는 Planner / Retriever / Critic / Analyzer / Synthesizer / Verifier 모두 LLM 호출 기반.

**이유**:
- 결정적 로직(Retriever 의 도구 선택, Verifier 의 검증 등)을 휴리스틱으로 짜려면 사전 설계가 필요한데 POC 단계에서 미정
- 일단 LLM 으로 만들고 동작 패턴 보고 결정적 변환 검토

**추후 변경 가능**: Verifier / Retriever 일부는 LLM 호출 없이 결정적 코드로 전환 가능 (비용/속도 개선).

**Retriever 의 의미**: "도구 선택은 LLM, 도구 실행은 코드". LLM 이 파이썬 함수 직접 실행하는 게 아님.

---

## D-09: 매핑 정책 — (가) 직접 + (다) LLM Fallback 결합

**시점**: 2026-05-10
**상태**: 채택

**결정**: OntologyMapper 가 어댑터 레지스트리를 갖고, 어댑터 등록된 입력은 (가) 직접 매핑, 미등록 입력은 (다) 텍스트 평탄화 + LLM.

**대안 비교**:
- **(가) 만**: 모든 도구에 어댑터 작성 필요. 비정형 입력(웹검색 결과) 처리 불가.
- **(나) 별도**: 배치/On-demand 매퍼 분리. 코드 중복.
- **(다) 만**: 모든 입력 LLM 처리. 정밀도 손실 (47 → "약 50명").
- **(가)+(다) 혼용 (채택)**: 구조화 입력은 (가) 로 정밀 보존, 비정형은 (다) 로 흡수.

**구현**: `core/processors/ontology_mapper/` 의 OntologyMapper + adapters/ + llm_fallback.py.

---

## D-10: 자동 수집 ↔ 온디멘드 연결 — 옵션 A 방향 (POC 보류)

**시점**: 2026-05-10
**상태**: 방향 채택, 구체 구현 보류

**결정**: 자동 수집 신호도 같은 온톨로지 어휘로 그래프화 (옵션 A). 공유 노드(LandUse, EvaluationFactor 등)를 통해 traversal 로 자동 연결.

**대안**:
- **옵션 A (즉시 그래프화, 채택)**: 신호끼리 관계 추적 가능, 어휘 공유로 자동 연결, 온톨로지 본질 부합
- **옵션 B (수집만 + RAG)**: 단순, 그러나 신호 간 관계 추적 약함

**보류 이유**: 자동 수집 그래프화는 검색어 설정 / 어휘 합의 등 사전 작업 필요. POC 에서는 자리만 (`signal_joiner.py` placeholder), 실제 구현은 추후.

---

## D-11: OntologyTag.extra: dict 추가

**시점**: 2026-05-10
**상태**: 채택

**결정**: OntologyTag dataclass 에 `extra: dict` 필드 추가. 안정적 필드는 명시, 변동 가능 필드는 extra 에.

**이유**:
- LLM 응답 스키마가 아직 미확정 — 모델 응답 구조 바뀌어도 dataclass 수정 없이 흡수
- 모델별 추가 메타데이터(reasoning trace, citations 등) 도 extra 로 받음
- 안정화된 필드는 정식 필드로 승격

**트레이드오프**: type-safety 가 약간 떨어짐. 안정화 후 typed 모델로 승격.

---

## D-12: LLM 추상화는 LLMClient ABC 로 충분

**시점**: 2026-05-10
**상태**: 채택

**결정**: 기존 `core/shared/infra/llm_client.py` 의 LLMClient ABC + LLMRequest/LLMResponse dataclass 를 그대로 사용.

**이유**:
- 다운스트림(taggers, 향후 agents)은 LLMClient ABC 만 의존 → 모델/제공자 변경 시 다운스트림 코드 0 줄 수정
- 모델 교체: `config/runtime.yaml` 한 줄
- 제공자 교체(OpenAI ↔ Anthropic): `langchain_llm_client.py:_get_chat_model` 분기 추가
- 추상화 자체 변경(LangChain → 직접 호출): LLMClient 새 구현체 1 개만

**제공자별 structured output 차이는 추후**: 두 번째 제공자 붙이는 시점에 LangChain의 with_structured_output() 호출로 통일 검토.

---

## D-13: 도구 재사용 정책 — 옵션 C (소스 카테고리별)

**시점**: 초기 설계
**상태**: 채택

**결정**: Tool 은 자산별이 아니라 소스 카테고리별 (`news_search_tool`, `streaming_tool`, `transaction_tool` 등). 자산은 파라미터로 전달.

**이유**:
- 자산이 늘어도 core 도구가 그대로 재사용
- 자산 추가 = AssetProfile 정의로 끝남, core/ 수정 불필요

**자산 특화 Tool**: 드물게 필요 시 `projects/<자산>/tools/`. 동일 도구가 2 개 이상 자산에서 쓰이면 core/ 로 승격.

---

## D-14: AgentContext.artifacts 는 dict (POC), 추후 typed 승격

**시점**: 2026-05-10
**상태**: 채택 (POC 범위)

**결정**: 서브 에이전트 간 산출물 전달은 dict 자유 형식. POC 안정화 후 자주 사용되는 키들을 typed 모델로 승격.

**이유**:
- POC 에서 단계별 산출물이 자주 변할 수 있음 — typed 로 시작하면 매번 dataclass 수정
- 안정 후 typed 가 안전성 측면에서 유리

**트레이드오프**: 초기에 키 이름 typo 등 런타임 에러 가능성. 테스트로 보완.

---

## D-15: SignalJoiner 폐기, 대신 GraphQueryPolicy 로 모듈화 — POC 보류

**시점**: 2026-05-10 (재검토)
**상태**: 보류

**경과**:
- 초기 제안: 배치 신호를 온디멘드 분석 그래프와 연결하는 SignalJoiner 컴포넌트
- 재검토: 옵션 A (어휘 공유) 채택 시 SignalJoiner 불필요, 대신 traversal 정책 모듈(GraphQueryPolicy) 만 필요
- 사용자 의견: "있으면 좋을 정도", POC 빠른 구현이 우선

**결론**: POC 에서는 placeholder 만 (`core/processors/graph_writers/signal_joiner.py`). 구현은 자동 수집 그래프화 정책 구체화 이후.

---

## D-16: Prompt 자산 분리 — PromptCatalog (YAML)

**시점**: 2026-05-12
**상태**: 채택

**결정**: 각 에이전트/서비스의 system + user prompt 와 JSON 응답 스키마를 코드 인라인이 아닌 `core/llm/prompts/<group>/<name>.yaml` 로 외부화. `PromptCatalog.render(key, **vars)` 를 통해 로드.

**구성**:
- 8 개 prompt YAML: exploration{planner,critic}, qa{analyzer,synthesizer,verifier}, tagging.sentiment, mapping.llm_fallback, reporting.report
- 치환 문법은 `string.Template` (`$var`) — prompt 안의 JSON 예시 `{"key": ...}` 와 충돌 회피
- 각 prompt 의 sha256 version_hash 가 자동 계산되어 EvidenceStep 과 Langfuse 메타에 송신

**이유**:
- **버전 추적**: YAML 의 git history = prompt 버전. 회귀 추적 가능
- **A/B 테스트 자리**: PromptCatalog 가 traffic split 가능 (현재는 미사용)
- **비개발자 수정**: prompt 만 바꿀 사람이 코드 안 보고 yaml 만 수정
- **테스트 분리**: render 결과 snapshot test 가능
- **별도 레포 추출 자리**: core/llm/ 디렉토리가 통째로 fnpricing-llm 패키지로 분리 가능

**대안 (기각)**:
- **인라인 유지** — 변경마다 코드 diff, 비개발자 수정 불가
- **Jinja2 템플릿** — 의존성 추가, str.Template 으로 충분
- **Langfuse Prompt Management 단독** — Langfuse 셋업 안 된 환경에서 prompt 로드 실패 가능. yaml + 메타 송신 조합이 안전

**enum drift 보호**: tagging.sentiment / mapping.llm_fallback 의 schema enum 값이 코드 enum 과 일치하는지 `tests/core/llm/test_prompt_catalog.py` 가 검증. drift 발생 시 즉시 테스트 실패.

**적용 범위 (2026-05-12 기준)**: 8 개 LLM 호출 지점 모두 마이그레이션 완료. policy.py 의 모델 단가표도 `core/llm/pricing.yaml` 로 이주.

---

## D-17: Observability — Langfuse 선택 (TraceBackend ABC 뒤)

**시점**: 2026-05-12
**상태**: 채택

**결정**: 1차 observability 백엔드로 Langfuse 채택. `TraceBackend` ABC + NoOp/Stdout/Langfuse 구현체. 호출 코드는 ABC 만 의존 — 결정 영구 아님.

**비교**:

| 항목 | Langfuse | OTEL + Phoenix(Arize) | LangSmith |
|---|---|---|---|
| 라이선스/비용 | 오픈소스 + Cloud free 50k events/월 | 오픈소스, Arize Cloud 유료 | 유료 (5k traces/월 free) |
| 셀프호스팅 부담 | 무거움 (web+worker+clickhouse+postgres+redis+minio) | 가벼움 (단일 컨테이너) | 셀프호스트 X |
| LangChain/LangGraph 통합 | callback 한 줄 | OpenInference instrumentation | 네이티브 |
| Prompt 관리 | First-class | 약함 | 있음 |
| OTEL 호환 | 최근 추가됨 (export) | 네이티브 | 부분 |

**Langfuse 채택 이유**:
- Cloud free 50k events/월 — POC 인프라 부담 0
- PromptCatalog (D-16) 와 시너지 — Langfuse 의 prompt management 가 자연스러운 백엔드
- LangChain callback 통합이 LangGraph (D-07) 와 매끄러움
- OTEL export 호환 — 미래 Phoenix 전환 시 데이터 손실 없음

**LangSmith 기각**: 유료 의존성. 한국 스타트업 환경에서 비용 압박.

**Phoenix 보류**: 더 가벼운 셀프호스팅이지만 prompt management 약함 + Cloud 무료 tier 없음. POC 끝나고 자체 호스팅 시 재검토 후보.

**구현**:
- `TraceBackend` ABC + 3 구현체 (`core/shared/infra/observability/`)
- `TracingLLMClient` 데코레이터 (`core/shared/infra/tracing_llm_client.py`) — contextvars 로 trace_id 전파
- Orchestrator.analyze() 에서 `trace_scope()` 한 번 열면 내부 모든 LLM 호출이 같은 trace 에 자동 첨부
- 호출 지점 (Planner / Tagger 등) 코드 변경 0

**미해결 (다음 sprint)**:
- 배치 DAG task 의 trace_scope (현재 on-demand 만)
- Anthropic prompt caching + `cache_control` 마킹
- LLM 응답 캐싱 (SQLite, 결정적 호출용)

---

## D-18: 4 축 확장 자리를 ABC + placeholder 로 미리 열어둠

**시점**: 2026-05-12
**상태**: 채택

**결정**: STO 평가 / LLM 추적 / 사용량 모니터링 / 대시보드 기반자료 4 축의 확장 자리를
ABC + placeholder 구현체로 한 번에 열어둠. 실제 구현은 추후 채운다.

**열린 자리 (9 ABC + 4 DB 테이블)**:

| ABC | placeholder | 추후 구현 후보 |
|---|---|---|
| `EvaluationOrchestrator` | `DefaultEvaluationOrchestrator` (strategy registry), `NoOpEvaluationOrchestrator` | 가중치 조정 + 결과 통합 |
| `ScoreBuilder` | `StubScoreBuilder` (always 0.0) | `WeightedSignalScoreBuilder` / `LLMRubricScoreBuilder` |
| `AnalysisRunStore` | `InMemoryAnalysisRunStore` | `SqliteAnalysisRunStore` / `PostgresAnalysisRunStore` |
| `EvaluationClaimStore` | `InMemoryEvaluationClaimStore` | `Sqlite*` / `Postgres*` |
| `LLMCallRecorder` | `NoOpLLMCallRecorder`, `InMemoryLLMCallRecorder` | `SqliteLLMCallRecorder` (TracingLLMClient 가 호출) |
| `UsageMetricsCollector` | `NoOpUsageMetricsCollector`, `InMemoryUsageMetricsCollector` | `Sqlite*` (Orchestrator 종료 시 PolicyGate snapshot 적재) |
| `DashboardExporter` | `NoOpDashboardExporter` | `CsvDashboardExporter` / `ParquetDashboardExporter` / `PostgresViewExporter` |
| `SecretProvider` | `EnvSecretProvider`, `ChainSecretProvider`, `StaticSecretProvider` | `AirflowVariableSecretProvider` / `AwsSecretsManagerProvider` / `VaultSecretProvider` |
| `IdentifierExtractor` | `NoOpIdentifierExtractor`, `RegistryBasedIdentifierExtractor` (어댑터 빈 registry) | source_type 별 추출 어댑터 (vworld / building_register / transaction 등) |

**DB 테이블 (스키마만, write 미연결)**:
- `analysis_runs` — on-demand 분석 1회 메타
- `evaluation_claims` — 3축 평가 결과
- `llm_calls` — LLM 호출 단위 metric
- `agent_evidence_steps` — evidence trace 영구화

**이유**:
- 추후 구현체 추가 시 인터페이스 변경 0 → 호출 측 (Orchestrator / Tracing / 보고서) 영향 없음
- GitHub history 가 의도를 명시 — "이 자리는 의도적으로 비어있다, Phase N 에 채운다"
- 한 번에 묶으면 점진 PR 보다 응집도 ↑

**대안 (기각)**:
- **필요 시 그때그때 추가** — 점진적이지만 매번 호출 측 변경 필요. 변경 비용이 누적.
- **ABC 없이 직접 구현체부터** — POC 단계에서 ABC 비용 너무 작음. 미래 swap 시 매번 마이그레이션.
- **실제 구현까지 한 번에** — 점수 산출 / SqliteStore / 대시보드까지 들어가면 PR 비대 + 결정 압박 (점수 가중치 누가 정하는가).

**구현체 wire-up**: `interfaces/composition.py` 의 `_build_*` 팩토리 함수들이 환경에 따라
구현체 선택. 현재는 모두 placeholder, 추후 SqliteStore 구현체가 추가되면 팩토리 한 줄만 교체.

**Orchestrator 변경**: `Orchestrator.analyze()` 가 `EvaluationOrchestrator.evaluate()` 호출 →
`AnalysisResult.claims: list[EvaluationClaim]` 필드 추가. 현재는 빈 list 또는 stub claim (score=0.0).

---

## 결정 추가 양식

새 결정을 추가할 때 다음 양식으로:

```markdown
## D-NN: 한 줄 제목

**시점**: YYYY-MM-DD
**상태**: 채택 / 보류 / 변경됨 / 기각

**결정**: 한 문장 또는 짧은 단락.

**이유**: 핵심 근거 bullet.

**대안 (기각)**: 검토했으나 기각된 옵션 + 기각 이유.

**트레이드오프**: 채택의 부작용 / 한계.
```

---

## 참고 문서

- [ARCHITECTURE.md](ARCHITECTURE.md) — 결정의 결과로 만들어진 시스템 구조
- [AGENT_DESIGN.md](AGENT_DESIGN.md) — D-04, D-05, D-06, D-07, D-08 의 구체 구현
- [ONTOLOGY.md](ONTOLOGY.md) — D-09, D-10, D-11 의 구체 구현
