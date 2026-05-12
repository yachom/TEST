from abc import ABC, abstractmethod
from typing import Optional


class DocumentStore(ABC):
    """사용자가 업로드한 PDF 및 파싱 결과 저장소 (On-demand용)."""

    @abstractmethod
    def save_document(self, address_key: str, filename: str, raw_bytes: bytes, parsed_text: str, metadata: dict | None = None) -> str:
        ...

    @abstractmethod
    def get(self, document_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def find_by_address(self, address_key: str) -> list[dict]:
        ...
