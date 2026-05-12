"""상가형 부동산 AssetProfile 정의."""
from pathlib import Path

from core.shared.domain.asset import AssetClass
from core.shared.domain.evaluation import AssetProfile, EvaluationDimension
from projects.commercial_real_estate.targets.building import BuildingTarget
from projects.commercial_real_estate.targets.tenant import TenantTarget

_CONFIG_DIR = Path(__file__).parent / "config"

COMMERCIAL_PROFILE = AssetProfile(
    asset_class=AssetClass.COMMERCIAL,
    evaluation_dimensions=[
        EvaluationDimension.QUANTITATIVE,
        EvaluationDimension.STRUCTURAL,
        EvaluationDimension.SENTIMENT,
    ],
    sentiment_target_types=[BuildingTarget, TenantTarget],
    collector_source_types=["news"],
    config_path=_CONFIG_DIR / "search_groups.yaml",
    ontology_schema_module="projects.commercial_real_estate.config.ontology_schema",
)
