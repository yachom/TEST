# 런타임 동작 — 입력/출력 레퍼런스

본 문서는 **현재 코드가 실제로 어떤 입력을 받아 어떤 출력을 내는지** 를 실행 결과 그대로 기록한다.

대상 독자:
1. 처음 레포를 받고 "이게 진짜 도는지" 확인하려는 사람
2. CLI / 파이프라인의 입출력 형태를 코드 안 까보고 알고 싶은 사람
3. Phase 4 외부 API 연동 시 "Mock/Stub 모드 vs Real 모드" 차이를 미리 알아둬야 하는 사람

모든 출력은 2026-05-12 기준 `Stub LLM + Mock Provider + Mock Tools` 모드에서 캡처되었다.
실제 LLM / 실제 API 연결 시 동작은 §3 참조.

---

## 1. 환경 / 의존성

```bash
# 최소
pip install -e ".[dev]"

# 실제 LLM 사용 시
pip install -e ".[dev,anthropic]"

# observability (Langfuse)
pip install -e ".[dev,anthropic,observability]"

# 실거래가 API
pip install -e ".[dev,realestate]"
```

테스트:
```bash
$ pytest -q
119 passed, 19 warnings in 0.22s
```

기본 모드(외부 키 없음)에서:
- LLM: `StubLLMClient` (빈 JSON `{}` 반환)
- News Provider: `MockNewsSearchProvider` (고정 mock 응답)
- Address Tool: `MockAddressInfoTool` (고정 1 레코드)
- GraphStore: `InMemoryGraphStore` (휘발)
- Observability: `NoOpBackend`

---

## 2. CLI 명령별 입력/출력

### 2.1 `run-once` — 배치 파이프라인 1 회 실행

**입력**:
```bash
python -m interfaces.cli run-once
# (또는) python -m interfaces.cli run-once --asset commercial
```

| 인자 | 기본값 | 설명 |
|---|---|---|
| `--asset` | `commercial` | `commercial` \| `music_copyright` |

**내부 동작 (현재 모드)**:
1. `projects/commercial_real_estate/profile.py::COMMERCIAL_PROFILE` 로드
2. `projects/commercial_real_estate/config/search_groups.yaml` 의 active 그룹 (현재 6 개) 로드
3. `MockNewsSearchProvider` 가 그룹별 query 에 대해 고정 응답 반환
4. RuleFilter → Embedder → SemanticDedup → OntologyTagger(Stub) → GraphSignal

**출력 (stdout)**:
```
[run_once] asset=commercial  run_id=93cb2fb7  queries=48  est_calls=58
  search  → fetched=144  saved=144  dup=0
  filter  → total=144  passed=18
  embed   → done=18
  dedup   → novel=0  duplicate=18
  tagging → ok=0  failed=0
  graph   → queued=0
[run_once] 완료
```

**숫자 해석**:
- `queries=48` — search_groups.yaml 의 활성 그룹들의 모든 쿼리 합
- `fetched=144` — Mock Provider 가 쿼리당 평균 3 개 mock 응답
- `passed=18` — RuleFilter (asset_keywords + signal_keywords + min_text_length 통과)
- `novel=0` — Mock 응답이 거의 동일 텍스트 → SemanticDedup 이 모두 중복 판정
- `tagging ok=0` — novel 만 태깅 대상이라 0 (Stub 동작이 아니라 입력 0)

**실제 Naver Provider 사용 시 차이**:
```bash
export NAVER_CLIENT_ID=...
export NAVER_CLIENT_SECRET=...
```
- `fetched` 가 실 API 응답 수 (그룹당 max_display)
- `novel` 이 실제로 0 이 아닌 값 → tagging 호출 발생
- 토큰 비용 발생 (anthropic 모드일 때)

---

### 2.2 `search` — 단일 키워드 즉시 검색

**입력**:
```bash
python -m interfaces.cli search "상가 공실률" --no-save --max-results 5
```

