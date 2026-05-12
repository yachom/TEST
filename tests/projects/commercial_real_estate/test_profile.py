"""상가형 부동산 AssetProfile 테스트."""
import pytest

from projects.commercial_real_estate.profile import COMMERCIAL_PROFILE
from core.shared.domain.asset import AssetClass
from core.shared.domain.evaluation import EvaluationDimension


def test_profile_asset_class():
    assert COMMERCIAL_PROFILE.asset_class == AssetClass.COMMERCIAL


def test_profile_has_all_three_dimensions():
    dims = COMMERCIAL_PROFILE.evaluation_dimensions
    assert EvaluationDimension.QUANTITATIVE in dims
    assert EvaluationDimension.STRUCTURAL in dims
    assert EvaluationDimension.SENTIMENT in dims


def test_profile_has_news_collector():
    assert "news" in COMMERCIAL_PROFILE.collector_source_types


def test_profile_has_sentiment_targets():
    assert len(COMMERCIAL_PROFILE.sentiment_target_types) >= 2


def test_profile_config_path_exists():
    assert COMMERCIAL_PROFILE.config_path.exists()


def test_profile_ontology_schema_loadable():
    import importlib
    module = importlib.import_module(COMMERCIAL_PROFILE.ontology_schema_module)
    assert hasattr(module, "COMMERCIAL_EVALUATION_FACTORS")
    assert len(module.COMMERCIAL_EVALUATION_FACTORS) > 0
