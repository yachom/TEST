# fnpricing

STO(Security Token Offering) 기초자산 감정평가 파이프라인.

## 프로젝트 목적

기존 기초자산 조각투자 시장에서 발행가와 시장가의 괴리는 발행가 산출 단계에서 사회적 가치에 대한 평가가 누락된 데 기인한다는 가설에서 출발한다. 본 프로젝트는 이 누락된 평가축을 보완하기 위해 뉴스·정책·규제·평판 등 비정형 신호를 LLM 온톨로지 기반으로 정형화하여 STO 기초자산의 감정평가를 수행한다.

## 평가 3축

모든 STO 기초자산은 다음 3개 축으로 평가된다.

| 축 | 책임 | 본 프로젝트의 범위 |
|---|---|---|
| 정량평가 (Quantitative) | 현금흐름 기반 — DCF, NOI, Cap Rate 등 | 기존 정량평가 사용 (목업) |
| 구조평가 (Structural) | 토큰·발행 구조, 신탁 구조 등 | 기존 증권 구조평가 차용 (목업) |
| 감정평가 (Sentiment) | 시장·정책·평판 신호의 온톨로지 매핑 | **본 프로젝트의 핵심 구현 대상** |

## POC 자산

| 자산 | 평가 대상 | 상태 |
|---|---|---|
| 상가형 부동산 | 건물(PNU), 입점업체(사업자번호) | MVP 진행 중 |
| 음악 저작권 | 음원(ISRC), 아티스트, 발행사 | Placeholder |

POC 종료 후 두 자산의 공통점·차이점을 기반으로 추후 자산 확장 시의 공통화 수준을 결정한다.

## 두 실행 흐름

본 시스템은 두 개의 흐름이 공유 저장소(`signal_store` + `GraphStore`) 를 매개로 연결된다.
**본 레포는 라이브러리 + on-demand 분석**, **배치 파이프라인은 별도 레포 [`fnpricing-batch`](https://github.com/yachom/fnpricing-batch) 가 운영** ([D-19](docs/DECISIONS.md#d-19)).

1. **배치 파이프라인 (Airflow)** — 별도 레포
   주기적으로 외부 신호(뉴스 / 규제 / 시장 동향)를 수집하여 자산 무관 Market & Policy Signal 을 적재.
   본 레포의 `core/pipelines/tasks.py` 를 import 해 DAG 가 호출.

2. **On-demand 주소 분석** (멀티 에이전트 Flow) — 본 레포
   주소 입력 → 공적 API 1차 수집 → ExplorationFlow (자율 추가 수집) → 온톨로지 매핑 → 그래프 DB → 보고서 → QAFlow.

두 흐름은 같은 온톨로지 어휘 + 공유 DB (추후 PostgreSQL) 를 통해 자동 연결된다.

상세 흐름은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 참조.

## 빠른 시작

```bash
# 의존성 설치 (기본 — Airflow 없음, 가벼움)
pip install -e ".[dev]"

# 실제 LLM / Langfuse observability 사용 시
pip install -e ".[dev,anthropic,observability]"

# 로컬에서 Airflow 도 띄우고 싶다면 (보통은 fnpricing-batch 레포 사용)
pip install -e ".[dev,airflow]"

# 전체 파이프라인 1회 실행 (Mock Provider)
python -m interfaces.cli run-once

# 단일 키워드 검색
python -m interfaces.cli search "상가 공실률" --no-save

# On-demand 주소 분석 (Stub LLM + Mock 도구)
python -m interfaces.cli analyze-address "강남구 역삼동 123-45"

# 테스트
pytest
```

LLM 호출 / 토큰 사용량을 관측하려면 `.env` 에 `FNPRICING_OBSERVABILITY_BACKEND=langfuse` + Langfuse 키를 설정. 상세는 [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md#observability)와 [config/runtime.yaml](config/runtime.yaml).

## 디렉토리 구조 개요

```
fnpricing-real/
├── core/             # 자산 무관 공통 도구 (collectors, processors, evaluation 추상)
│   ├── llm/          # PromptCatalog, prompts/*.yaml, pricing.yaml (LLM 자산 분리)
│   └── shared/infra/observability/  # TraceBackend (NoOp / Stdout / Langfuse)
├── projects/         # 자산별 평가 프로젝트
│   ├── commercial_real_estate/
│   └── music_copyright/
├── interfaces/       # Composition Root, CLI
├── config/           # 자산 무관 정책 (임계치, API 한도, observability)
└── docs/             # 설계 문서
```

상세 구조는 [docs/CODE_STRUCTURE.md](docs/CODE_STRUCTURE.md) 참조.

## 추가 문서

새 합류자 권장 읽기 순서: README → ARCHITECTURE → **IMPLEMENTATION_STATUS** → **RUNTIME_BEHAVIOR** → AGENT_DESIGN → ONTOLOGY → CODE_STRUCTURE → DECISIONS → POC_PLAN → EXTENSION_GUIDE.

| 문서 | 내용 |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 전체 시스템 아키텍처, 두 흐름의 연결 방식, 데이터 흐름, observability |
| [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) | **현재 무엇이 동작하는가 + Mock/Stub 인벤토리 + Phase 4 교체 우선순위** |
| [docs/RUNTIME_BEHAVIOR.md](docs/RUNTIME_BEHAVIOR.md) | **CLI 명령별 실제 입력/출력 + 모드 매트릭스 + sanity 체크** |
| [docs/AGENT_DESIGN.md](docs/AGENT_DESIGN.md) | 멀티 에이전트 Flow, PolicyGate, evidence trace, LangGraph 라우팅 |
| [docs/ONTOLOGY.md](docs/ONTOLOGY.md) | 온톨로지 매핑 정책 (어댑터 + LLM fallback), 그래프 DB scope_id |
| [docs/CODE_STRUCTURE.md](docs/CODE_STRUCTURE.md) | 디렉토리 구조, core/projects 분리 원칙, 핵심 추상화 명세 |
| [docs/DECISIONS.md](docs/DECISIONS.md) | 주요 설계 결정의 이유 / 트레이드오프 / 기각된 대안 |
| [docs/POC_PLAN.md](docs/POC_PLAN.md) | POC 2 자산의 평가 계획 및 단계별 목표 |
| [docs/EXTENSION_GUIDE.md](docs/EXTENSION_GUIDE.md) | 새 자산·데이터 소스·평가축·도구·어댑터·서브 에이전트·prompt·observability 추가 절차 |
