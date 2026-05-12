"""SignalJoiner — 자동 수집 그래프와 온디멘드 분석 그래프의 연결 (POC 보류).

배경: 옵션 A 채택 시 같은 온톨로지 어휘로 그래프화 → 공유 노드 통한 자동 연결로 충분.
별도 컴포넌트는 자동 수집 그래프화 정책 구체화 후 검토.
docs/DECISIONS.md D-15 참조.
"""
from __future__ import annotations


class SignalJoiner:
    """현 시점 placeholder. POC 에서는 호출되지 않는다."""

    def join(self, scope_id: str) -> None:
        raise NotImplementedError("SignalJoiner is intentionally not implemented in POC. See DECISIONS.md D-15.")
