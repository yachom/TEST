"""처리 파이프라인 상태 Enum 6종.

각 수집 레코드가 파이프라인 단계를 거치며 갖는 상태를 정의한다.
"""
from enum import Enum


class IngestionStatus(str, Enum):
    NEW = "new"
    URL_DUPLICATE = "url_duplicate"
    HASH_DUPLICATE = "hash_duplicate"
    SAVE_FAILED = "save_failed"


class FilterStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    EXCLUDED = "excluded"
    FAILED = "failed"


class FilterExcludeReason(str, Enum):
    ADVERTISEMENT = "advertisement"
    IRRELEVANT_ASSET = "irrelevant_asset"
    NO_SIGNAL_KEYWORD = "no_signal_keyword"
    INSUFFICIENT_TEXT = "insufficient_text"
    DUPLICATE_ARTICLE = "duplicate_article"


class EmbeddingStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    EXCLUDED = "excluded"


class DedupStatus(str, Enum):
    PENDING = "pending"
    NOVEL = "novel"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class TagStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    EXCLUDED = "excluded"


class TagExcludeReason(str, Enum):
    FILTER_EXCLUDED = "filter_excluded"
    SEMANTIC_DUPLICATE = "semantic_duplicate"
    INSUFFICIENT_INPUT = "insufficient_input"
    LOW_CONFIDENCE = "low_confidence"


class GraphStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    DONE = "done"
    FAILED = "failed"
    EXCLUDED = "excluded"


class GraphExcludeReason(str, Enum):
    NOT_RELEVANT = "not_relevant"
    LOW_CONFIDENCE = "low_confidence"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    TAG_EXCLUDED = "tag_excluded"
