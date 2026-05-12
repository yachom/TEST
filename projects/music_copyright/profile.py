"""음악 저작권 AssetProfile 정의 — POC 2번째 자산."""
from pathlib import Path

from core.shared.domain.asset import AssetClass
from core.shared.domain.evaluation import AssetProfile, EvaluationDimension
from projects.music_copyright.targets.artist import ArtistTarget
from projects.music_copyright.targets.song import SongTarget

_CONFIG_DIR = Path(__file__).parent / "config"

MUSIC_COPYRIGHT_PROFILE = AssetProfile(
    asset_class=AssetClass.MUSIC_COPYRIGHT,
    evaluation_dimensions=[
        EvaluationDimension.QUANTITATIVE,
        EvaluationDimension.STRUCTURAL,
        EvaluationDimension.SENTIMENT,
    ],
    sentiment_target_types=[ArtistTarget, SongTarget],
    collector_source_types=["news", "streaming"],
    config_path=_CONFIG_DIR / "search_groups.yaml",
    ontology_schema_module="projects.music_copyright.config.ontology_schema",
)
