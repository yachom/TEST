"""등기사항증명서 PDF 도구 — HITL 단계에서 사용자가 발급받은 PDF 를 받는다.

현재 상태 (POC):
  - 파일 받아 metadata (size, sha256, page_count) 만 저장
  - 본문 파싱은 NotImplementedError — 별도 단독 도구로 추후 구현
  - 저장 위치: var/uploads/registry/<scope_id>/<filename>

사용 위치 (현재):
  - analyze-address CLI 의 --pdf-path 옵션
  - TransactionTool 의 HITL 안내 후, 사용자가 다음 호출에 PDF 경로를 첨부

사용 위치 (추후):
  - 단독 CLI: analyze-registry-pdf <path> — PDF 파싱 후 등기 분석
  - 다른 도구의 의존성으로 호출
"""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.tools.base import BaseTool


_DEFAULT_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "var" / "uploads" / "registry"


@dataclass(frozen=True)
class RegistryPdfMetadata:
    original_path: str
    stored_path: str
    filename: str
    size_bytes: int
    sha256: str
    page_count: Optional[int]
    uploaded_at: str


class RegistryPdfTool(BaseTool):
    """등기사항증명서 PDF 업로드 + metadata 추출.

    파싱(텍스트/표 추출, 권리관계 분석)은 추후 별도 도구로 구현.
    """

    @property
    def name(self) -> str:
        return "registry_pdf_tool"

    @property
    def description(self) -> str:
        return (
            "사용자가 정부24/인터넷등기소에서 발급받은 등기사항증명서 PDF 를 받아 "
            "저장하고 metadata 를 반환한다. PDF 본문 파싱은 별도 도구."
        )

    def __init__(self, upload_root: Optional[Path] = None) -> None:
        self._root = upload_root or _DEFAULT_UPLOAD_ROOT

    def run(self, **kwargs) -> dict:
        pdf_path = kwargs.get("pdf_path")
        scope_id = kwargs.get("scope_id", "default")
        if not pdf_path:
            raise ValueError("pdf_path is required")
        meta = self._ingest(Path(pdf_path), scope_id)
        return {
            "source_type": "registry_pdf",
            "source_id": meta.sha256,
            "content": {
                "filename": meta.filename,
                "stored_path": meta.stored_path,
                "size_bytes": meta.size_bytes,
                "sha256": meta.sha256,
                "page_count": meta.page_count,
                "uploaded_at": meta.uploaded_at,
                "parsed": False,
                "parse_status": "deferred — parsing tool not yet implemented",
            },
        }

    def _ingest(self, src: Path, scope_id: str) -> RegistryPdfMetadata:
        if not src.exists():
            raise FileNotFoundError(f"PDF not found: {src}")
        if src.suffix.lower() != ".pdf":
            raise ValueError(f"Expected .pdf, got: {src.suffix}")

        target_dir = self._root / scope_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src.name
        shutil.copy2(src, target)

        return RegistryPdfMetadata(
            original_path=str(src),
            stored_path=str(target),
            filename=src.name,
            size_bytes=target.stat().st_size,
            sha256=_sha256(target),
            page_count=_page_count(target),
            uploaded_at=datetime.utcnow().isoformat() + "Z",
        )

    @staticmethod
    def parse(pdf_path: str) -> dict:
        """추후 단독 PDF 파서로 교체될 자리. 현재는 미구현."""
        raise NotImplementedError(
            "Registry PDF parsing not yet implemented. "
            "Will be a standalone tool — see core/tools/registry_pdf_tool.py."
        )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _page_count(path: Path) -> Optional[int]:
    """PDF 페이지 수. PyPDF2 같은 의존성이 없으면 None — POC 에서는 best-effort."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        return data.count(b"/Type /Page") + data.count(b"/Type/Page") or None
    except Exception:
        return None
