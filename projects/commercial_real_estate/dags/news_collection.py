"""상가형 부동산 — 뉴스 수집 Airflow DAG.

DAG는 실행 순서만 정의한다. 비즈니스 로직은 core/pipelines/tasks.py 에 있다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.decorators import task
    from core.pipelines.tasks import (
        load_config_task,
        build_plan_task,
        check_quota_task,
        search_and_save_task,
        rule_filter_task,
        embed_task,
        dedup_task,
        llm_tag_task,
        build_graph_signals_task,
        save_summary_task,
    )
    from projects.commercial_real_estate.profile import COMMERCIAL_PROFILE

    _DEFAULT_ARGS = {
        "owner": "fnpricing",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    }

    with DAG(
        dag_id="commercial_real_estate_news_collection",
        description="상가형 부동산 감성평가용 뉴스 수집",
        schedule_interval="0 6 * * *",
        start_date=datetime(2025, 1, 1),
        catchup=False,
        default_args=_DEFAULT_ARGS,
        tags=["fnpricing", "commercial", "news"],
    ) as dag:
        _config = load_config_task(COMMERCIAL_PROFILE)
        _plan = build_plan_task(_config)
        _quota = check_quota_task(_plan)
        _search = search_and_save_task(_quota)
        _filter = rule_filter_task(_search)
        _embed = embed_task(_filter)
        _dedup = dedup_task(_embed)
        _tag = llm_tag_task(_dedup)
        _graph = build_graph_signals_task(_tag)
        save_summary_task(_graph)

except ImportError:
    # Airflow 미설치 환경에서도 모듈 import 가능하도록 처리
    dag = None  # type: ignore
