"""Composition Root — 의존성 조립.

모든 구현체 선택과 주입은 이 모듈에서만 수행한다.
Airflow DAG, LLM Tool, CLI 모두 이 모듈의 팩토리 함수를 사용한다.

AssetProfile을 받아 해당 자산의 파이프라인을 조립한다.
새 자산 추가 시 _PROFILE_REGISTRY 에 AssetProfile 인스턴스만 등록하면 된다.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from core.shared.domain.asset import AssetClass
from core.shared.config.settings import (
    ObservabilitySettings,
    load_runtime_settings,
)
from core.shared.infra.embedding_adapter import StubEmbeddingAdapter
from core.shared.infra.graph_writer import NoOpGraphWriter
from core.shared.infra.llm_client import LLMClient, StubLLMClient
from core.shared.infra.db_schema import DatabaseSchemaInitializer
from core.shared.infra.observability.base import TraceBackend
from core.shared.infra.observability.noop_backend import NoOpBackend
from core.shared.infra.tracing_llm_client import TracingLLMClient
from core.llm.catalog import PromptCatalog

from core.collectors.news.mock import MockNewsSearchProvider
from core.collectors.news.naver import NaverNewsSearchProvider
from core.collectors.news.normalizer import NewsNormalizer
from core.collectors.news.repositories.in_memory.in_memory_news_repository import InMemoryNewsRepository
from core.collectors.news.repositories.in_memory.in_memory_embedding_repository import InMemoryEmbeddingRepository
from core.collectors.news.repositories.in_memory.in_memory_ontology_tag_repository import InMemoryOntologyTagRepository
from core.collectors.news.repositories.in_memory.in_memory_signal_store import InMemorySignalStore

from core.application.search_plan_service import SearchConfigService, SearchPlanService
from core.application.collection_service import NewsSearchApplicationService
from core.application.run_summary_service import RunSummaryService

from core.processors.filters.rule_filter import RuleFilterService
from core.processors.embedders.text_embedder import TextEmbedderService
from core.processors.deduplicators.semantic_dedup import SemanticDeduplicationService
from core.processors.taggers.sentiment_tagger import OntologyTaggingService
from core.processors.graph_writers.signal_writer import GraphSignalService

if TYPE_CHECKING:
    from core.shared.domain.evaluation import AssetProfile

_ROOT = Path(__file__).parent.parent

# PromptCatalog 는 stateless + cache 내장 → 프로세스 공용 인스턴스로 충분.
# 테스트에서 격리 필요 시 build_pipeline_from_profile / build_address_analysis_orchestrator 인자로 override.
_DEFAULT_PROMPT_CATALOG = PromptCatalog()


def _load_policy() -> dict:
    path = _ROOT / "config" / "policy.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_naver_credentials() -> list[tuple[str, str]]:
    """네이버 API credentials 로딩.

    NAVER_CLIENT_IDS / NAVER_CLIENT_SECRETS 가 콤마 구분이면 다중 키 (ApiKeyRotator).
    아니면 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 단일 키.
    둘 다 없으면 빈 리스트.
    """
    ids = os.environ.get("NAVER_CLIENT_IDS", "")
    secrets = os.environ.get("NAVER_CLIENT_SECRETS", "")
    if ids and secrets:
        id_list = [s.strip() for s in ids.split(",") if s.strip()]
        sec_list = [s.strip() for s in secrets.split(",") if s.strip()]
        if id_list and len(id_list) == len(sec_list):
            return list(zip(id_list, sec_list))

    single_id = os.environ.get("NAVER_CLIENT_ID", "")
    single_sec = os.environ.get("NAVER_CLIENT_SECRET", "")
    if single_id and single_sec:
        return [(single_id, single_sec)]
    return []


def _get_evaluation_factors(profile: "AssetProfile") -> list[str]:
    """AssetProfile 의 ontology_schema_module 에서 평가 요인 사전을 로드한다."""
    import importlib
    try:
        module = importlib.import_module(profile.ontology_schema_module)
        # 모듈에서 *_EVALUATION_FACTORS 변수를 자동 탐색
        for name in dir(module):
            if name.endswith("_EVALUATION_FACTORS"):
                return getattr(module, name)
    except (ImportError, AttributeError):
        pass
    return []


def build_pipeline_from_profile(
    profile: "AssetProfile",
    use_mock_provider: bool = True,
    prompt_catalog: PromptCatalog | None = None,
    trace_backend: TraceBackend | None = None,
) -> dict:
    """AssetProfile을 받아 해당 자산의 전체 파이프라인을 조립한다."""
    policy = _load_policy()
    runtime = load_runtime_settings()
    catalog = prompt_catalog or _DEFAULT_PROMPT_CATALOG
    backend = trace_backend or _build_trace_backend(runtime.observability)

    # Provider — 키 부재 시 자동으로 mock 으로 fallback (env 가이드)
    if use_mock_provider:
        provider = MockNewsSearchProvider()
    else:
        creds = _build_naver_credentials()
        provider = NaverNewsSearchProvider(credentials=creds) if creds else MockNewsSearchProvider()
    provider_registry = {provider.provider_name(): provider}

    # Repositories
    news_repo = InMemoryNewsRepository()
    embed_repo = InMemoryEmbeddingRepository()
    tag_repo = InMemoryOntologyTagRepository()
    signal_store = InMemorySignalStore()

    # Infra stubs
    embed_adapter = StubEmbeddingAdapter()
    llm_client = _build_llm_client(
        runtime.llm_for("ontology_tagging"),
        trace_backend=backend,
        role="ontology_tagging",
    )
    graph_writer = NoOpGraphWriter()

    # 자산별 평가 요인 사전 로드
    evaluation_factors = _get_evaluation_factors(profile)

    # Services
    config_service = SearchConfigService(profile.config_path)
    plan_service = SearchPlanService()
    search_service = NewsSearchApplicationService(provider_registry, NewsNormalizer(), news_repo)

    filter_cfg = policy.get("rule_filter", {})
    filter_service = RuleFilterService(
        repository=news_repo,
        signal_keywords=filter_cfg.get("signal_keywords", []),
        asset_keywords=filter_cfg.get("asset_keywords", []),
        min_text_length=filter_cfg.get("min_text_length", 10),
    )

    embed_service = TextEmbedderService(news_repo, embed_repo, embed_adapter)

    dedup_cfg = policy.get("semantic_dedup", {})
    dedup_service = SemanticDeduplicationService(
        news_repo, embed_repo,
        similarity_threshold=dedup_cfg.get("similarity_threshold", 0.92),
    )

    tag_cfg = policy.get("ontology_tagging", {})
    tagging_service = OntologyTaggingService(
        news_repo, tag_repo, llm_client, catalog,
        confidence_threshold=tag_cfg.get("confidence_threshold", 0.7),
        evaluation_factors=evaluation_factors,
    )

    graph_cfg = policy.get("graph_signal", {})
    graph_service = GraphSignalService(
        news_repo, tag_repo, signal_store, graph_writer,
        min_confidence=graph_cfg.get("min_confidence", 0.7),
    )

    summary_service = RunSummaryService()

    return {
        "config": config_service,
        "plan": plan_service,
        "search": search_service,
        "filter": filter_service,
        "embedding": embed_service,
        "dedup": dedup_service,
        "tagging": tagging_service,
        "graph": graph_service,
        "summary": summary_service,
    }


# ---------------------------------------------------------------------------
# AssetProfile 레지스트리 — 새 자산 추가 시 여기에 등록
# ---------------------------------------------------------------------------

def _build_profile_registry() -> dict[AssetClass, "AssetProfile"]:
    from projects.commercial_real_estate.profile import COMMERCIAL_PROFILE
    from projects.music_copyright.profile import MUSIC_COPYRIGHT_PROFILE
    return {
        AssetClass.COMMERCIAL: COMMERCIAL_PROFILE,
        AssetClass.MUSIC_COPYRIGHT: MUSIC_COPYRIGHT_PROFILE,
    }


def get_profile_by_asset_class(asset_class: AssetClass) -> "AssetProfile":
    registry = _build_profile_registry()
    profile = registry.get(asset_class)
    if profile is None:
        raise ValueError(f"등록되지 않은 자산 클래스: {asset_class}")
    return profile


# ---------------------------------------------------------------------------
# CLI / 레거시 호환용 헬퍼 — 'commercial'이 기본값
# ---------------------------------------------------------------------------

def build_news_pipeline(use_mock_provider: bool = True) -> dict:
    """하위 호환성 유지. 기본 자산은 상가형 부동산."""
    from projects.commercial_real_estate.profile import COMMERCIAL_PROFILE
    return build_pipeline_from_profile(COMMERCIAL_PROFILE, use_mock_provider=use_mock_provider)


def build_schema_initializer() -> DatabaseSchemaInitializer:
    runtime = load_runtime_settings()
    return DatabaseSchemaInitializer(runtime.database)


def _build_llm_client(
    settings,
    *,
    trace_backend: TraceBackend | None = None,
    role: str | None = None,
) -> LLMClient:
    """LLMSettings 기반 클라이언트 생성. trace_backend 주어지면 TracingLLMClient 로 wrap."""
    provider = settings.provider.lower()
    if provider == "stub":
        inner: LLMClient = StubLLMClient()
    else:
        from core.shared.infra.langchain_llm_client import LangChainLLMClient
        inner = LangChainLLMClient(settings)

    if trace_backend is None:
        return inner
    return TracingLLMClient(inner, trace_backend, role=role or settings.role)


def _build_trace_backend(settings: ObservabilitySettings | None = None) -> TraceBackend:
    """ObservabilitySettings 기반 백엔드 선택.

    backend 가 "langfuse" 인데 SDK 미설치 또는 키 부재면 LangfuseBackend 자체가
    내부적으로 disabled 모드로 fallback — 흐름 안 깨짐.
    """
    if settings is None:
        settings = load_runtime_settings().observability
    backend = (settings.backend or "noop").lower()

    if backend == "langfuse":
        from core.shared.infra.observability.langfuse_backend import LangfuseBackend
        return LangfuseBackend(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    if backend == "stdout":
        from core.shared.infra.observability.stdout_backend import StdoutBackend
        return StdoutBackend(include_prompts=settings.stdout_include_prompts)
    return NoOpBackend()


# ---------------------------------------------------------------------------
# On-demand 주소 분석 — Orchestrator 조립
# ---------------------------------------------------------------------------


def _build_address_tools_and_adapters(use_real_tools: bool):
    """주소 분석 도구들 + OntologyMapper 어댑터들 조립.

    키 조합:
      use_real_tools=False 또는 키 부족 → MockAddressInfoTool 1 개 (mock)
      JUSO + VWORLD 만                  → VworldTool
      JUSO + VWORLD + MOLIT             → VworldTool + TransactionTool

    반환: (tools: list[BaseTool], adapters: dict[source_type, BaseAdapter])
    """
    from core.processors.ontology_mapper.adapters.mock_adapter import MockAddressAdapter
    from core.tools.mock_address_info_tool import MockAddressInfoTool

    juso_key = os.environ.get("JUSO_CONFIRM_KEY", "")
    vworld_key = os.environ.get("VWORLD_API_KEY", "")
    molit_key = os.environ.get("MOLIT_SERVICE_KEY") or os.environ.get("DATA_GO_KR_SERVICE_KEY", "")

    if not (use_real_tools and juso_key and vworld_key):
        mock_tool = MockAddressInfoTool()
        mock_adapter = MockAddressAdapter()
        return [mock_tool], {mock_adapter.source_type: mock_adapter}

    from core.processors.ontology_mapper.adapters.vworld_adapter import VworldAdapter
    from core.tools.vworld_tool import VworldTool

    tools = [VworldTool(
        juso_key=juso_key,
        vworld_key=vworld_key,
        vworld_domain=os.environ.get("VWORLD_DOMAIN") or None,
    )]
    adapters = {VworldAdapter().source_type: VworldAdapter()}

    if molit_key:
        from core.processors.ontology_mapper.adapters.building_register_adapter import (
            BuildingRegisterAdapter,
        )
        from core.processors.ontology_mapper.adapters.transaction_adapter import TransactionAdapter
        from core.tools.building_register_tool import BuildingRegisterTool
        from core.tools.transaction_tool import TransactionTool

        policy = _load_policy()
        tx_cfg = policy.get("transaction", {}) or {}
        review_cfg = tx_cfg.get("registry_review_threshold", {}) or {}
        tools.append(TransactionTool(
            juso_key=juso_key,
            molit_service_key=molit_key,
            months=int(tx_cfg.get("months", 12)),
            registry_review_total_count=int(review_cfg.get("total_count", 20)),
            registry_review_recent_12_months=int(review_cfg.get("recent_12_months", 5)),
            always_trigger_review=bool(tx_cfg.get("always_trigger_review", False)),
        ))
        adapters[TransactionAdapter().source_type] = TransactionAdapter()

        tools.append(BuildingRegisterTool(
            juso_key=juso_key,
            molit_service_key=molit_key,
        ))
        adapters[BuildingRegisterAdapter().source_type] = BuildingRegisterAdapter()

    return tools, adapters


def build_address_analysis_orchestrator(
    profile: "AssetProfile",
    use_stub_llm: bool = True,
    use_real_tools: bool = False,
    prompt_catalog: PromptCatalog | None = None,
    trace_backend: TraceBackend | None = None,
):
    """On-demand 주소 분석을 위한 Orchestrator 조립.

    use_real_tools=True 이고 키가 있으면 VworldTool, 그 외에는 MockAddressInfoTool.
    use_stub_llm=True 면 StubLLMClient, 아니면 runtime.yaml 의 LLM.

    trace_backend=None 이면 runtime.yaml observability 설정 기반 자동 선택 (noop default).
    """
    catalog = prompt_catalog or _DEFAULT_PROMPT_CATALOG
    from core.agents.exploration.critic import Critic
    from core.agents.exploration.flow import ExplorationFlow
    from core.agents.exploration.planner import Planner
    from core.agents.exploration.retriever import Retriever
    from core.agents.initial_collector import InitialCollector
    from core.agents.orchestrator import Orchestrator
    from core.agents.policy import AgentPolicy, PolicyGate
    from core.agents.qa.analyzer import Analyzer
    from core.agents.qa.flow import QAFlow
    from core.agents.qa.retriever import QARetriever
    from core.agents.qa.synthesizer import Synthesizer
    from core.agents.qa.verifier import Verifier
    from core.collectors.news.repositories.in_memory.in_memory_signal_store import InMemorySignalStore
    from core.processors.graph_writers.pattern_builder import GraphPatternBuilder
    from core.processors.ontology_mapper.base import OntologyMapper
    from core.processors.ontology_mapper.llm_fallback import LLMFallbackMapper
    from core.reporting.report_builder import ReportBuilder
    from core.shared.stores.graph_store import InMemoryGraphStore
    from core.shared.stores.in_memory_report_store import InMemoryReportStore

    runtime = load_runtime_settings()
    backend = trace_backend or _build_trace_backend(runtime.observability)
    if use_stub_llm:
        llm = TracingLLMClient(StubLLMClient(), backend, role="address_analysis")
    else:
        llm = _build_llm_client(
            runtime.llm_for("ontology_tagging"),
            trace_backend=backend,
            role="address_analysis",
        )

    address_tools, address_adapters = _build_address_tools_and_adapters(use_real_tools)
    tool_registry = {tool.name: tool for tool in address_tools}
    tool_names = list(tool_registry.keys())

    initial_collector = InitialCollector(address_tools)

    exploration_policy = AgentPolicy(
        max_tool_calls=5,
        max_cost_usd=1.0,
        allowed_tools=tool_names,
    )
    exploration_gate = PolicyGate(exploration_policy)
    exploration_flow = ExplorationFlow(
        planner=Planner(llm, allowed_tools=exploration_policy.allowed_tools, prompt_catalog=catalog),
        retriever=Retriever(tool_registry, exploration_gate),
        critic=Critic(llm, prompt_catalog=catalog),
        gate=exploration_gate,
    )

    pattern_builder = GraphPatternBuilder()
    ontology_mapper = OntologyMapper(
        registry=address_adapters,
        llm_fallback=LLMFallbackMapper(llm, pattern_builder, prompt_catalog=catalog),
    )

    graph_store = InMemoryGraphStore()
    report_store = InMemoryReportStore()
    signal_store = InMemorySignalStore()
    report_builder = ReportBuilder(graph_store, llm, prompt_catalog=catalog)

    qa_flow = QAFlow(
        analyzer=Analyzer(llm, prompt_catalog=catalog),
        retriever=QARetriever(
            graph_store=graph_store,
            report_store=report_store,
            signal_store=signal_store,
        ),
        synthesizer=Synthesizer(llm, prompt_catalog=catalog),
        verifier=Verifier(llm, prompt_catalog=catalog),
    )

    return Orchestrator(
        initial_collector=initial_collector,
        exploration_flow=exploration_flow,
        ontology_mapper=ontology_mapper,
        graph_store=graph_store,
        report_builder=report_builder,
        report_store=report_store,
        qa_flow=qa_flow,
        trace_backend=backend,
    )
