from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from core.shared.config.settings import DatabaseSettings


@dataclass(frozen=True)
class SchemaInitResult:
    database_url: str
    schema_version: int
    tables: tuple[str, ...]


class DatabaseSchemaInitializer:
    """Create the initial relational schema for local/dev storage."""

    _TABLES = (
        "schema_migrations",
        "news_articles",
        "article_embeddings",
        "ontology_tags",
        "market_signals",
        "run_summaries",
        # ---- 확장 자리 (현재는 스키마만 생성, write 미연결) ----
        # 추후 Sqlite*Store 구현체가 추가되면 활성화됨.
        "analysis_runs",
        "evaluation_claims",
        "llm_calls",
        "agent_evidence_steps",
    )

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings

    def initialize(self) -> SchemaInitResult:
        scheme, path = self._parse_sqlite_url(self._settings.url)
        if scheme != "sqlite":
            raise ValueError(f"Unsupported database scheme for schema init: {scheme}")

        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.executescript(self._sqlite_schema_sql())
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, description) VALUES (?, ?)",
                (self._settings.schema_version, "initial news pipeline schema"),
            )
            conn.commit()

        return SchemaInitResult(
            database_url=self._settings.url,
            schema_version=self._settings.schema_version,
            tables=self._TABLES,
        )

    @staticmethod
    def _parse_sqlite_url(url: str) -> tuple[str, Path]:
        parsed = urlparse(url)
        if parsed.scheme != "sqlite":
            return parsed.scheme, Path("")
        if parsed.path in ("", "/"):
            raise ValueError("SQLite database URL must include a file path")
        if parsed.netloc:
            raw_path = f"//{parsed.netloc}{parsed.path}"
        elif parsed.path.startswith("/./"):
            raw_path = parsed.path[1:]
        else:
            raw_path = parsed.path
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        return "sqlite", path

    @staticmethod
    def _sqlite_schema_sql() -> str:
        return """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS news_articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            original_link TEXT NOT NULL,
            provider_link TEXT NOT NULL,
            pub_date TEXT,
            collected_at TEXT NOT NULL,
            search_query TEXT NOT NULL,
            search_group TEXT NOT NULL,
            provider TEXT NOT NULL,
            normalized_url TEXT NOT NULL UNIQUE,
            content_hash TEXT NOT NULL UNIQUE,
            asset_family TEXT,
            asset_class TEXT,
            raw_response_json TEXT,
            ingestion_status TEXT NOT NULL,
            filter_status TEXT NOT NULL,
            filter_exclude_reason TEXT,
            embedding_status TEXT NOT NULL,
            dedup_status TEXT NOT NULL,
            dedup_reference_id TEXT,
            tag_status TEXT NOT NULL,
            tag_exclude_reason TEXT,
            graph_status TEXT NOT NULL,
            graph_exclude_reason TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_news_articles_filter_status ON news_articles(filter_status);
        CREATE INDEX IF NOT EXISTS idx_news_articles_embedding_status ON news_articles(embedding_status);
        CREATE INDEX IF NOT EXISTS idx_news_articles_dedup_status ON news_articles(dedup_status);
        CREATE INDEX IF NOT EXISTS idx_news_articles_tag_status ON news_articles(tag_status);
        CREATE INDEX IF NOT EXISTS idx_news_articles_graph_status ON news_articles(graph_status);

        CREATE TABLE IF NOT EXISTS article_embeddings (
            article_id TEXT PRIMARY KEY,
            vector_json TEXT NOT NULL,
            model TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(article_id) REFERENCES news_articles(id)
        );

        CREATE TABLE IF NOT EXISTS ontology_tags (
            article_id TEXT PRIMARY KEY,
            asset_family TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            influence_direction TEXT NOT NULL,
            influence_strength TEXT NOT NULL,
            influence_period TEXT NOT NULL,
            applicability TEXT NOT NULL,
            applied_scope TEXT NOT NULL,
            affected_evaluation_factors_json TEXT NOT NULL,
            affected_asset_subtypes_json TEXT NOT NULL,
            event_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            rationale TEXT NOT NULL,
            confidence REAL NOT NULL,
            tagged_at TEXT NOT NULL,
            llm_model TEXT NOT NULL,
            raw_llm_response TEXT,
            graph_done INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(article_id) REFERENCES news_articles(id)
        );

        CREATE TABLE IF NOT EXISTS market_signals (
            signal_id TEXT PRIMARY KEY,
            article_id TEXT NOT NULL,
            asset_family TEXT,
            asset_class TEXT,
            signal_type TEXT,
            influence_direction TEXT,
            influence_strength TEXT,
            influence_period TEXT,
            applicability TEXT,
            applied_scope TEXT,
            affected_evaluation_factors_json TEXT,
            confidence REAL,
            summary TEXT,
            tagged_at TEXT,
            payload_json TEXT NOT NULL,
            upserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS run_summaries (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            summary_json TEXT NOT NULL
        );

        -- ===================================================================
        -- 확장 자리 (현재는 스키마만, write 미연결).
        -- core/shared/stores/{analysis_run_store, evaluation_claim_store}.py
        -- core/shared/infra/observability/recorders.py
        -- 의 Sqlite 구현체가 추후 추가되면 채워진다.
        -- ===================================================================

        -- on-demand 주소 분석 1회분 메타 + 누적 metric.
        CREATE TABLE IF NOT EXISTS analysis_runs (
            scope_id TEXT PRIMARY KEY,                -- analysis_<uuid>
            asset_class TEXT NOT NULL,
            address TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            total_cost_usd REAL NOT NULL DEFAULT 0.0,
            total_input_tokens INTEGER NOT NULL DEFAULT 0,
            total_output_tokens INTEGER NOT NULL DEFAULT 0,
            total_llm_calls INTEGER NOT NULL DEFAULT 0,
            total_tool_calls INTEGER NOT NULL DEFAULT 0,
            report_summary TEXT,
            report_json TEXT,
            error TEXT,
            metadata_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_runs_asset_class ON analysis_runs(asset_class);
        CREATE INDEX IF NOT EXISTS idx_analysis_runs_started_at ON analysis_runs(started_at);

        -- 3축 평가 결과 (sentiment / quantitative / structural × target).
        CREATE TABLE IF NOT EXISTS evaluation_claims (
            claim_id TEXT PRIMARY KEY,
            scope_id TEXT,                            -- on-demand 면 analysis_*, 배치면 batch_*
            asset_id TEXT NOT NULL,
            target_type TEXT NOT NULL,                -- building, tenant, song, artist
            target_key TEXT NOT NULL,                 -- PNU, 사업자번호, ISRC 등
            dimension TEXT NOT NULL,                  -- sentiment | quantitative | structural
            score REAL NOT NULL,
            rationale TEXT,
            evidence_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_evaluation_claims_asset_id ON evaluation_claims(asset_id);
        CREATE INDEX IF NOT EXISTS idx_evaluation_claims_scope_id ON evaluation_claims(scope_id);
        CREATE INDEX IF NOT EXISTS idx_evaluation_claims_dimension ON evaluation_claims(dimension);
        CREATE INDEX IF NOT EXISTS idx_evaluation_claims_created_at ON evaluation_claims(created_at);

        -- LLM 호출 단위 metric (토큰/비용/지연/prompt 버전).
        CREATE TABLE IF NOT EXISTS llm_calls (
            call_id TEXT PRIMARY KEY,
            scope_id TEXT,                            -- analysis_* | batch_* | NULL
            role TEXT NOT NULL,                       -- ontology_tagging, exploration.planner, ...
            model TEXT NOT NULL,
            prompt_key TEXT,                          -- exploration.planner (PromptCatalog key)
            prompt_version_hash TEXT,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0.0,
            latency_ms INTEGER,
            occurred_at TEXT NOT NULL,
            error TEXT,
            metadata_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_llm_calls_scope_id ON llm_calls(scope_id);
        CREATE INDEX IF NOT EXISTS idx_llm_calls_role ON llm_calls(role);
        CREATE INDEX IF NOT EXISTS idx_llm_calls_model ON llm_calls(model);
        CREATE INDEX IF NOT EXISTS idx_llm_calls_occurred_at ON llm_calls(occurred_at);

        -- 에이전트 evidence step 영구화 — 어떤 (서브)에이전트가 어떤 도구를 호출했는지.
        CREATE TABLE IF NOT EXISTS agent_evidence_steps (
            step_id_global INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_id TEXT NOT NULL,
            step_id INTEGER NOT NULL,                 -- scope 내부 sequential id
            actor TEXT NOT NULL,                      -- exploration.planner, qa.verifier, ...
            tool_name TEXT NOT NULL,
            rationale TEXT,
            input_summary_json TEXT,
            result_summary_json TEXT,
            occurred_at TEXT NOT NULL,
            UNIQUE(scope_id, step_id)
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_steps_scope_id ON agent_evidence_steps(scope_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_steps_actor ON agent_evidence_steps(actor);
        """
