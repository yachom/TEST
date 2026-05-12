from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlunparse

from core.collectors.news.models import NewsArticle, SearchQuery


_HTML_TAG = re.compile(r"<[^>]+>")


class NewsNormalizer:
    """Provider 원본 응답 dict → NewsArticle 변환."""

    def normalize(self, raw: dict, query: SearchQuery) -> NewsArticle:
        title = self._clean(raw.get("title", ""))
        description = self._clean(raw.get("description", ""))
        original_link = raw.get("originallink", "")
        provider_link = raw.get("link", "")
        pub_date = self._parse_date(raw.get("pubDate", ""))
        normalized_url = self._normalize_url(original_link or provider_link)
        content_hash = self._hash(title, description)

        return NewsArticle(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            original_link=original_link,
            provider_link=provider_link,
            pub_date=pub_date,
            collected_at=datetime.now(tz=timezone.utc),
            search_query=query.text,
            search_group=query.group_name,
            provider=query.provider,
            normalized_url=normalized_url,
            content_hash=content_hash,
            asset_family=query.asset_family,
            asset_class=query.asset_class,
            raw_response=raw,
        )

    @staticmethod
    def _clean(text: str) -> str:
        return _HTML_TAG.sub("", text).strip()

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        normalized = parsed._replace(query="", fragment="")
        return urlunparse(normalized).rstrip("/")

    @staticmethod
    def _hash(title: str, description: str) -> str:
        text = f"{title}|{description}".encode("utf-8")
        return hashlib.sha256(text).hexdigest()
