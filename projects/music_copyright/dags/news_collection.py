"""음악 저작권 — 뉴스 수집 Airflow DAG."""
from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from core.pipelines.tasks import (
        load_config_task, build_plan_task, check_quota_task,
        search_and_save_task, rule_filter_task, embed_task,
        dedup_task, llm_tag_task, build_graph_signals_task, save_summary_task,
    )
    from projects.music_copyright.profile import MUSIC_COPYRIGHT_PROFILE

    _DEFAULT_ARGS = {"owner": "fnpricing", "retries": 1, "retry_delay": timedelta(minutes=5)}

    with DAG(
        dag_id="music_copyright_news_collection",
        description="음악 저작권 감성평가용 뉴스 수집",
        schedule_interval="0 7 * * *",
        start_date=datetime(2025, 1, 1),
        catchup=False,
        default_args=_DEFAULT_ARGS,
        tags=["fnpricing", "music", "news"],
    ) as dag:
        _config = load_config_task(MUSIC_COPYRIGHT_PROFILE)
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
    dag = None  # type: ignore
