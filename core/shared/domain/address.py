from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AddressIdentifier:
    """주소 식별자 — On-demand 분석의 기본 키"""
    raw_address: str
    pnu: Optional[str] = None                # 토지고유번호 19자리
    bupjungdong_code: Optional[str] = None   # 법정동 코드 10자리
    building_mgmt_no: Optional[str] = None   # 건물관리번호
    road_address: Optional[str] = None
    jibun_address: Optional[str] = None

    @property
    def is_identified(self) -> bool:
        return self.pnu is not None or self.building_mgmt_no is not None

    @property
    def primary_key(self) -> str:
        """저장소 조회에 사용할 단일 키 — PNU 우선"""
        if self.pnu:
            return f"pnu:{self.pnu}"
        if self.building_mgmt_no:
            return f"mgmt:{self.building_mgmt_no}"
        return f"raw:{self.raw_address}"
