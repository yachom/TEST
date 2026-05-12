"""로컬 디버깅 CLI.

사용 예시:
    python -m interfaces.cli run-once
    python -m interfaces.cli run-once --asset music_copyright
    python -m interfaces.cli search "상가 공실률" --no-save
    python -m interfaces.cli analyze-address "강남구 역삼동 123-45"
"""
from __future__ import annotations

import argparse
import uuid

from interfaces.composition import (
    build_address_analysis_orchestrator,
    build_pipeline_from_profile,
    build_schema_initializer,
    get_profile_by_asset_class,
)
from core.shared.domain.asset import AssetClass


def cmd_run_once(args) -> None:
    """전체 파이프라인을 1회 실행한다 (Mock Provider 사용)."""
    try:
        asset_class = AssetClass(args.asset)
    except ValueError:
        print(f"[오류] 알 수 없는 자산 클래스: {args.asset}")
        return

    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile, use_mock_provider=True)

    pipeline["config"].load()
    groups = pipeline["config"].get_active_groups()
    plan = pipeline["plan"].build(groups)

    run_id = str(uuid.uuid4())[:8]
    print(f"[run_once] asset={args.asset}  run_id={run_id}  queries={plan.total_queries}  est_calls={plan.estimated_calls}")

    result = pipeline["search"].execute(plan, save=True)
    print(f"  search  → fetched={result.total_fetched}  saved={result.new_saved}  dup={result.url_duplicates}")

    filter_results = pipeline["filter"].run_batch()
    passed = sum(1 for r in filter_results if r.passed)
    print(f"  filter  → total={len(filter_results)}  passed={passed}")

    embed_results = pipeline["embedding"].run_batch()
    print(f"  embed   → done={len(embed_results)}")

    dedup_results = pipeline["dedup"].run_batch()
    novel = sum(1 for r in dedup_results if r.is_novel)
    print(f"  dedup   → novel={novel}  duplicate={len(dedup_results) - novel}")

    tag_results = pipeline["tagging"].run_batch()
    ok = sum(1 for r in tag_results if r.success)
    print(f"  tagging → ok={ok}  failed={len(tag_results) - ok}")

    candidates = pipeline["graph"].run_batch()
    queued = sum(1 for c in candidates if c.is_graph_eligible)
    print(f"  graph   → queued={queued}")

    print("[run_once] 완료")


def cmd_search(args) -> None:
    """단일 키워드로 뉴스를 검색한다."""
    from interfaces.composition import build_news_pipeline
    from core.collectors.news.models import SearchGroup, SearchPlan, SearchQuery

    pipeline = build_news_pipeline(use_mock_provider=True)
    query = SearchQuery(text=args.keyword, group_name="cli_search", provider="naver", max_display=args.max_results)
    plan = SearchPlan(groups=[], queries=[query], estimated_calls=1, provider_breakdown={"naver": 1})
    result = pipeline["search"].execute(plan, save=not args.no_save)
    print(f"[search] keyword='{args.keyword}'  fetched={result.total_fetched}  saved={result.new_saved}")


def cmd_init_db(args) -> None:
    """초기 DB 스키마를 생성한다."""
    initializer = build_schema_initializer()
    result = initializer.initialize()
    print(f"[init-db] url={result.database_url} schema_version={result.schema_version}")
    print(f"  tables={', '.join(result.tables)}")


