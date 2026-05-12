from enum import Enum


class SignalType(str, Enum):
    MARKET = "market"
    POLICY = "policy"
    REGULATION = "regulation"
    MACRO = "macro"
    DEMAND_SUPPLY = "demand_supply"
    RISK = "risk"
    STO_SYSTEM = "sto_system"


class InfluenceDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class InfluenceStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class InfluencePeriod(str, Enum):
    SHORT = "short"    # 1개월 미만
    MEDIUM = "medium"  # 1~12개월
    LONG = "long"      # 12개월 이상


class Applicability(str, Enum):
    DIRECT = "direct"                          # 직접 적용 가능
    NEEDS_VERIFICATION = "needs_verification"  # 자산별 추가 확인 필요
    BACKGROUND_ONLY = "background_only"        # 배경 맥락으로만 사용
    NOT_RELEVANT = "not_relevant"              # 관련 없음


class AppliedScope(str, Enum):
    NATIONAL = "national"
    REGIONAL = "regional"
    LOCAL = "local"
    ASSET_SPECIFIC = "asset_specific"
