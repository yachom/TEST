# 에이전트 설계

본 문서는 On-demand 분석 흐름의 핵심인 **멀티 에이전트 Flow** 의 설계를 기술한다.
대상 독자는 (1) 새 세션에서 본 시스템을 빠르게 이해해야 하는 개발자, (2) 본 시스템에 새 에이전트나 서브 컴포넌트를 추가하려는 사람.

---

## 1. 설계 원칙

### 1.1 "에이전트"의 정의를 좁게 잡는다

본 시스템에서 **에이전트** = LLM 이 도구를 자율적으로 선택하는 컴포넌트.
정해진 순서대로 도구를 호출하는 코드는 에이전트가 아니다.

이 정의를 좁게 잡는 이유:
- 모든 LLM 호출을 에이전트로 부르면 비용·디버깅·평가가 모두 어려워짐
- 결정적 부분과 자율적 부분을 분리하면 PolicyGate 가 의미를 가짐
- 결정적 부분은 단위 테스트가 가능, 자율적 부분은 시뮬레이션·평가가 필요

### 1.2 자율 에이전트는 두 곳에만 존재한다

| 단계 | 자율성 필요? | 형태 |
|---|---|---|
| 주소 입력 → 1차 공적 API 호출 | 정해진 순서 | 결정적 Collector |
| 1차 결과 보고 추가 수집 도구 결정 | **자율** | **ExplorationFlow** |
| 수집물 → 그래프 노드/엣지 매핑 | 출력 스키마 고정 | LLM 호출 (어댑터) |
| 그래프 → 보고서 작성 | 형식 고정 | LLM 호출 |
| 사용자 QA | **자율** | **QAFlow** |

자율 에이전트는 ExplorationFlow 와 QAFlow 둘뿐이다. 나머지는 결정적 또는 단발 LLM 호출.

### 1.3 단일 에이전트가 아닌 Flow

ExplorationFlow / QAFlow 는 **단일 LLM 호출이 아니라 여러 서브 에이전트의 그래프** 다.
각 Flow 내부는 자유롭게 확장 가능하도록 열려 있다.

---

## 2. ExplorationFlow

주소 1차 수집 결과를 보고 **추가로 어떤 정보를 수집할지** 자율 판단한다.

### 2.1 구성

```
1차 수집 결과
    │
    ▼
[Planner] ──→ 추가 수집 계획 (도구 + 사유)
    │
    ▼
[Retriever] ──→ PolicyGate 통과한 도구 호출 → 결과 누적
    │
    ▼
[Critic] ──→ 충분한가?
    │
    ├── No → Planner 재호출 (수집물 추가 컨텍스트)
    └── Yes → Flow 종료
```

### 2.2 서브 에이전트 역할

| 서브 에이전트 | 입력 | 출력 | LLM 사용 |
|---|---|---|---|
| Planner | 1차 수집 결과 + (재계획 시) 누적 결과 | 도구 호출 계획 (도구명, 입력, rationale) | Yes |
| Retriever | Planner 의 계획 + PolicyGate | 호출된 도구의 결과 | Yes (도구 선택), 도구 실행은 코드 |
| Critic | 누적된 수집물 | 충분/부족 판정 + 사유 | Yes |

### 2.3 종료 조건

다음 중 하나라도 충족되면 종료:
- Critic 이 충분 판정
- 최대 반복 3회 도달
- PolicyGate 한도 도달 (max_tool_calls / max_cost_usd)

### 2.4 확장 자리

POC 에서는 위 3개로 시작. 추후 추가 후보:
- Hypothesizer — 1차 결과 보고 가설 생성, Planner 가 가설 검증 도구를 우선 선택
- FactChecker — Retriever 결과의 일관성 검증
- Summarizer — 누적 결과 압축 (Planner 의 컨텍스트 비대화 방지)

신규 서브 에이전트 추가 시 변경 범위는 `core/agents/exploration/` 만.

---

## 3. QAFlow

사용자 질문에 대해 그래프 / 보고서 / 신호를 검색해서 답한다.

### 3.1 구성

```
사용자 질문
    │
    ▼
[Analyzer] ──→ 질문 분류 (사실 조회 / 추론 / 비교 / 시계열)
    │
    ▼
[Retriever] ──→ 분류별 검색 전략으로 정보 수집
    │
    ▼
[Synthesizer] ──→ 답변 초안
    │
    ▼
[Verifier] ──→ 근거 정합성 검증
    │
    ├── Fail → Synthesizer 재시도 (검증 실패 사유 추가)
    └── Pass → 답변 반환
```

### 3.2 서브 에이전트 역할

| 서브 에이전트 | 책임 | LLM 사용 |
|---|---|---|
| Analyzer | 질문 종류 분류, 필요 정보 식별 | Yes |
| Retriever | 그래프 traversal / 보고서 RAG / signal_store 조회 | Yes (전략 선택), 검색은 코드 |
| Synthesizer | 검색 결과 종합 → 답변 초안 | Yes |
| Verifier | 근거 누락 / 모순 검사 | Yes |