def cmd_analyze_address(args) -> None:
    """On-demand 주소 분석 — InitialCollector → ExplorationFlow → OntologyMapper → GraphStore → ReportBuilder."""
    try:
        asset_class = AssetClass(args.asset)
    except ValueError:
        print(f"[오류] 알 수 없는 자산 클래스: {args.asset}")
        return

    profile = get_profile_by_asset_class(asset_class)
    orchestrator = build_address_analysis_orchestrator(
        profile,
        use_stub_llm=not args.real_llm,
        use_real_tools=args.real_tools,
    )
    try:
        result = orchestrator.analyze(args.address)
    except RuntimeError as e:
        print(f"[오류] {type(e).__name__}: {e}")
        return

    print(f"[analyze-address] scope_id={result.scope_id}")
    print(f"  evidence_steps={len(result.evidence)}")
    print(f"  report.node_count={result.report.get('node_count')}")
    print(f"  report.relation_count={result.report.get('relation_count')}")
    print(f"  report.nodes_by_label={result.report.get('nodes_by_label')}")
    print(f"  summary={result.report.get('summary')!r}")

    if args.show_graph:
        print("\n  Graph (LLM input):")
        for line in result.report.get("graph_text", "").splitlines():
            print(f"    {line}")

    review = result.report.get("registry_review")
    if review:
        print("\n[HITL] 등기사항증명서 PDF 업로드가 필요합니다.")
        print(f"  사유: {review.get('triggered_by')}")
        print(f"  마스킹 매칭 거래: {review.get('total_masked_count')}건 (최근 12개월 {review.get('recent_12_months_count')}건)")
        print(f"  발급/조회: {review.get('guidance_url')}")
        print(f"  안내: {review.get('guidance_text')}")
        if not args.pdf_path:
            print(f"  업로드: 다음 호출에 --pdf-path <path> 추가")

    if args.pdf_path:
        from core.tools.registry_pdf_tool import RegistryPdfTool
        try:
            pdf_result = RegistryPdfTool().run(pdf_path=args.pdf_path, scope_id=result.scope_id)
            content = pdf_result["content"]
            print("\n[PDF 업로드 완료]")
            print(f"  filename: {content['filename']}")
            print(f"  stored:   {content['stored_path']}")
            print(f"  size:     {content['size_bytes']:,} bytes")
            print(f"  sha256:   {content['sha256'][:16]}...")
            print(f"  pages:    {content['page_count']}")
            print(f"  parse:    {content['parse_status']}")
        except (FileNotFoundError, ValueError) as e:
            print(f"\n[PDF 오류] {e}")

    if args.show_evidence:
        print("\n  Evidence steps:")
        for step in result.evidence.steps:
            print(f"    [{step.step_id}] {step.actor} → {step.tool_name}: {step.rationale}")

    if args.question:
        from core.reporting.qa_service import QAService
        qa = QAService(result.qa_flow)
        answer = qa.ask(result.scope_id, args.question)
        print(f"\n[qa] {answer['question']}")
        print(f"  answer={answer['answer']!r}")
        print(f"  verifier={answer['verifier_decision']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="fnpricing-cli")
    sub = parser.add_subparsers(dest="command")

    p_once = sub.add_parser("run-once", help="전체 파이프라인 1회 실행")
    p_once.add_argument("--asset", default="commercial", help="자산 클래스 (default: commercial)")

    sub.add_parser("init-db", help="초기 DB 스키마 생성")

    p_search = sub.add_parser("search", help="단일 키워드 뉴스 검색")
    p_search.add_argument("keyword", help="검색어")
    p_search.add_argument("--no-save", action="store_true", help="조회 전용 모드")
    p_search.add_argument("--max-results", type=int, default=5)

    p_analyze = sub.add_parser("analyze-address", help="On-demand 주소 분석")
    p_analyze.add_argument("address", help="분석 대상 주소")
    p_analyze.add_argument("--asset", default="commercial", help="자산 클래스 (default: commercial)")
    p_analyze.add_argument("--show-evidence", action="store_true", help="evidence trace 출력")
    p_analyze.add_argument("--show-graph", action="store_true", help="LLM 에 입력되는 직렬화된 그래프 출력")
    p_analyze.add_argument("--question", help="분석 후 추가로 질의할 내용 (optional)")
    p_analyze.add_argument("--real-tools", action="store_true",
                           help="실제 vworld/Juso API 호출 (JUSO_CONFIRM_KEY + VWORLD_API_KEY 필요. "
                                "MOLIT_SERVICE_KEY 가 추가로 있으면 실거래가 + HITL 등기 안내까지)")
    p_analyze.add_argument("--real-llm", action="store_true",
                           help="StubLLMClient 대신 runtime.yaml 의 LLM 사용")
    p_analyze.add_argument("--pdf-path",
                           help="등기사항증명서 PDF 경로. HITL 안내 후 사용자가 업로드할 때 사용")

    args = parser.parse_args()
    if args.command == "run-once":
        cmd_run_once(args)
    elif args.command == "init-db":
        cmd_init_db(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "analyze-address":
        cmd_analyze_address(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
