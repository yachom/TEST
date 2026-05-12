"""PromptCatalog 동작 + enum drift 검증.

drift 테스트:
  tagging.sentiment / mapping.llm_fallback 의 enum 값이 코드 (AssetFamily, SignalType 등)
  와 일치하는지. 코드 enum 변경 시 yaml 갱신 강제.
"""
from __future__ import annotations

import pytest

from core.llm.catalog import (
    PromptCatalog,
    PromptDefinitionError,
    PromptNotFoundError,
)
from core.shared.domain.asset import AssetClass, AssetFamily
from core.shared.domain.ontology_schema import (
    Applicability,
    AppliedScope,
    InfluenceDirection,
    InfluencePeriod,
    InfluenceStrength,
    SignalType,
)


_CATALOG = PromptCatalog()


def test_catalog_lists_all_expected_keys():
    keys = set(_CATALOG.list_keys())
    expected = {
        "exploration.planner",
        "exploration.critic",
        "qa.analyzer",
        "qa.synthesizer",
        "qa.verifier",
        "tagging.sentiment",
        "mapping.llm_fallback",
        "reporting.report",
    }
    missing = expected - keys
    assert not missing, f"missing prompt keys: {missing}"


def test_planner_render_substitutes_variables():
    rendered = _CATALOG.render(
        "exploration.planner",
        tools="news_search_tool, vworld_tool",
        address="강남구 역삼동 123-45",
        initial_count=3,
        retrieved_section="",
        feedback_section="",
    )
    assert "news_search_tool, vworld_tool" in rendered.system
    assert "강남구 역삼동" in rendered.user
    assert "3 records" in rendered.user
    assert rendered.response_schema is not None
    assert rendered.response_schema["required"] == ["calls"]


def test_render_missing_variable_raises():
    with pytest.raises(KeyError):
        _CATALOG.render("qa.analyzer")  # missing $question


def test_unknown_key_raises_not_found():
    with pytest.raises(PromptNotFoundError):
        _CATALOG.get("nonexistent.prompt")


def test_to_llm_request_carries_schema_and_text():
    rendered = _CATALOG.render("qa.analyzer", question="What is the cap rate?")
    req = rendered.to_llm_request(temperature=0.1, max_tokens=512)
    assert req.system_prompt.startswith("Classify the user question")
    assert req.user_prompt == "What is the cap rate?"
    assert req.response_schema is not None
    assert req.temperature == 0.1
    assert req.max_tokens == 512


def test_version_hash_changes_when_template_changes(tmp_path):
    # 격리된 prompt root 로 테스트
    prompt_dir = tmp_path / "prompts" / "ex"
    prompt_dir.mkdir(parents=True)

    (prompt_dir / "p.yaml").write_text(
        "version: 1\nsystem: A\nuser: B $x\nschema:\n  type: object\n",
        encoding="utf-8",
    )
    catalog_v1 = PromptCatalog(root=tmp_path / "prompts")
    h1 = catalog_v1.get("ex.p").version_hash

    (prompt_dir / "p.yaml").write_text(
        "version: 2\nsystem: A2\nuser: B $x\nschema:\n  type: object\n",
        encoding="utf-8",
    )
    catalog_v2 = PromptCatalog(root=tmp_path / "prompts")
    h2 = catalog_v2.get("ex.p").version_hash

    assert h1 != h2


# ---------------------------------------------------------------------------
# enum drift 검증 — yaml 의 enum 값이 코드 enum 과 일치해야 함
# ---------------------------------------------------------------------------


def _enum_values(enum_cls) -> set[str]:
    return {e.value for e in enum_cls}


def test_tagging_sentiment_enums_match_code():
    template = _CATALOG.get("tagging.sentiment")
    schema = template.response_schema
    assert schema is not None
    props = schema["properties"]

    drift_pairs = [
        ("asset_family", AssetFamily),
        ("asset_class", AssetClass),
        ("signal_type", SignalType),
        ("influence_direction", InfluenceDirection),
        ("influence_strength", InfluenceStrength),
        ("influence_period", InfluencePeriod),
        ("applicability", Applicability),
        ("applied_scope", AppliedScope),
    ]
    for field_name, enum_cls in drift_pairs:
        yaml_values = set(props[field_name]["enum"])
        code_values = _enum_values(enum_cls)
        assert yaml_values == code_values, (
            f"enum drift detected in tagging.sentiment.{field_name}: "
            f"yaml={yaml_values}, code={code_values}"
        )


def test_mapping_fallback_enums_match_code():
    template = _CATALOG.get("mapping.llm_fallback")
    schema = template.response_schema
    assert schema is not None
    props = schema["properties"]

    drift_pairs = [
        ("signal_type", SignalType),
        ("influence_direction", InfluenceDirection),
        ("influence_strength", InfluenceStrength),
    ]
    for field_name, enum_cls in drift_pairs:
        yaml_values = set(props[field_name]["enum"])
        code_values = _enum_values(enum_cls)
        assert yaml_values == code_values, (
            f"enum drift detected in mapping.llm_fallback.{field_name}: "
            f"yaml={yaml_values}, code={code_values}"
        )