### 3.3 확장 자리

- Clarifier — 질문이 모호할 때 되묻기
- Comparator — 두 자산 / 두 시점 비교 전용
- ScopeRouter — scope_id 가 여러 개일 때 어느 scope 를 볼지 결정

---

## 4. 공통 추상화

### 4.1 Agent ABC

모든 (서브)에이전트가 구현하는 통일 인터페이스. Flow 자체도 이 ABC 를 구현한다.

```python
# core/agents/base.py

class Agent(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, context: AgentContext) -> AgentContext: ...
```

**Flow 도 Agent 인 이유**:
- Orchestrator 는 `flow.run(ctx)` 한 줄로 어떤 Flow 든 호출 가능
- 추후 Flow 안에 Flow 를 둘 수 있음 (재귀적 멀티 에이전트)
- Mock Agent 로 Flow 를 통째로 대체하여 테스트 가능

### 4.2 AgentContext

서브 에이전트들이 주고받는 공유 상태.

```python
@dataclass
class AgentContext:
    scope_id: str                # 그래프 격리 단위
    inputs: dict                 # Flow 진입 시 입력
    artifacts: dict              # 단계 간 공유 산출물
    evidence: EvidenceTrace      # 누적 evidence
```

**artifacts 가 dict 인 이유**: POC 단계에서는 단계별 산출물이 자주 변할 수 있음. 안정화되면 typed 모델로 승격.

### 4.3 EvidenceTrace

Flow 가 거친 모든 단계의 흔적.

```python
@dataclass
class EvidenceStep:
    step_id: int
    actor: str               # 어느 서브 에이전트인지
    tool_name: str
    rationale: str           # LLM 이 이 단계를 선택한 이유
    input_summary: dict
    result_summary: dict
    occurred_at: datetime

@dataclass
class EvidenceTrace:
    scope_id: str
    steps: list[EvidenceStep]
```

**evidence trace 의 용도**:
- 보고서의 근거 체인 (어떤 도구가 어떤 결과를 줬고, 그 결과가 보고서 어느 부분에 반영됐는지)
- QA 답변의 근거 (사용자가 "왜 이 결론?" 물었을 때 evidence trace 따라 설명)
- 디버깅 (Flow 가 잘못 동작했을 때 어느 단계 문제인지)
- 비용 추적 (도구별 호출 수)