| 인자 | 기본값 | 설명 |
|---|---|---|
| `keyword` (필수) | — | 검색어 |
| `--no-save` | False | `True` 시 결과만 반환, 저장 안 함 |
| `--max-results` | 5 | 응답 개수 (Provider 의 max_display) |

**출력**:
```
[search] keyword='상가 공실률'  fetched=3  saved=0
```

저장 모드 (`save=True`) 일 경우 `saved=N` 도 0 보다 큼.

**용도**: 검색어 튜닝, 신규 검색 그룹 후보 검증, API 응답 형태 점검.

---

### 2.3 `analyze-address` — On-demand 주소 분석

**입력**:
```bash
python -m interfaces.cli analyze-address "강남구 역삼동 123-45" --show-evidence
```

| 인자 | 기본값 | 설명 |
|---|---|---|
| `address` (필수) | — | 분석 대상 주소 |
| `--asset` | `commercial` | 자산 클래스 |
| `--show-evidence` | False | EvidenceTrace 출력 |
| `--show-graph` | False | LLM 에 입력된 직렬화 그래프 출력 |
| `--question "..."` | None | 분석 후 QAFlow 로 추가 질문 |
| `--real-llm` | False | StubLLM 대신 runtime.yaml 의 LLM 사용 |
| `--real-tools` | False | MockAddressInfoTool 대신 Vworld/Juso/MOLIT 실 API |
| `--pdf-path PATH` | None | 등기 PDF 업로드 (HITL flow) |

**출력 — 기본 모드** (Stub LLM + Mock Tool):
```
[analyze-address] scope_id=analysis_919bec292ae5
  evidence_steps=2
  report.node_count=2
  report.relation_count=1
  report.nodes_by_label={'Address': 1, 'LandUse': 1}
  summary='2개 노드 / 1개 관계 식별됨.'

  Evidence steps:
    [1] exploration.planner → llm: propose additional collection tools
    [2] exploration.critic → llm: evaluate sufficiency of collected information
```

**왜 evidence_steps=2 인가?** Stub LLM 이 빈 JSON 을 반환 → Planner 의 plan 이 빈 list → Retriever 가 호출할 도구 없음 (step 추가 0) → Critic 이 빈 응답에 안전 기본값 `sufficient` 반환 → 1 회 iteration 으로 종료.

**왜 summary 가 fallback 인가?** ReportBuilder 의 LLM 도 stub 이라 `{"summary": ...}` 가 비어있음 → `_fallback_summary()` 가 노드/관계 카운트만 표시.

**`--show-graph` 추가 시**:
```
  Graph (LLM input):
    ## Nodes
    Address (1):
      - 강남구 역삼동 123-45 | address=강남구 역삼동 123-45
    LandUse (1):
      - 제2종근린 | code=제2종근린

    ## Relations
    Address(강남구 역삼동 123-45) -[HAS_USE]-> LandUse(제2종근린)
```
이 텍스트가 `reporting.report` prompt 의 `$graph_text` 변수에 들어감.

**`--question "..."` 추가 시**:
```
[qa] 이 자산의 임대수익률은 어떻게 평가됐나요?
  answer=''
  verifier=pass
```
Stub 모드에서는 Synthesizer 가 빈 응답을 줘서 `answer=''`. Verifier 안전 기본값으로 `pass`. (실 LLM 연결 시 의미 있는 답변.)

---

### 2.4 `init-db` — DB 스키마 초기화

**입력**:
```bash
python -m interfaces.cli init-db
```

환경변수로 DB URL 변경 가능:
```bash
FNPRICING_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/fnpricing python -m interfaces.cli init-db
```

**출력**:
```
[init-db] url=sqlite:///./var/fnpricing.db schema_version=1
  tables=schema_migrations, news_articles, article_embeddings, ontology_tags, market_signals, run_summaries, analysis_runs, evaluation_claims, llm_calls, agent_evidence_steps
```

