"""상가형 부동산 평가 대상(BuildingTarget, TenantTarget) 테스트."""
import pytest

from projects.commercial_real_estate.targets.building import BuildingTarget
from projects.commercial_real_estate.targets.tenant import TenantTarget


def test_building_target_unique_key():
    t = BuildingTarget(pnu="1234567890123456789", address="서울시 강남구")
    assert t.unique_key() == "building:1234567890123456789"


def test_building_target_label_with_address():
    t = BuildingTarget(pnu="1234567890123456789", address="서울시 강남구 테헤란로 1")
    assert t.label() == "서울시 강남구 테헤란로 1"


def test_building_target_label_fallback():
    t = BuildingTarget(pnu="1234567890123456789")
    assert "PNU:" in t.label()


def test_tenant_target_unique_key():
    t = TenantTarget(business_number="1234567890", business_name="테스트 카페")
    assert t.unique_key() == "tenant:1234567890"


def test_tenant_target_label():
    t = TenantTarget(business_number="1234567890", business_name="테스트 카페")
    assert t.label() == "테스트 카페"


def test_tenant_target_label_fallback():
    t = TenantTarget(business_number="1234567890")
    assert "사업자:" in t.label()


def test_building_target_is_hashable():
    t1 = BuildingTarget(pnu="1111111111111111111")
    t2 = BuildingTarget(pnu="1111111111111111111")
    assert t1 == t2
    assert hash(t1) == hash(t2)


def test_targets_have_distinct_target_types():
    assert BuildingTarget.target_type != TenantTarget.target_type
