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
        """
