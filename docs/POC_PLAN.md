# POC 계획

## 1. POC 목적

- 두 개의 이질적인 자산(상가형 부동산, 음악 저작권)에 대해 동일한 감정평가 파이프라인을 적용한다.
- 두 자산의 공통점·차이점을 통해 본 시스템의 추상화 수준이 적절한지 검증한다.
- POC 결과를 바탕으로 향후 자산 확장 시의 공통화 정책을 결정한다.

POC가 끝나는 시점에 대답해야 할 질문:
- `Collector` 추상화가 두 자산 모두에 자연스럽게 맞는가?
- `SentimentTarget`의 `unique_key()` 추상화가 충분한가, 더 세부적인 인터페이스가 필요한가?
- `EvaluationClaim` 모델이 두 자산의 결과를 모두 표현할 수 있는가?
- 자산별 온톨로지 스키마는 얼마나 다른가? 공통 부분이 있는가?

---

## 2. POC 자산 비교

### 2.1 상가형 부동산

| 항목 | 내용 |
|---|---|
| AssetFamily | REAL_ESTATE |
| AssetClass | COMMERCIAL |
| 평가 대상 | 건물 (PNU), 입점업체 (사업자번호) |
| 데이터 소스 | 뉴스, 실거래가, 건축물대장, 토지대장, 리뷰 |
| 시장 신호 카테고리 | STO 제도, 거시 금융, 상업용 부동산 시장, 임차 업황, 규제, 도시계획 |
| 주요 평가 요인 | 임대수익률, 공실위험, 거래량, 임차수요 안정성 |
| 식별자 체계 | PNU(19자리), 법정동코드(10자리), 사업자번호(10자리) |

### 2.2 음악 저작권

| 항목 | 내용 |
|---|---|
| AssetFamily | INTELLECTUAL_PROPERTY |
| AssetClass | MUSIC_COPYRIGHT |
| 평가 대상 | 음원 (ISRC), 아티스트, 발행사 (법인번호) |
| 데이터 소스 | 뉴스, 음원 차트, 스트리밍 통계, SNS 평판 |
| 시장 신호 카테고리 | STO 제도, K-pop 산업 동향, 저작권법 변경, 스트리밍 시장, 글로벌 음원 시장 |
| 주요 평가 요인 | 스트리밍 추세, 저작권 분쟁, 아티스트 평판, 글로벌 진출 가능성 |
| 식별자 체계 | ISRC(12자), 법인번호(13자리), 아티스트명+소속사 |

### 2.3 공통점

- 둘 다 LLM 온톨로지 태깅을 거친다.
- 둘 다 **시장 신호** + **평가 대상별 신호** 두 종류를 수집한다.
- 둘 다 점수 + claim + evidence 구조의 보고서를 생성한다.
- 둘 다 STO 제도와 거시 금융환경 신호를 공통으로 사용할 수 있다.

### 2.4 차이점

- 데이터 소스가 거의 겹치지 않는다 (공통은 뉴스 정도).
- 평가 대상의 식별자 체계가 다르다.
- 평가 요인 사전이 다르다.
- 음악 저작권은 **글로벌 신호**가 중요하다 (영어 데이터 소스 필요).

---

## 3. 단계별 목표

### Phase 1: 상가형 부동산 MVP (현재)

**목표**: 뉴스 수집 → 룰 필터 → 임베딩 → 의미 중복 제거 → LLM 태깅 → Signal 적재의 전체 흐름이 Mock 환경에서 동작.

**범위**:
- `projects/commercial_real_estate/` 전체 구성
- `core/collectors/news/` 기본 구현 (실제 네이버 API는 TODO)
- `core/processors/` 모든 단계 구현
- `core/evaluation/sentiment/` 기본 흐름
- 테스트 22개 이상 통과

**제외**:
- 정량평가 / 구조평가 — stub만
- 실제 네이버 API 호출 — TODO
- 실제 LLM 호출 — Stub
- 실제 Graph DB 적재 — NoOp

### Phase 2: 음악 저작권 추가

**목표**: 두 번째 자산을 추가하여 추상화의 적절성을 검증.

**범위**:
- `projects/music_copyright/` 구성
- 음원 차트 / 스트리밍 통계 collector 추상 (실제 호출은 TODO)
- 음악 저작권 평가 대상 (`ArtistTarget`, `SongTarget`)
- 음악 저작권 온톨로지 스키마 사전
- 추가 검색어 그룹 (글로벌 신호 포함)

**검증**:
- 부동산 코드를 수정하지 않고 음악 저작권을 추가할 수 있는가?
- 두 자산이 동일한 `core/processors/` 를 그대로 사용할 수 있는가?

### Phase 3: On-demand 주소 분석 흐름 추가 (현재 진행)

**목표**: 부동산 자산을 대상으로 주소 입력 → 멀티 에이전트 Flow → 보고서 → QA 까지의 흐름을 Mock 환경에서 끝까지 흘려본다.

