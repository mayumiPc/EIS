from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


ALL_CLASS_NAMES: Tuple[str, ...] = (
    "mitsubishi",
    "hitachi",
    "otis",
    "toshiba",
    "thyssenkrupp",
    "westinghouse",
    "montgomery",
)


@dataclass(frozen=True)
class ModelConfig:
    class_names: Tuple[str, ...] = ALL_CLASS_NAMES
    input_size: int = 224
    model_path: Path = Path("models/eis_classifier_base.pt")
    frame_interval: int = 20


@dataclass(frozen=True)
class RecommendationWeights:
    safety: float = 0.2
    noise: float = 0.2
    speed: float = 0.2
    maintenance: float = 0.2
    energy: float = 0.1
    cost: float = 0.1


USE_CASE_PRESETS = {
    "hospital": RecommendationWeights(0.35, 0.15, 0.20, 0.20, 0.05, 0.05),
    "office": RecommendationWeights(0.20, 0.10, 0.35, 0.15, 0.10, 0.10),
    "residential": RecommendationWeights(0.20, 0.25, 0.10, 0.20, 0.15, 0.10),
    "hotel": RecommendationWeights(0.20, 0.25, 0.20, 0.10, 0.10, 0.15),
    "factory": RecommendationWeights(0.20, 0.05, 0.15, 0.30, 0.10, 0.20),
}