**prompt_version 기록**: 각 LLM 호출 EvidenceStep 의 `input_summary["prompt_version"]` 에 PromptCatalog 가 계산한 sha256 version_hash 가 저장된다. prompt YAML 이 바뀌면 hash 가 바뀌어 회귀 추적 가능 ([D-16](DECISIONS.md#d-16)).

**Langfuse trace 와의 관계**: EvidenceTrace 는 도메인 사용자가 보는 근거 체인, Langfuse 는 개발자가 보는 시스템 추적. `scope_id` = Langfuse trace_id 로 매핑되어 cross-reference 가능 ([ARCHITECTURE.md §8](ARCHITECTURE.md#8-observability), [D-17](DECISIONS.md#d-17)).

---

## 5. PolicyGate (하이브리드 자율성 통제)

자율 에이전트가 무한정 도구를 호출하지 못하도록 정책으로 게이트.

### 5.1 정책 항목

```python
@dataclass
class AgentPolicy:
    max_tool_calls: int = 10       # Flow 단위 누적 호출 한도
    max_cost_usd: float = 1.0      # Flow 단위 누적 비용 한도
    allowed_tools: list[str]       # AssetProfile 에서 주입
    require_rationale: bool = True # rationale 없는 호출 차단
```

### 5.2 흐름

```
LLM(Planner/Analyzer) — 도구 + rationale 제안
        │
        ▼
PolicyGate.check(tool, rationale, cost)

        │
        ├── allowed=False → Flow 가 다른 도구 시도 또는 종료
        └── allowed=True
                │
                ▼
        도구 실행 (코드)
                │
                ▼
        PolicyGate.record(cost)
        EvidenceStep 누적
```

### 5.3 LLM 호출 비용 자동 누적 (TracingLLMClient 경유)

`PolicyGate.record(usage, model)` 은 LLM 호출에 대해서도 누적된다. 다만 서브 에이전트(Planner / Critic / 등)가 명시적으로 호출하지 않고 `TracingLLMClient` 가 자동으로 처리한다:

```python
# composition.py
gate = PolicyGate(policy)
llm = TracingLLMClient(inner_llm, trace_backend, role="...", policy_gate=gate)
planner = Planner(llm, allowed_tools=..., prompt_catalog=catalog)
# planner.run() 안의 llm.call() 이 끝나면 자동으로 gate.record(usage, model) 호출
```

따라서 PolicyGate.cost_used 에는 도구 호출 비용 + LLM 호출 비용 (토큰 → USD 환산) 이 함께 누적된다. 토큰 단가는 `core/llm/pricing.yaml` ([D-16](DECISIONS.md#d-16)).

### 5.4 자산별 다른 정책

같은 PolicyGate 클래스에 다른 AgentPolicy 만 주입:
- 부동산 분석 — `allowed_tools=[vworld_tool, building_hub_tool, tenant_tool, pdf_upload_tool, web_search_tool]`
- 음악 저작권 분석 — `allowed_tools=[streaming_tool, chart_tool, web_search_tool]`

`AssetProfile` 이 자산별 정책을 들고 있다.

---

## 6. LangGraph 라우팅

Flow 의 라우팅(분기 / 루프 / 조건부 종료)은 LangGraph 의 StateGraph 로 구현한다.

### 6.1 채택 이유

- 기존 `core/shared/infra/langchain_llm_client.py` 가 이미 LangGraph 사용 중 — 의존성 추가 없음
- Critic 루프 같은 조건부 분기를 `add_conditional_edges` 한 줄로 표현
- 그래프 시각화 가능 (디버깅 / 문서화)
- 상태 전달이 StateGraph 로 일관됨

### 6.2 Flow 골격 (의사 코드)

```python
from langgraph.graph import StateGraph, START, END

class ExplorationFlow(Agent):
    def __init__(self, planner, retriever, critic, gate):
        self._graph = self._build_graph(planner, retriever, critic, gate)

    def _build_graph(self, planner, retriever, critic, gate):
        g = StateGraph(AgentContext)
        g.add_node("plan", planner.run)
        g.add_node("retrieve", retriever.run)
        g.add_node("critic", critic.run)
        g.add_edge(START, "plan")
        g.add_edge("plan", "retrieve")
        g.add_edge("retrieve", "critic")
        g.add_conditional_edges("critic", self._route_after_critic, {
            "replan": "plan",
            "done": END,
        })
        return g.compile()

    def run(self, ctx: AgentContext) -> AgentContext:
        return self._graph.invoke(ctx)

    @staticmethod
    def _route_after_critic(ctx: AgentContext) -> str:
        if ctx.artifacts.get("critic_decision") == "sufficient":
            return "done"
        if len(ctx.evidence) >= 3 * MAX_TOOLS_PER_ITER:
            return "done"
        return "replan"
```

---

## 7. Orchestrator (결정적 흐름 제어)

Flow 들과 결정적 컴포넌트를 묶어 전체 분석을 수행하는 진입점.

```
[Orchestrator]
    ├── scope_id 발급 (analysis_<uuid>)
    ├── ① InitialCollector — 정해진 API 호출 (vworld 등)
    ├── ② ExplorationFlow.run(ctx)
    ├── ③ OntologyMapper — 수집물 → 그래프
    ├── (④ SignalJoiner placeholder — POC 보류)
    ├── ⑤ ReportBuilder — 그래프 → 보고서
    └── ⑥ QAFlow 인스턴스 반환 (사용자 인터랙션용)
```

Orchestrator 는 LLM 을 직접 호출하지 않는다. Flow 와 컴포넌트의 호출 순서만 관리.

---

## 8. POC 단계의 단순화

다음은 POC 에서 명시적으로 단순화한 부분이다. 안정화 후 정교화 검토.

| 부분 | POC | 추후 |
|---|---|---|
| Flow 라우팅 | LangGraph 직선 + 단일 분기 | 다중 분기, 병렬 노드 |
| 서브 에이전트 수 | Flow 당 3~4개 | 확장 자리 활용 |
| AgentContext.artifacts | 자유 dict | typed 모델 |
| 비용 추적 | 호출 수만 (고정 비용) | LLM usage 토큰 기반 실제 비용 |
| EvidenceStep.result_summary | 단순 dict | 표준 스키마 |
| Verifier 로직 | 휴리스틱 (근거 인용 존재 여부) | 사실 검증 LLM |

---

## 9. 새 (서브) 에이전트 추가 절차

### 9.1 ExplorationFlow / QAFlow 안에 서브 에이전트 추가

```python
# core/agents/exploration/hypothesizer.py

class Hypothesizer(Agent):
    name = "exploration.hypothesizer"

    def __init__(self, llm_client):
        self._llm = llm_client

    def run(self, ctx: AgentContext) -> AgentContext:
        # ctx.artifacts["initial_collection"] 보고 가설 생성
        hypotheses = self._call_llm(...)
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

그 다음 `exploration/flow.py` 의 LangGraph 에 노드 추가 + 엣지 변경.

### 9.2 새 Flow 추가

`core/agents/<flow_name>/` 디렉토리 생성, `flow.py` 에 Flow 클래스, 서브 에이전트 파일들. Orchestrator 가 새 Flow 를 호출하도록 등록.

---

## 10. 참고 문서

- [ARCHITECTURE.md](ARCHITECTURE.md) — 시스템 전체 구조에서 에이전트의 위치
- [ONTOLOGY.md](ONTOLOGY.md) — 에이전트가 수집한 데이터를 어떻게 그래프로 매핑하는가
- [DECISIONS.md](DECISIONS.md) — Flow 채택 / LangGraph 채택 등 의사결정 이력