**범위**:
- `core/shared/stores/graph_store.py` — GraphStore ABC + InMemoryGraphStore (✓ 완료)
- `core/agents/base.py`, `policy.py` — Agent ABC, PolicyGate (✓ 완료)
- `core/agents/exploration/{flow,planner,retriever,critic}` — ExplorationFlow + LangGraph
- `core/agents/qa/{flow,analyzer,retriever,synthesizer,verifier}` — QAFlow + LangGraph
- `core/agents/orchestrator.py` — 결정적 흐름 제어
- `core/processors/ontology_mapper/` — 어댑터 + LLM fallback
- `core/processors/graph_writers/pattern_builder.py`
- `core/reporting/{report_builder,qa_service}.py`
- Mock 도구 1~2 개 (`vworld_mock_tool` 등)
- CLI: `python -m interfaces.cli analyze-address <주소>`

**제외**:
- 실제 vworld / 건축허브 API 연동 — 추후 (Phase 4)
- 자동 수집 그래프화 (옵션 A 구체화) — 보류
- 영구 그래프 DB — Phase 4
- SignalJoiner 실제 구현 — 보류

**검증**:
- 주소 입력 → 보고서 생성까지 끝까지 동작
- ExplorationFlow 의 Critic 루프가 의도대로 종료됨
- evidence trace 가 보고서 근거에 반영됨
- PolicyGate 가 max_tool_calls 한도를 강제함

상세 [AGENT_DESIGN.md](AGENT_DESIGN.md), [ONTOLOGY.md](ONTOLOGY.md), [DECISIONS.md](DECISIONS.md).

### Phase 4: 실제 외부 연동 + 공통화 정책 결정

**목표**: Stub 을 실제 구현으로 교체하고, POC 결과를 토대로 향후 자산 확장 시의 공통화 정책을 정한다.

**범위**:
- 네이버 뉴스 API 실제 호출
- 실제 임베딩 모델 (예: KoSimCSE)
- 실제 LLM 호출 (예: Claude API)
- 실제 Graph DB (예: Neo4j) — 영구 모드 검증
- 실제 Signal 저장소 (예: PostgreSQL + pgvector)
- vworld / 건축허브 / 입점 상가 API 연동
- 자동 수집 그래프화 구체화 (옵션 A 의 어휘 합의)

**산출물**:
- 본 시스템의 자산 확장 정책 문서 (어떤 부분이 자산 무관, 어떤 부분이 자산 특화인지의 최종 결정)
- 실제 운영 환경 배포 가이드

---

## 4. POC에서 다루지 않는 것

다음은 POC 범위에서 명시적으로 제외한다.

- **정량평가 / 구조평가의 실제 구현**: stub만 두고 추후 채운다.
- **사용자 인터페이스(웹/앱)**: CLI 와 LLM Tool 만 제공.
- **실제 운영 환경의 Airflow 설정**: DAG 정의만 하고, Airflow 인프라 구성은 별도.
- **자동 수집 그래프화 구체화**: 옵션 A 방향만 결정. 검색어 / 어휘 합의는 추후 ([D-10](DECISIONS.md#d-10)).
- **영구 그래프 DB 운영**: POC 는 휘발(InMemoryGraphStore). 영구는 지리/행정동 그룹화 룰 검증 후 ([D-03](DECISIONS.md#d-03)).
- **SignalJoiner 실제 구현**: placeholder 만, 자동 수집 그래프화 후 검토 ([D-15](DECISIONS.md#d-15)).

---

## 5. POC 종료 기준

다음 조건을 모두 만족하면 POC가 종료된 것으로 본다.

- [ ] 상가형 부동산 자산의 전체 배치 흐름이 Mock 환경에서 끝까지 실행된다.
- [ ] 음악 저작권 자산이 추가되어도 부동산 코드 수정이 발생하지 않는다.
- [ ] 두 자산 모두에서 22 개 이상의 단위 테스트가 통과한다.
- [ ] 실제 네이버 뉴스 API 호출이 한 번 이상 성공한다.
- [ ] LLM 온톨로지 태깅 결과가 `signal_store` 에 적재된다.
- [ ] On-demand 분석: 주소 입력 → ExplorationFlow → OntologyMapper → GraphStore → ReportBuilder → QAFlow 가 Mock 환경에서 끝까지 동작한다.
- [ ] PolicyGate 가 max_tool_calls 한도를 강제한다 (테스트로 검증).
- [ ] EvidenceTrace 가 보고서의 근거 체인으로 반영된다.

---

## 6. POC 이후 결정해야 할 정책

POC 결과를 바탕으로 다음을 결정한다.

| 정책 | 결정해야 할 내용 |
|---|---|
| 추상화 수준 | `Collector` 를 더 일반화할지, 자산별로 분리할지 |
| 평가 대상 표현 | `EvaluationTarget` 에 추가 메서드가 필요한지 |
| 평가 결과 모델 | `EvaluationClaim` 에 자산별 확장 필드가 필요한지 |
| Tool 인터페이스 | 카테고리별 Tool 로 충분한지, 자산별 Tool 도 필요한지 |
| 자산 간 신호 공유 | STO 제도·거시 금융 신호를 공통 Pool 로 둘지 |
| 보고서 형식 | 차원별 점수 표시, 종합 점수 산출 방식 |
| Graph 스키마 | 자산 간 공유 어휘 (LandUse, EvaluationFactor 등) 의 표준화 수준 |
| 그래프 영구화 | 지리 / 행정동 / 자산 단위 중 어느 scope_id 로 누적할지 |
| AgentContext.artifacts | dict 자유 형식 유지 vs typed 모델 승격 |
| 자동 수집 그래프화 | 옵션 A 의 어휘 합의 / 검색어 정의 수준 |