기본 DB: `./var/fnpricing.db` (SQLite). `.gitignore` 에서 `var/` 제외.

테이블 중 6개(`schema_migrations`, `news_articles`, `article_embeddings`, `ontology_tags`, `market_signals`, `run_summaries`)는 배치 파이프라인이 실제 사용. 나머지 4개(`analysis_runs`, `evaluation_claims`, `llm_calls`, `agent_evidence_steps`)는 확장 자리 — 스키마만 생성, write 는 추후 SqliteStore 구현체가 추가되면 활성화 ([D-18](DECISIONS.md#d-18)).

---

## 3. 모드 매트릭스 — Stub vs Real

| 모드 | LLM | Provider | Tools | GraphStore | Observability |
|---|---|---|---|---|---|
| **기본** | Stub | Mock | Mock (1 개) | InMemory | NoOp |
| `--real-llm` | runtime.yaml (anthropic) | Mock | Mock | InMemory | NoOp |
| `--real-tools` (키 일부) | Stub | Mock | Vworld + Juso | InMemory | NoOp |
| `--real-tools` (키 전체) | Stub | Mock | Vworld + Juso + MOLIT (실거래가) + 건축물대장 | InMemory | NoOp |
| `--real-llm --real-tools` | runtime.yaml | Mock | 위 + 등기 PDF HITL | InMemory | NoOp |
| `FNPRICING_OBSERVABILITY_BACKEND=langfuse` | (어느 모드든) | (어느 모드든) | (어느 모드든) | InMemory | Langfuse |

### 3.1 키 / 환경변수 의존

| 모드 활성화 조건 | 필요한 env var |
|---|---|
| `--real-llm` (anthropic) | `ANTHROPIC_API_KEY` |
| `--real-llm` (openai) | `OPENAI_API_KEY` |
| `--real-tools` 최소 | `JUSO_CONFIRM_KEY`, `VWORLD_API_KEY` |
| `--real-tools` 실거래가 | 위 + `MOLIT_SERVICE_KEY` 또는 `DATA_GO_KR_SERVICE_KEY` |
| Naver 뉴스 | `NAVER_CLIENT_ID` + `NAVER_CLIENT_SECRET` (또는 multi: `NAVER_CLIENT_IDS` / `NAVER_CLIENT_SECRETS` 콤마구분) |
| Langfuse | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (옵션: `LANGFUSE_HOST`) |

키가 누락되면 해당 컴포넌트는 자동으로 Stub/Mock/NoOp 으로 fallback — 흐름은 안 깨짐.

---

## 4. Observability 출력 예시

backend 를 stdout 으로 켜면 trace 라이프사이클이 JSON line 으로 출력된다:

```bash
FNPRICING_OBSERVABILITY_BACKEND=stdout \
python -m interfaces.cli analyze-address "강남구 역삼동 123-45"
```

```json
{"ts": "2026-05-12T05:35:48.309412Z", "event": "trace.start", "trace_id": "analysis_495601c6ba3a", "name": "address_analysis", "metadata": {"address": "강남구 역삼동 123-45"}}
{"ts": "2026-05-12T05:35:48.311141Z", "event": "generation.start", "trace_id": "analysis_495601c6ba3a", "name": "llm.address_analysis", "role": "address_analysis", "model": "stub", "input": {"system": "...", "user": "..."}}
{"ts": "2026-05-12T05:35:48.311161Z", "event": "generation.end", "trace_id": "analysis_495601c6ba3a", "name": "llm.address_analysis", "role": "address_analysis", "model": "stub", "usage": {"input_tokens": 0, "output_tokens": 0}, "error": null, "output": "{}"}
{"ts": "2026-05-12T05:35:48.311832Z", "event": "generation.start", "trace_id": "analysis_495601c6ba3a", "name": "llm.address_analysis", ...}
{"ts": "2026-05-12T05:35:48.311843Z", "event": "generation.end", ...}
{"ts": "2026-05-12T05:35:48.312327Z", "event": "generation.start", ...}
{"ts": "2026-05-12T05:35:48.312337Z", "event": "generation.end", ...}
{"ts": "2026-05-12T05:35:48.312355Z", "event": "trace.end", "trace_id": "analysis_495601c6ba3a", "name": "address_analysis", "error": null}
```

- 1 trace 안에 3 개 generation (planner / critic / report_builder) 가 시간 순서로 기록됨
- 토큰 사용량 (현재 stub 라 0), 모델, 에러 등 메타 포함
- Langfuse 백엔드도 동일 시퀀스를 SDK 로 송신 — Cloud 대시보드에서 시각화

prompt 전체를 보고 싶으면:
```bash
FNPRICING_OBSERVABILITY_STDOUT_INCLUDE_PROMPTS=true \
FNPRICING_OBSERVABILITY_BACKEND=stdout \
python -m interfaces.cli analyze-address "..."
```

---

## 5. 도메인 객체 입출력

### 5.1 AnalysisResult (Orchestrator.analyze 반환)

```python
@dataclass
class AnalysisResult:
    scope_id: str             # "analysis_<uuid12>"
    report: dict              # {scope_id, node_count, relation_count,
                              #  nodes_by_label, relations_by_type,
                              #  summary, graph_text, prompt_version,
                              #  registry_review?}
    qa_flow: QAFlow           # 추가 질문용 인스턴스
    evidence: EvidenceTrace   # 누적 실행 흔적
```

### 5.2 report dict 형태 (실측)

```python
{
    "scope_id": "analysis_919bec292ae5",
    "node_count": 2,
    "relation_count": 1,
    "nodes_by_label": {"Address": 1, "LandUse": 1},
    "relations_by_type": {"HAS_USE": 1},
    "summary": "2개 노드 / 1개 관계 식별됨.",   # Stub 모드: fallback
    "graph_text": "## Nodes\nAddress (1):\n  - 강남구 역삼동 123-45 | ...",
    "prompt_version": "<sha256_prefix>",
}
```

`--real-tools` 가 MOLIT 키까지 있고 거래가 일정 임계 이상이면:
```python
{
    ...,
    "registry_review": {
        "guidance_url": "https://www.iros.go.kr/...",
        "guidance_text": "등기사항증명서 발급 후 --pdf-path 옵션으로 재호출하세요.",
        "triggered_by": "always",
        "total_masked_count": 23,
        "recent_12_months_count": 7,
    },
}
```
이 경우 사용자는 PDF 발급 후 `--pdf-path` 옵션으로 재호출.

### 5.3 QA 답변 형태

```python
qa.ask(scope_id, question) → {
    "question": "...",
    "answer": "...",                 # Stub: ""
    "citations": ["src1", "src2"],   # Stub: []
    "verifier_decision": "pass" | "fail",   # Stub: pass (안전 기본값)
    "evidence_steps": [...]
}
```

---

## 6. 빠른 sanity 체크 (커밋/배포 전)

```bash
# 1) 단위 테스트
pytest -q
# expected: 119 passed

# 2) 배치 1회
python -m interfaces.cli run-once
# expected: fetched=144 saved=144 → ... [run_once] 완료

# 3) on-demand
python -m interfaces.cli analyze-address "강남구 역삼동 123-45"
# expected: scope_id=analysis_<...> evidence_steps=2 node_count=2

# 4) DB 초기화
python -m interfaces.cli init-db
# expected: tables=schema_migrations, news_articles, ...

# 5) observability JSON 흐름 검증
FNPRICING_OBSERVABILITY_BACKEND=stdout python -m interfaces.cli analyze-address "테스트" 2>&1 | grep -c '"event"'
# expected: 8  (trace.start + generation × 3 (planner, critic, report) × 2 (start/end) + trace.end)
```

5 가지가 모두 통과하면 시스템이 의도대로 동작.
